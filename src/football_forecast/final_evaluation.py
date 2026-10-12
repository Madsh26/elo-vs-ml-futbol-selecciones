"""Evaluate immutable candidates with causal states and explicit small-stratum rules."""
from pathlib import Path
from collections import defaultdict,deque
from datetime import datetime,timezone
import hashlib
import json
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
