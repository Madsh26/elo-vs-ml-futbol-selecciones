"""Evaluate immutable candidates with causal states and explicit small-stratum rules."""
from pathlib import Path
from collections import defaultdict,deque
from datetime import datetime,timezone
import hashlib
import json
import re
import zipfile
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import minimize
from scipy.special import expit
from .ingestion import load_study_data,MATCH_KEY,archive_before,NameRegistry,digest_file
from .elo_calibration import EloParameters,CalibratedElo,per_match_metrics
from .selection_review import build_batches,elo_from_batches,form_features
from .preparation import EvidenceState
from .selected_models import score_losses,effective_rho
from .models import score_matrix,matrix_1x2

MODEL_NAMES={'frequency':'Frecuencias históricas','elo':'Solo Elo con sede fija','logistic':'Logística con Elo y forma',
 'ordinal':'Regresión ordinal','xgboost':'XGBoost 1X2','poisson':'Poisson independiente',
 'dixon_coles':'Dixon-Coles con covariables','xgboost_poisson':'XGBoost Poisson'}
PROBABILITY_COLUMNS=['p_home_win','p_draw','p_away_win']


def now():return datetime.now(timezone.utc).isoformat()


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def event(folder,kind,**values):
    with (folder/'chronology.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps({'at_utc':now(),'event':kind,**values},ensure_ascii=False)+'\n')


def active_protocol(root):
    folder=root/'reports/final_evaluation'
    seal=json.loads((folder/'active_protocol.json').read_text(encoding='utf-8'))
    if not seal['explicit_approval_received']:raise ValueError('Explicit human approval required')
    if digest_file(root/seal['protocol_file'])!=seal['protocol_sha256']:raise ValueError('Protocol hash mismatch')
    return json.loads((root/seal['protocol_file']).read_text(encoding='utf-8')),seal


def bundles(root):
    return {name:joblib.load(root/f'reports/models_selected/model_{name}.joblib') for name in MODEL_NAMES}


def causal_frames(history,fixtures,parameters):
    if history.date.max()>=pd.Timestamp('2026-06-10'):raise ValueError('Post-cutoff result used as input')
    batches=build_batches(history)
    ratings=elo_from_batches(batches,parameters)
    full=form_features(history,ratings,'all_assumed')
    full['elo_effective']=(full.elo_diff+parameters.home_advantage*full.venue_sign)/400
    full['strong_teams']=full.elo_home.gt(1700)&full.elo_away.gt(1700)
    elo=CalibratedElo(parameters)
    for date,rows in batches:
        elo.prepare_day([t for r in rows for t in (r.home_team,r.away_team)],date)
        elo.update_day(rows)
    evidence=EvidenceState()
    # Same goal window policy as frozen training; no new model fit.
    working=history.copy()
    working['home_score_90']=working.x12_home_score
    working['away_score_90']=working.x12_away_score
    for _,day in working.groupby('date',sort=True):evidence.update_day(list(day.itertuples(index=False)))
    opponents=defaultdict(lambda:deque(maxlen=10))
    for r in ratings.itertuples(index=False):
        opponents[r.home_team].append(r.elo_away);opponents[r.away_team].append(r.elo_home)
    future=[]
    for r in fixtures.itertuples(index=False):
        f={**r._asdict(),**evidence.features(r)}
        f['elo_home'],f['elo_away']=elo.ratings[r.home_team],elo.ratings[r.away_team]
        f['elo_diff']=f['elo_home']-f['elo_away']
        f['venue_sign']=0 if r.neutral else int(r.home_team==r.country)-int(r.away_team==r.country)
        f['elo_effective']=(f['elo_diff']+parameters.home_advantage*f['venue_sign'])/400
        f['gf_diff']=f['gf5_home']-f['gf5_away'];f['ga_diff']=f['ga5_home']-f['ga5_away']
        f['form_diff']=f['form5_home']-f['form5_away']
        oh=np.mean(opponents[r.home_team]) if opponents[r.home_team] else 1500.
        oa=np.mean(opponents[r.away_team]) if opponents[r.away_team] else 1500.
        f['opponent_diff']=(oh-oa)/400
        f['goal_coverage_sum']=f['goals_90_coverage5_home']+f['goals_90_coverage5_away']
        future.append(f)
    return full,pd.DataFrame(future),elo


def predict(frame,loaded):
    result={};symmetry={}
    for name,bundle in loaded.items():
        model=bundle['model'];x=frame[bundle['features']].fillna(0).to_numpy(float)
        p=model.predict_proba(x)
        difference=float(np.max(np.abs(p-model.predict_proba(x*np.asarray(bundle['signs']))[:,::-1]))) if len(frame) else 0.
        if difference>1e-9:raise ValueError(f'Symmetry failed: {name}')
        if np.any(p<0) or not np.allclose(p.sum(axis=1),1,atol=1e-12):raise ValueError('Invalid probabilities')
        available=[c for c in ['match_id','group','date','date_utc','home_team','away_team','country','neutral',
            'elo_home','elo_away','competitive','competition_family','shootout_record','proven_extra_time_goals',
            'x12_uncertain_timing','strong_teams','goal_training_eligible'] if c in frame]
        out=frame[available].reset_index(drop=True)
        out[PROBABILITY_COLUMNS]=p
        if hasattr(model,'rates'):
            lh,la=model.rates(x)
            out['lambda_home'],out['lambda_away']=lh,la
            out['rho']=effective_rho(lh,la,model.rho)
            out['rho_clamped']=np.abs(out.rho-model.rho)>1e-12
        result[name]=out;symmetry[name]=difference
    return result,symmetry


def freeze_predictions(root,integrity):
    protocol,seal=active_protocol(root)
    folder=root/'reports/final_evaluation'
    if (folder/'predictions_seal.json').exists():raise ValueError('Predictions already frozen; do not overwrite')
    loaded=bundles(root)
    params=EloParameters(**loaded['elo']['elo_parameters'])
    print('Entrada: resultados exclusivamente anteriores a 2026-06-10; no evaluación',flush=True)
    data=load_study_data(root,'2026-06-10')
    data.history.to_csv(folder/'history_precut.csv',index=False)
    write_json(folder/'ingestion_precut_audit.json',data.audit)
    full,future,state=causal_frames(data.history,data.fixtures,params)
    full.to_csv(folder/'features_precut.csv',index=False)
    future.to_csv(folder/'features_72_frozen.csv',index=False)
    predictions,symmetry=predict(future,loaded)
    paths=[]
    for name,pred in predictions.items():
        path=folder/f'group_forecasts_{name}.csv';pred.to_csv(path,index=False);paths.append(path)
    scores=[]
    for r in predictions['poisson'].itertuples(index=False):
        matrix,tail=score_matrix(r.lambda_home,r.lambda_away,r.rho,tolerance=1e-12)
        if np.max(np.abs(matrix_1x2(matrix)-np.array([r.p_home_win,r.p_draw,r.p_away_win])))>1e-9:
            raise AssertionError('Poisson matrix/1X2 mismatch')
        for h,a in np.ndindex(matrix.shape):
            scores.append({'match_id':r.match_id,'home_goals':h,'away_goals':a,'probability':matrix[h,a],
                           'omitted_tail_mass':tail})
    path=folder/'group_score_matrix_poisson.csv';pd.DataFrame(scores).to_csv(path,index=False);paths.append(path)
    # Historical predictions contain no evaluated losses and no post-cutoff labels.
    reserved=full[full.date.ge('2023-01-01')]
    prior,_=predict(reserved,loaded)
    for name,pred in prior.items():pred.to_csv(folder/f'semiconfirmatory_probabilities_{name}.csv',index=False)
    write_json(folder/'state_at_cutoff.json',{'cutoff_exclusive':'2026-06-10','latest_result':str(data.history.date.max().date()),
        'elo':dict(state.ratings),'last_match':{k:str(v.date()) for k,v in state.last.items()},'model_weights_refitted':False})
    paths.extend([folder/'features_72_frozen.csv',folder/'state_at_cutoff.json'])
    stamp={'sealed_at_utc':now(),'protocol_file':seal['protocol_file'],'protocol_sha256':seal['protocol_sha256'],
        'protocol_commit':integrity['protocol_commit'],'models_commit':integrity['models_selected_commit'],
        'model_weights_refitted':False,'group_matches':len(future),'teams':len(set(future.home_team)|set(future.away_team)),
        'max_symmetry_error':symmetry,'files':{p.relative_to(root).as_posix():digest_file(p) for p in paths},
        'official_worldcup_results_loaded_at_utc':None,'post2022_metrics_computed':False}
    write_json(folder/'predictions_seal.json',stamp)
    event(folder,'group_predictions_sealed',seal_sha256=digest_file(folder/'predictions_seal.json'),
          protocol_sha256=seal['protocol_sha256'],matches=len(future))
    print(json.dumps(stamp,indent=2,ensure_ascii=False),flush=True)


def cluster_bootstrap(dates,values,frequency='Q',replicates=2000,seed=20261012):
    values=np.asarray(values,float)
    if len(values)==0:return [None,None],0
    frame=pd.DataFrame({'cluster':pd.to_datetime(dates).dt.to_period(frequency).astype(str),'value':values})
    grouped=frame.groupby('cluster').value.agg(['sum','count'])
    rng=np.random.default_rng(seed)
    picks=rng.integers(0,len(grouped),size=(replicates,len(grouped)))
    draws=grouped['sum'].to_numpy()[picks].sum(axis=1)/grouped['count'].to_numpy()[picks].sum(axis=1)
    return [float(x) for x in np.quantile(draws,[.025,.975])],len(grouped)


def estimable(target,minimum=200,events=30):
    counts=np.bincount(np.asarray(target,int),minlength=3)
    return len(target)>=minimum and bool((counts>=events).all())


def rps_values(y,p):
    ordered=p[:,::-1]
    actual=np.eye(3)[2-np.asarray(y,int)]
    return ((np.cumsum(ordered,axis=1)[:,:-1]-np.cumsum(actual,axis=1)[:,:-1])**2).sum(axis=1)/2


def score_predictions(pred,target):
    fields=target[MATCH_KEY+['x12_target','x12_home_score','x12_away_score','goal_training_eligible']].rename(
        columns={'goal_training_eligible':'strict_duration_verified'})
    out=pred.merge(fields,on=MATCH_KEY,validate='one_to_one')
    p=out[PROBABILITY_COLUMNS].to_numpy(float);y=out.x12_target.to_numpy(int)
    out['log_loss'],out['brier']=per_match_metrics(y,p)
    out['rps']=rps_values(y,p)
    out['accuracy']=(p.argmax(axis=1)==y).astype(float)
    out['actual_draw']=(y==1).astype(float)
    if 'lambda_home' in out:
        out['score_nll']=score_losses(out.x12_home_score.to_numpy(),out.x12_away_score.to_numpy(),
                                     out.lambda_home.to_numpy(),out.lambda_away.to_numpy(),out.rho.to_numpy())
    return out


def stratum_masks(frame,teams):
    h=frame.home_team.isin(teams);a=frame.away_team.isin(teams)
    return {'total':pd.Series(True,index=frame.index),'non_friendlies':frame.competitive,
        'friendlies':~frame.competitive,'worldcup':frame.competition_family.eq('worldcup'),
        'strong_teams':frame.elo_home.gt(1700)&frame.elo_away.gt(1700),
        'strong_non_friendlies':frame.elo_home.gt(1700)&frame.elo_away.gt(1700)&frame.competitive,
        'worldcup_48_mutual':h&a,'worldcup_48_any_opponent':h|a,
        'exclude_marked':~(frame.shootout_record|frame.proven_extra_time_goals.gt(0)),
        'strict_duration':frame.strict_duration_verified}


def calibration(data,model,population,eligible):
    rows=[];parameters=[]
    for k,column in enumerate(PROBABILITY_COLUMNS):
        probability=data[column].to_numpy(float);actual=data.x12_target.to_numpy(int)==k
        bins=np.minimum((probability*10).astype(int),9)
        ece=0.
        for b in range(10):
            mask=bins==b;n=int(mask.sum())
            mean=float(probability[mask].mean()) if n else None
            rate=float(actual[mask].mean()) if n else None
            if n:ece+=n*abs(mean-rate)/len(data)
            rows.append({'model':model,'stratum':population,'class':k,'bin':b,'matches':n,
                         'mean_probability':mean,'actual_rate':rate})
        entry={'model':model,'stratum':population,'class':k,'ece_10_bins':ece if len(data) else None,
               'intercept':None,'slope':None,'fit_status':'insufficient_stratum' if not eligible else 'pending'}
        if eligible:
            z=np.log(np.clip(probability,1e-6,1-1e-6)/np.clip(1-probability,1e-6,1-1e-6))
            x=np.column_stack([np.ones(len(z)),z]);y=actual.astype(float)
            def objective(t):
                eta=x@t
                return np.mean(np.logaddexp(0,eta)-y*eta), x.T@(expit(eta)-y)/len(y)
            result=minimize(objective,[0.,1.],jac=True,method='BFGS',options={'gtol':1e-7})
            if result.success and np.all(np.isfinite(result.x)):
                entry.update(intercept=float(result.x[0]),slope=float(result.x[1]),fit_status='diagnostic_only')
            else:entry['fit_status']='optimization_not_verified'
        parameters.append(entry)
    return rows,parameters


def summary_rows(predictions,protocol,bootstrap_frequency='Q',prefix=''):
    rows=[];reliability=[];calibration_parameters=[]
    baseline=predictions['elo']
    for model,pred in predictions.items():
        for name,mask in stratum_masks(pred,protocol['worldcup_48']).items():
            data=pred[mask].reset_index(drop=True)
            ref=baseline.merge(data[MATCH_KEY],on=MATCH_KEY,validate='one_to_one').reset_index(drop=True)
            if not data[MATCH_KEY].equals(ref[MATCH_KEY]):raise ValueError('Paired strata differ')
            y=data.x12_target.to_numpy(int)
            counts=np.bincount(y,minlength=3)
            eligible=estimable(y)
            row={'model':model,'stratum':name,'matches':len(data),'home_wins':int(counts[0]),
                 'draws':int(counts[1]),'away_wins':int(counts[2]),'estimable':eligible,
                 'evidence_status':'semiconfirmatory','bootstrap_unit':bootstrap_frequency,
                 'quarter_clusters':int(data.date.dt.to_period('Q').nunique()),
                 'month_clusters':int(data.date.dt.to_period('M').nunique()),
                 'ci_interpretation':'inferential_with_prior_exposure' if eligible else 'descriptive_small_stratum'}
            for metric in ['log_loss','brier','rps','accuracy','actual_draw','p_draw','score_nll']:
                if metric not in data:continue
                row[metric]=float(data[metric].mean()) if len(data) else None
                interval,_=cluster_bootstrap(data.date,data[metric],bootstrap_frequency)
                row[metric+'_ci_low'],row[metric+'_ci_high']=interval
            for metric in ['log_loss','brier','rps']:
                difference=data[metric].to_numpy()-ref[metric].to_numpy()
                row['difference_'+metric]=float(difference.mean()) if len(data) else None
                ci,_=cluster_bootstrap(data.date,difference,bootstrap_frequency)
                row['difference_'+metric+'_ci_low'],row['difference_'+metric+'_ci_high']=ci
            if bootstrap_frequency=='Q':
                bins,params=calibration(data,model,name,eligible)
                reliability.extend(bins);calibration_parameters.extend(params)
            rows.append(row)
    return pd.DataFrame(rows),pd.DataFrame(reliability),pd.DataFrame(calibration_parameters)


def evaluate_semiconfirmatory(root,integrity):
    protocol,seal=active_protocol(root);folder=root/'reports/final_evaluation'
    features=pd.read_csv(folder/'features_precut.csv',parse_dates=['date'])
    target=features[features.date.ge('2023-01-01')&features.date.lt('2026-06-10')].copy()
    # form_features marks ALL goals admitted under the assumed-duration policy.
    # Strict verification for sensitivity comes from the independent raw audit.
    raw=pd.read_csv(folder/'history_precut.csv',parse_dates=['date'],usecols=MATCH_KEY+['goal_training_eligible'])
    target=target.drop(columns='goal_training_eligible').merge(raw,on=MATCH_KEY,validate='one_to_one')
    predictions={}
    for name in MODEL_NAMES:
        pred=pd.read_csv(folder/f'semiconfirmatory_probabilities_{name}.csv',parse_dates=['date'])
        scored=score_predictions(pred,target)
        scored.to_csv(folder/f'semiconfirmatory_scored_{name}.csv',index=False)
        predictions[name]=scored
    print('Evaluación semiconfirmatoria; bootstrap trimestral y mensual',flush=True)
    quarters,bins,parameters=summary_rows(predictions,protocol,'Q')
    months,_,_=summary_rows(predictions,protocol,'M')
    quarters.to_csv(folder/'semiconfirmatory_metrics.csv',index=False)
    months.to_csv(folder/'semiconfirmatory_monthly_sensitivity.csv',index=False)
    bins.to_csv(folder/'semiconfirmatory_reliability.csv',index=False)
    parameters.to_csv(folder/'semiconfirmatory_calibration.csv',index=False)
    block_rows=[]
    for start,end in protocol['subperiods']:
        subset={name:p[p.date.ge(start)&p.date.lt(end)] for name,p in predictions.items()}
        block,_,_=summary_rows(subset,protocol,'Q')
        block['start'],block['end_exclusive']=start,end
        block_rows.append(block)
    block_table=pd.concat(block_rows,ignore_index=True)
    block_table.to_csv(folder/'semiconfirmatory_subperiods.csv',index=False)
    principal=quarters[quarters.model.eq('logistic')&quarters.stratum.eq('non_friendlies')].iloc[0]
    blocks=block_table[block_table.model.eq('logistic')&block_table.stratum.eq('non_friendlies')]
    improves=int((blocks.difference_log_loss<0).sum())
    confirmed=bool(principal.estimable and principal.difference_log_loss_ci_high<0 and principal.difference_brier<=0 and improves>=3)
    difference=np.abs(predictions['logistic'][PROBABILITY_COLUMNS].to_numpy()-predictions['poisson'][PROBABILITY_COLUMNS].to_numpy())
    conclusion={'evaluation_completed_at_utc':now(),'evidence':'semiconfirmatory, not untouched','selection_confirmed':confirmed,
        'blocks_improving':improves,'primary_log_loss_difference':float(principal.difference_log_loss),
        'primary_log_loss_difference_ci':[float(principal.difference_log_loss_ci_low),float(principal.difference_log_loss_ci_high)],
        'primary_brier_difference':float(principal.difference_brier),'model_weights_refitted':False,
        'product_discrepancy_mean_percentage_points':float(difference.mean()*100),
        'protocol_sha256':seal['protocol_sha256'],'prediction_commit':integrity['prediction_commit'],
        'matches':len(target),'actual_quarter_clusters':int(target.date.dt.to_period('Q').nunique()),
        'actual_month_clusters':int(target.date.dt.to_period('M').nunique())}
    write_json(folder/'semiconfirmatory_conclusion.json',conclusion)
    event(folder,'semiconfirmatory_evaluation_completed',**conclusion)
    print(json.dumps(conclusion,indent=2,ensure_ascii=False),flush=True)
    return conclusion


def parse_openfootball(text,registry,stage):
    """Parse explicit FT, HT and (for a.e.t.) regulation pairs, not goal minutes."""
    rows=[];day=None;group=None
    for line in text.splitlines():
        line=line.strip()
        gm=re.match(r'▪ Group ([A-L])$',line)
        if gm:group=gm.group(1)
        dm=re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(June|Jun|July|Jul)\s+(\d+)',line)
        if dm:
            day=pd.Timestamp(2026,6 if dm.group(1).startswith('Jun') else 7,int(dm.group(2)));continue
        match=re.match(r'(?:\((\d+)\)\s*)?(\d{1,2}:\d\d)\s+UTC([+-]\d+)\s+(.+?)\s+(\d+)-(\d+)\s+(.+?)\s*@\s*(.+)',line)
        if not match:continue
        if day is None:raise ValueError('Openfootball match without explicit date')
        mid,clock,offset,home,h,a,right,venue=match.groups()
        h,a=int(h),int(a);h90,a90=h,a
        extra='a.e.t.' in right
        if extra:
            regulation=re.match(r'a\.e\.t\.\s*\((\d+)-(\d+),\s*\d+-\d+\)',right)
            if not regulation:raise ValueError('Extra-time match without regulation pair')
            h90,a90=map(int,regulation.groups())
            right=right[regulation.end():]
        else:right=re.sub(r'^\(\d+-\d+\)\s*','',right)
        penalties=bool(re.search(r'\d+-\d+\s+pen\.',right))
        right=re.sub(r'^[,\s]*\d+-\d+\s+pen\.\s*','',right).strip(' ,')
        hour,minute=map(int,clock.split(':'))
        utc=day+pd.Timedelta(hours=hour-int(offset),minutes=minute)
        rows.append({'date':day,'date_utc':utc,'home_team':registry.normalize(home,day),
                     'away_team':registry.normalize(right,day),'recorded_home_score':h,'recorded_away_score':a,
                     'home_score_90':h90,'away_score_90':a90,'extra_time':extra,'shootout_record':penalties,
                     'stage':stage,'group':group,'openfootball_match_id':int(mid) if mid else None,
                     'venue':venue.split('##')[0].strip()})
    return pd.DataFrame(rows)


def orient_match(frame,home,away,date,tolerance_days=1):
    """Unordered pair + explicit date tolerance for UTC/local-day differences."""
    mask=(frame.home_team.eq(home)&frame.away_team.eq(away))|(frame.home_team.eq(away)&frame.away_team.eq(home))
    candidate=frame[mask].copy()
    candidate['date_distance']=(candidate.date.dt.normalize()-pd.Timestamp(date).normalize()).dt.days.abs()
    candidate=candidate[candidate.date_distance.le(tolerance_days)]
    if len(candidate)>1:raise ValueError(f'Ambiguous source match: {home} / {away}')
    if not len(candidate):return None
    row=candidate.iloc[0].to_dict();swapped=row['home_team']!=home
    row['swapped_to_fixture_order']=swapped
    if swapped:
        for h,a in [('recorded_home_score','recorded_away_score'),('x12_home_score','x12_away_score'),('home_score_90','away_score_90')]:
            if h in row:row[h],row[a]=row[a],row[h]
    return row


def world_bootstrap(dates,values,unit='date',replicates=2000):
    if unit=='match':
        keys=np.arange(len(values)).astype(str)
    else:keys=pd.to_datetime(dates).dt.strftime('%Y-%m-%d').to_numpy()
    grouped=pd.DataFrame({'key':keys,'value':values}).groupby('key').value.agg(['sum','count'])
    if not len(grouped):return [None,None],0
    picks=np.random.default_rng(20261012).integers(0,len(grouped),size=(replicates,len(grouped)))
    means=grouped['sum'].to_numpy()[picks].sum(axis=1)/grouped['count'].to_numpy()[picks].sum(axis=1)
    return [float(x) for x in np.quantile(means,[.025,.975])],len(grouped)


def world_summaries(predictions,population):
    rows=[];bins=[];parameters=[]
    ref=predictions['elo']
    for name,data in predictions.items():
        eligible=estimable(data.x12_target)
        count=np.bincount(data.x12_target.to_numpy(int),minlength=3)
        row={'model':name,'population':population,'matches':len(data),'estimable':eligible,
             'home_wins':int(count[0]),'draws':int(count[1]),'away_wins':int(count[2]),
             'evidence_status':'descriptive_small_sample','quarter_clusters':int(data.date.dt.to_period('Q').nunique()),
             'month_clusters':int(data.date.dt.to_period('M').nunique()),'date_clusters':int(data.date.dt.normalize().nunique())}
        for metric in ['log_loss','brier','rps','accuracy','actual_draw','p_draw','score_nll']:
            if metric not in data:continue
            row[metric]=float(data[metric].mean())
            ci,_=world_bootstrap(data.date,data[metric].to_numpy())
            row[metric+'_ci_low'],row[metric+'_ci_high']=ci
        delta=data.log_loss.to_numpy()-ref.log_loss.to_numpy()
        row['difference_log_loss']=float(delta.mean())
        ci,_=world_bootstrap(data.date,delta)
        row['difference_log_loss_ci_low'],row['difference_log_loss_ci_high']=ci
        ci,_=world_bootstrap(data.date,delta,'match')
        row['difference_log_loss_match_ci_low'],row['difference_log_loss_match_ci_high']=ci
        reliability,cal=calibration(data,name,population,eligible)
        bins.extend(reliability);parameters.extend(cal);rows.append(row)
    return pd.DataFrame(rows),pd.DataFrame(bins),pd.DataFrame(parameters)


def evaluate_worldcup(root,integrity):
    protocol,seal=active_protocol(root);folder=root/'reports/final_evaluation'
    if not (folder/'semiconfirmatory_conclusion.json').exists():raise ValueError('Semiconfirmatory stage must precede World Cup evaluation')
    record=folder/'official_results_load_record.json'
    if not record.exists():
        write_json(record,{'first_official_results_load_started_at_utc':now(),'prediction_commit':integrity['prediction_commit'],
                          'prediction_commit_time':integrity['prediction_commit_time'],'models_refitted':False})
        event(folder,'official_results_load_started',prediction_commit=integrity['prediction_commit'])
    source_path=folder/'official_worldcup_results_source.csv'
    if source_path.exists():world=pd.read_csv(source_path,parse_dates=['date'])
    else:
        loaded=load_study_data(root,'2026-07-21')
        world=loaded.history[loaded.history.tournament.eq('FIFA World Cup')&loaded.history.date.ge('2026-06-10')]
        world.to_csv(source_path,index=False)
    registry=NameRegistry()
    with zipfile.ZipFile(root/'data/raw/openfootball_worldcup.zip') as archive:
        group=parse_openfootball(archive.read('worldcup-master/2026--canada-usa-mexico/cup.txt').decode('utf-8-sig'),registry,'group')
        knock=parse_openfootball(archive.read('worldcup-master/2026--canada-usa-mexico/cup_finals.txt').decode('utf-8-sig'),registry,'knockout')
    if len(group)!=72 or len(knock)!=32:raise ValueError('Incomplete independent match catalogue')
    openfootball=pd.concat([group,knock],ignore_index=True)
    openfootball.to_csv(folder/'openfootball_worldcup_90.csv',index=False)
    import duckdb
    db=duckdb.connect(str(root/'data/raw/transfermarkt.duckdb'),read_only=True)
    transfer=db.execute("SELECT date,home_club_name AS home_team,away_club_name AS away_team,home_club_goals AS recorded_home_score,away_club_goals AS recorded_away_score,round FROM games WHERE competition_id='FIWC' AND date>=DATE '2026-06-11'").df()
    transfer['date']=pd.to_datetime(transfer.date)
    transfer=registry.frame(transfer,['home_team','away_team'])
    # Current 2026 spelling variants only; no historical federation merger.
    for column in ['home_team','away_team']:
        transfer[column]=transfer[column].replace({'Turkiye':'Turkey','Democratic Republic of the Congo':'DR Congo'})
    transfer.to_csv(folder/'transfermarkt_worldcup_results_source.csv',index=False)
    fixture=pd.read_csv(folder/'group_forecasts_logistic.csv',parse_dates=['date'])
    targets=[];cross=[];missing=[];consumed=set()
    for r in fixture.itertuples(index=False):
        primary=orient_match(world,r.home_team,r.away_team,r.date)
        secondary=orient_match(group,r.home_team,r.away_team,r.date)
        market=orient_match(transfer,r.home_team,r.away_team,r.date)
        if primary is None or secondary is None:
            missing.append({'match_id':r.match_id,'home_team':r.home_team,'away_team':r.away_team});continue
        consumed.add((primary['date'],frozenset([r.home_team,r.away_team])))
        h,a=int(primary['recorded_home_score']),int(primary['recorded_away_score'])
        # Group-stage duration is independently certified for every score, including 0-0.
        ok=(h,a)==(int(secondary['recorded_home_score']),int(secondary['recorded_away_score']))
        tm_ok=(h,a)==(int(market['recorded_home_score']),int(market['recorded_away_score'])) if market else None
        cross.append({'match_id':r.match_id,'home_team':r.home_team,'away_team':r.away_team,'primary_date':primary['date'],
             'fixture_utc_date':r.date,'openfootball_date':secondary['date'],'transfermarkt_date':market['date'] if market else None,
             'martj42_score':f'{h}-{a}','openfootball_score':f"{secondary['recorded_home_score']}-{secondary['recorded_away_score']}",
             'transfermarkt_score':f"{market['recorded_home_score']}-{market['recorded_away_score']}" if market else None,
             'openfootball_agrees':ok,'transfermarkt_agrees':tm_ok,'utc_local_date_difference':pd.Timestamp(primary['date']).normalize()!=r.date.normalize(),
             'swapped_primary_order':primary['swapped_to_fixture_order']})
        if not ok:raise ValueError('Group scores disagree; source adjudication required')
        targets.append({'match_id':r.match_id,'date':r.date,'actual_local_date':primary['date'],'home_team':r.home_team,'away_team':r.away_team,
             'x12_home_score':h,'x12_away_score':a,'x12_target':0 if h>a else 1 if h==a else 2,'goal_training_eligible':True,
             'duration_basis':'independent group-stage match catalogue, no extra time'})
    pd.DataFrame(cross).to_csv(folder/'worldcup_source_comparison.csv',index=False)
    pd.DataFrame(missing,columns=['match_id','home_team','away_team']).to_csv(folder/'worldcup_unmatched.csv',index=False)
    target=pd.DataFrame(targets)
    target.to_csv(folder/'group_results_90.csv',index=False)
    predictions={}
    for name in MODEL_NAMES:
        pred=pd.read_csv(folder/f'group_forecasts_{name}.csv',parse_dates=['date'])
        scored=score_predictions(pred[pred.match_id.isin(target.match_id)],target)
        scored.to_csv(folder/f'worldcup_group_scored_{name}.csv',index=False);predictions[name]=scored
    metrics,bins,cal=world_summaries(predictions,'groups')
    metrics.to_csv(folder/'worldcup_group_metrics.csv',index=False)
    bins.to_csv(folder/'worldcup_group_reliability.csv',index=False)
    cal.to_csv(folder/'worldcup_group_calibration.csv',index=False)
    error=predictions['logistic'].copy().sort_values('log_loss',ascending=False)
    error['actual_score']=error.x12_home_score.astype(str)+'-'+error.x12_away_score.astype(str)
    error.to_csv(folder/'worldcup_largest_errors.csv',index=False)
    # Knockout participants are known retrospectively. Freeze no model or policy from these outcomes.
    # Use the SAME pre-cutoff state; report conditional, hindsight-known matchups explicitly.
    ko=[];ko_cross=[]
    for r in knock.itertuples(index=False):
        primary=orient_match(world,r.home_team,r.away_team,r.date)
        if primary is None:continue
        full_agrees=(int(primary['recorded_home_score']),int(primary['recorded_away_score']))==(r.recorded_home_score,r.recorded_away_score)
        reconstructed=(int(primary['x12_home_score']),int(primary['x12_away_score']))
        reliable_agrees=not primary['x12_90_reconstructed'] or reconstructed==(r.home_score_90,r.away_score_90)
        ko_cross.append({'match_id':r.openfootball_match_id,'home_team':r.home_team,'away_team':r.away_team,
             'full_score_agrees':full_agrees,'verified_90_score_agrees':reliable_agrees,
             'martj42_regulation_score':f'{reconstructed[0]}-{reconstructed[1]}',
             'openfootball_regulation_score':f'{r.home_score_90}-{r.away_score_90}'})
        if not full_agrees or not reliable_agrees:continue
        h,a=r.home_score_90,r.away_score_90
        ko.append({'match_id':int(r.openfootball_match_id),'date':r.date_utc,'date_utc':str(r.date_utc),'home_team':r.home_team,'away_team':r.away_team,
          'country':primary['country'],'neutral':primary['neutral'],'tournament':'FIFA World Cup','competitive':True,'competition_family':'worldcup',
          'shootout_record':r.shootout_record,'proven_extra_time_goals':r.recorded_home_score+r.recorded_away_score-h-a,
          'x12_home_score':h,'x12_away_score':a,'x12_target':0 if h>a else 1 if h==a else 2,'goal_training_eligible':True,
          'x12_uncertain_timing':False})
    pd.DataFrame(ko_cross).to_csv(folder/'knockout_source_comparison.csv',index=False)
    if ko:
        ko_frame=pd.DataFrame(ko)
        history=pd.read_csv(folder/'history_precut.csv',parse_dates=['date'])
        loaded=bundles(root);params=EloParameters(**loaded['elo']['elo_parameters'])
        _,ko_features,_=causal_frames(history,ko_frame,params)
        ko_preds,_=predict(ko_features,loaded)
        ko_predictions={}
        for name,pred in ko_preds.items():
            scored=score_predictions(pred,ko_frame)
            scored.to_csv(folder/f'worldcup_knockout_scored_{name}.csv',index=False);ko_predictions[name]=scored
        km,kr,kc=world_summaries(ko_predictions,'knockouts_conditional_known_participants')
        km.to_csv(folder/'worldcup_knockout_metrics.csv',index=False)
        kr.to_csv(folder/'worldcup_knockout_reliability.csv',index=False)
        kc.to_csv(folder/'worldcup_knockout_calibration.csv',index=False)
    difference=np.abs(predictions['logistic'][PROBABILITY_COLUMNS].to_numpy()-predictions['poisson'][PROBABILITY_COLUMNS].to_numpy())
    conclusion={'evaluation_completed_at_utc':now(),'evidence':'descriptive only; 72 below inferential minimum',
       'groups_evaluated':len(target),'knockouts_evaluated':len(ko),'knockouts_excluded_source_disagreement':len(knock)-len(ko),
       'group_openfootball_discrepancies':int((~pd.DataFrame(cross).openfootball_agrees).sum()),
       'group_transfermarkt_discrepancies':int(pd.DataFrame(cross).transfermarkt_agrees.eq(False).sum()),
       'group_transfermarkt_matches':int(pd.DataFrame(cross).transfermarkt_agrees.notna().sum()),
       'utc_local_date_differences':int(pd.DataFrame(cross).utc_local_date_difference.sum()),
       'product_discrepancy_mean_percentage_points':float(difference.mean()*100),
       'knockout_interpretation':'conditional on hindsight-known participants, same pre-cutoff Elo/form state; no tournament forecasting claim',
       'first_official_results_load_started_at_utc':json.loads(record.read_text(encoding='utf-8'))['first_official_results_load_started_at_utc'],
       'prediction_commit':integrity['prediction_commit'],'models_refitted':False}
    write_json(folder/'worldcup_conclusion.json',conclusion)
    event(folder,'worldcup_descriptive_evaluation_completed',**conclusion)
    print(json.dumps(conclusion,indent=2,ensure_ascii=False),flush=True)
    return conclusion
