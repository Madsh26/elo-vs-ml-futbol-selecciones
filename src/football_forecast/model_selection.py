"""Pre-2023 joint Elo search and coherent probabilistic model selection."""
from pathlib import Path
from dataclasses import asdict, replace
from datetime import datetime, timezone
from itertools import product
import json
import hashlib
import joblib
import numpy as np
import pandas as pd
from .elo_calibration import EloParameters, BLOCKS, dated_history, per_match_metrics, block_interval
from .selection_review import (BOUNDARY, MATCH_KEY, GROUPS, build_batches, elo_from_batches,
    outcome_frame, fit_blocks, form_features, metric_rows, passes)
from .selected_models import ResultModel, GoalModel, score_losses, effective_rho
from .context_features import venue_sign
from .ingestion import digest_file
from .preparation import markdown_table

NAMES = {'frequency':'Frecuencias históricas', 'elo':'Solo Elo con sede fija',
         'logistic':'Logística con Elo y forma', 'ordinal':'Regresión ordinal con Elo',
         'xgboost':'XGBoost 1X2', 'poisson':'Poisson independiente',
         'dixon_coles':'Dixon-Coles con covariables', 'xgboost_poisson':'XGBoost Poisson'}
FORM = GROUPS['recent_form'][0]
FORM_SIGNS = GROUPS['recent_form'][1]
FEATURES = ['elo_effective']+FORM
SIGNS = [-1]+FORM_SIGNS


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def code_digest(path):
    """Hash source with LF line endings to permit Windows/Linux checkouts."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def protocol(output):
    """Persist commitments before loading the new search inputs or metrics."""
    definition = {
      'boundary_exclusive':BOUNDARY, 'blocks':BLOCKS,
      'goal_policy':'all_assumed: verified 90 where known, registered final otherwise; every score admitted',
      'membership_independent_of_score':True,
      'elo_grid':{'home_advantage':[60,100,120,150], 'inactivity_rate':[0,.1],
                  'k':['reference','higher'], 'margin_strength':[.5,1.]},
      'elo_selection':'minimum pooled non-friendly log loss; candidate eligible if paired excess <= one paired SE',
      'paired_se':'standard deviation of 400 paired bootstrap differences, whole calendar quarters, seed 20261012',
      'simplicity_order':['no inactivity regression','reference K','gamma 0.5','smaller home advantage','log loss'],
      'model_adoption':'non-friendly paired log-loss upper 95% CI < 0; mean Brier difference <= 0; at least 3/4 blocks improve',
      'model_tie_break':'smallest feature/model complexity among passing models within one paired SE of best',
      'score_model_selection':'minimum non-friendly score NLL among passing count candidates; if none pass, descriptive score model only',
      'complexity_order':['elo','logistic','ordinal','poisson','dixon_coles','xgboost','xgboost_poisson'],
      'bootstrap':{'replicates':400, 'unit':'calendar quarter', 'seed':20261012},
      'ece':{'bins':10, 'edges':'equal width [0,1]', 'classes':['home win','draw','away win']},
      'train_start':'2000-01-01',
      'training':'all earlier valid outcomes, both team orders; Elo state all available historical dates',
      'xgboost_fixed':{'n_estimators':160,'max_depth':2,'learning_rate':.04,'min_child_weight':20,
                        'reg_lambda':5,'subsample':1,'colsample_bytree':1,'threads':2,'seed':20261012},
      'calibration':'native probabilities; no post-hoc outcome calibration for count models, preserving score/1X2 coherence',
      'sensitivities':{
          'exclude_marked':'omit shootout or proven ET from count/form history, train and evaluation; retain all for Elo',
          'non_friendlies':'fit count models on all prior non-friendlies, evaluate separately',
          'strict_worldcup':'evaluate main count-model predictions on independently verified World Cup rows; not an alternative fitting population'},
      'form_admission':'approved all-assumed duration group; repeat against selected fixed-venue Elo and excluding marked history',
      'secondary_features':'repeat individual ablations vs Elo + free venue; report, do not silently add new groups',
      'symmetry':'predict both role orders, reconcile; count rates use one shared oriented regressor; tolerance 1e-9',
      'score_nll':'infinite-support joint likelihood, optional bounded Dixon-Coles correction',
      'count_rate_limits':[float(np.exp(-6)),12.],
      'rho_validity':'per-match clamp to positive low-score cell bounds; report activation',
      'no_2023_results':True, 'retrospective':True}
    path = output/'protocol.json'
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if 'score_model_selection' not in existing['definition'] and not (output/'selected_elo.json').exists():
            existing['definition']['score_model_selection']=definition['score_model_selection']
            existing['clarified_before_execution_at_utc']=datetime.now(timezone.utc).isoformat()
            save_json(path,existing)
        if existing['definition'] != json.loads(json.dumps(definition)):
            raise ValueError('Protocol already exists with different commitments')
        return existing
    registered = {'written_at_utc':datetime.now(timezone.utc).isoformat(), 'definition':definition}
    save_json(path, registered)
    return registered


def paired_se(pred, reference):
    left = pred[pred.competitive].reset_index(drop=True)
    right = reference[reference.competitive].reset_index(drop=True)
    if not left[MATCH_KEY].equals(right[MATCH_KEY]):
        raise ValueError('Paired SE requires the same matches')
    values = left.log_loss.to_numpy()-right.log_loss.to_numpy()
    grouped = pd.DataFrame({'quarter':left.date.dt.to_period('Q'), 'value':values}).groupby('quarter').value.agg(['sum','count'])
    rng = np.random.default_rng(20261012)
    picks = rng.integers(0,len(grouped),size=(400,len(grouped)))
    means = grouped['sum'].to_numpy()[picks].sum(axis=1)/grouped['count'].to_numpy()[picks].sum(axis=1)
    return float(values.mean()), float(means.std(ddof=1))


def joint_search(history, output):
    batches = build_batches(history)
    original = outcome_frame(history)
    predictions, parameters, rows = {}, {}, []
    for index,(home, inactivity, k, gamma) in enumerate(product([60,100,120,150],[0,.1],['reference','higher'],[.5,1.])):
        p = replace(EloParameters(),home_advantage=home,inactivity_rate=inactivity,margin_strength=gamma)
        if k == 'higher':
            p = replace(p,friendly_k=16,nations_k=24,continental_k=32,worldcup_k=48)
        name = f'H{home}_R{inactivity}_K{k}_G{gamma}'
        print(f'Elo conjunto {index+1}/32: {name}', flush=True)
        ratings = elo_from_batches(batches,p)
        frame = original.merge(ratings,on=MATCH_KEY,validate='one_to_one')
        frame['elo_effective']=(frame.elo_diff+p.home_advantage*venue_sign(frame))/400
        pred = fit_blocks(frame,['elo_effective'],[-1])
        predictions[name], parameters[name] = pred,p
        rows.append({'configuration':name, **asdict(p), 'k_level':k,
                     'log_loss':float(pred.loc[pred.competitive,'log_loss'].mean())})
    best = min(predictions,key=lambda n: predictions[n].loc[predictions[n].competitive,'log_loss'].mean())
    for row in rows:
        delta,se = paired_se(predictions[row['configuration']],predictions[best])
        row.update(excess_vs_minimum=delta,paired_standard_error=se,within_one_se=bool(delta<=se+1e-14))
    eligible = [r for r in rows if r['within_one_se']]
    chosen = min(eligible,key=lambda r:(r['inactivity_rate']!=0,r['k_level']!='reference',
                                       r['margin_strength'],r['home_advantage'],r['log_loss']))
    name = chosen['configuration']
    p = parameters[name]
    table = pd.DataFrame(rows)
    table['selected'] = table.configuration.eq(name)
    table.to_csv(output/'elo_joint_grid.csv',index=False)
    neighbors=[]
    selected_dims = [chosen[k] for k in ['home_advantage','inactivity_rate','k_level','margin_strength']]
    for row in rows:
        dims=[row[k] for k in ['home_advantage','inactivity_rate','k_level','margin_strength']]
        if sum(a!=b for a,b in zip(dims,selected_dims))<=1:
            entries=metric_rows(predictions[row['configuration']],row['configuration'],predictions[name])
            neighbors.extend([{**e,**asdict(parameters[row['configuration']])} for e in entries])
    pd.DataFrame(neighbors).to_csv(output/'elo_neighbors.csv',index=False)
    selection = {'parameters':asdict(p),'selected_configuration':name,'minimum_configuration':best,
                 'selection_completed_at_utc':datetime.now(timezone.utc).isoformat(),
                 'previous_inactivity_0_1_was_reference_not_selected_by_isolated_search':True,
                 'one_se_eligible_configurations':len(eligible),'reserved_results_opened':False}
    save_json(output/'selected_elo.json',selection)
    predictions[name].to_csv(output/'elo_predictions.csv',index=False)
    return p, elo_from_batches(batches,p), predictions[name], selection


def flagged(frame):
    return frame.shootout_record | frame.proven_extra_time_goals.gt(0)


def exclude_marked_features(history, ratings, params):
    clean = history.loc[~flagged(history)].copy()
    full = form_features(clean,ratings,'all_assumed')
    full['elo_effective']=(full.elo_diff+params.home_advantage*full.venue_sign)/400
    return full


def calibration_rows(pred, model, scope):
    rows=[]
    for klass,col in enumerate(['p_home_win','p_draw','p_away_win']):
        binid = np.minimum((pred[col].to_numpy()*10).astype(int),9)
        actual = pred.target.to_numpy()==klass
        for index in range(10):
            mask=binid==index
            if mask.any():
                rows.append({'model':model,'scope':scope,'class':klass,'bin':index,'matches':int(mask.sum()),
                    'mean_probability':float(pred[col].to_numpy()[mask].mean()),
                    'actual_rate':float(actual[mask].mean())})
    return rows


def model_metrics(pred, name, reference):
    extra = pred[pred.competition_family.eq('worldcup')]
    rows = metric_rows(pred,name,reference)
    if len(extra):
        ref=reference[reference.competition_family.eq('worldcup')]
        entries=metric_rows(extra,name,ref)
        rows += [{**r,'scope':'worldcup'} for r in entries if r['scope']=='total']
    reliability=[]
    for row in rows:
        scope=row['scope']
        data = pred if scope=='total' else pred[pred.competitive] if scope=='non_friendlies' else pred[~pred.competitive] if scope=='friendlies' else extra
        row['accuracy']=float((data[['p_home_win','p_draw','p_away_win']].to_numpy().argmax(axis=1)==data.target).mean())
        bins=calibration_rows(data,name,scope)
        reliability.extend(bins)
        for klass in range(3):
            row[f'ece_{klass}']=sum(r['matches']*abs(r['mean_probability']-r['actual_rate']) for r in bins if r['class']==klass)/len(data)
        if 'score_nll' in data:
            row['score_nll']=float(data.score_nll.mean())
            row['score_nll_ci']=block_interval(data.date,data.score_nll)
    return rows,reliability


def predictions_for(frame, kind, train_nonfriend=False):
    parts=[]
    columns=['elo_effective'] if kind in ('elo','ordinal','frequency') else FEATURES
    signs=[-1] if len(columns)==1 else SIGNS
    for start,end in BLOCKS:
        train=frame[(frame.date>='2000-01-01')&(frame.date<start)]
        if train_nonfriend:
            train=train[train.competitive]
        test=frame[(frame.date>=start)&(frame.date<end)]
        if train.date.max()>=pd.Timestamp(start):
            raise ValueError('Leaked fold')
        x,y=train[columns].to_numpy(float),train.target.to_numpy(int)
        xx=test[columns].to_numpy(float)
        out=test[MATCH_KEY+['competitive','competition_family','target','x12_uncertain_timing','goal_training_eligible',
                          'shootout_record','proven_extra_time_goals']].reset_index(drop=True)
        if kind in ('poisson','dixon_coles','xgboost_poisson'):
            fitted=GoalModel(kind,signs).fit(x,train.x12_home_score,train.x12_away_score)
            lh,la=fitted.rates(xx)
            out['lambda_home'],out['lambda_away']=lh,la
            out['rho']=effective_rho(lh,la,fitted.rho)
            out['rho_clamped']=np.abs(out.rho-fitted.rho)>1e-12
            out['score_nll']=score_losses(test.x12_home_score.to_numpy(),test.x12_away_score.to_numpy(),lh,la,fitted.rho)
        else:
            fitted=ResultModel('logistic' if kind=='elo' else kind,signs).fit(x,y)
        probability=fitted.predict_proba(xx)
        mirrored=fitted.predict_proba(xx*np.asarray(signs))[:,::-1]
        if np.max(np.abs(probability-mirrored))>1e-9:
            raise AssertionError(f'Role symmetry failed: {kind}')
        out['block_start']=start
        out[['p_home_win','p_draw','p_away_win']]=probability
        out['log_loss'],out['brier']=per_match_metrics(test.target.to_numpy(int),probability)
        parts.append(out)
    return pd.concat(parts,ignore_index=True)


def additional_ablations(root, full, baseline, output):
    from .elo_calibration import semester_rankings, backward_rank_join
    from .context_features import venue_altitude, altitude_lookup
    full=backward_rank_join(full,semester_rankings(root/'data/raw/fifa_rank_semesters.zip'))
    full['rank_diff']=(full.fifa_rank_away-full.fifa_rank_home).fillna(0)/200
    full['ranking_missing']=full.fifa_rank_home.isna()|full.fifa_rank_away.isna()
    full['points_diff']=((full.fifa_points_home-full.fifa_points_away)/(full.fifa_points_home+full.fifa_points_away)).replace([np.inf,-np.inf],np.nan)
    full['points_missing']=full.points_diff.isna()
    full=venue_altitude(full,altitude_lookup(root/'data/raw/geonames_cities15000.zip'))
    full['altitude_scaled']=full.venue_altitude_m/1000
    reference=fit_blocks(full,['elo_effective','venue_sign'],[-1,-1])
    rows=metric_rows(reference,'additional_venue',baseline)
    for name,(cols,signs) in GROUPS.items():
        pred=fit_blocks(full,['elo_effective','venue_sign']+cols,[-1,-1]+signs)
        entries=metric_rows(pred,name,reference)
        for r in entries:r['passes_criterion']=passes(entries)
        rows.extend(entries)
    pd.DataFrame(rows).to_csv(output/'secondary_ablations.csv',index=False)
    return rows


def run(root):
    output=root/'reports/models_selected'
    output.mkdir(parents=True,exist_ok=True)
    if (output/'freeze_manifest.json').exists():
        frozen=json.loads((output/'freeze_manifest.json').read_text(encoding='utf-8'))
        for artifact in frozen['models']:
            if digest_file(root/artifact['path'])!=artifact['sha256']:
                raise ValueError('Frozen model hash mismatch')
        if digest_file(output/'protocol.json')!=frozen['protocol_sha256']:
            raise ValueError('Frozen protocol hash mismatch')
        print('Modelos y protocolo congelados verificados; no reentreno ni sustituyo el congelado.',flush=True)
        return frozen
    registered=protocol(output)
    # Reuse the audited cohort; never load or type a reserved result.
    source=root/'reports/selection_review/historical_results.csv'
    ingestion=json.loads((root/'reports/selection_review/data_audit.json').read_text(encoding='utf-8'))
    if not source.exists():
        from .ingestion import load_study_data
        print('Reconstruyendo el historial auditado exclusivamente anterior a 2023',flush=True)
        load_study_data(root,BOUNDARY).history.to_csv(source,index=False)
    artifacts=ingestion.get('artifacts',[])
    if isinstance(artifacts,list):
        saved_hash=next((r['sha256'] for r in artifacts if r.get('file')==source.relative_to(root).as_posix()),None)
    else:
        saved_hash=artifacts.get(source.relative_to(root).as_posix())
    if isinstance(saved_hash,dict):
        saved_hash=saved_hash.get('sha256')
    if saved_hash and saved_hash!=digest_file(source):
        raise ValueError('Historical cohort differs from the audit')
    history=dated_history(source,BOUNDARY)
    for col in ['recorded_home_score','recorded_away_score','x12_home_score','x12_away_score',
                'proven_extra_time_goals','x12_target','assumed_home_score_90','assumed_away_score_90']:
        history[col]=pd.to_numeric(history[col],errors='raise')
    for col in ['competitive','shootout_record','x12_eligible','x12_uncertain_timing','independent_goal_catalogue','x12_90_reconstructed']:
        history[col]=history[col].str.casefold().eq('true')
    if history.empty or history.date.max()>=pd.Timestamp(BOUNDARY):
        raise ValueError('Invalid pre-2023 cohort')
    selection_path=output/'selected_elo.json'
    if selection_path.exists() and (output/'elo_joint_grid.csv').exists():
        selection=json.loads(selection_path.read_text(encoding='utf-8'))
        params=EloParameters(**selection['parameters'])
        ratings=elo_from_batches(build_batches(history),params)
        baseline=pd.read_csv(output/'elo_predictions.csv',parse_dates=['date'])
    else:
        params,ratings,baseline,selection=joint_search(history,output)
    print('Forma principal y sensibilidad sin partidos marcados',flush=True)
    full=form_features(history,ratings,'all_assumed')
    full['elo_effective']=(full.elo_diff+params.home_advantage*full.venue_sign)/400
    clean=exclude_marked_features(history,ratings,params)
    clean_elo=fit_blocks(clean,['elo_effective'],[-1])
    clean_form=fit_blocks(clean,FEATURES,SIGNS)
    form_test=fit_blocks(full,FEATURES,SIGNS)
    form_rows=metric_rows(form_test,'form_all_assumed',baseline)+metric_rows(clean_form,'form_exclude_marked',clean_elo)
    pd.DataFrame(form_rows).to_csv(output/'form_sensitivity.csv',index=False)
    clean_form.to_csv(output/'form_exclude_marked_predictions.csv',index=False)
    ablations=additional_ablations(root,full,baseline,output)
    predictions={'elo':baseline};metric_table=[];reliability=[]
    for kind in NAMES:
        print(f'Modelo: {NAMES[kind]}',flush=True)
        cache=output/f'predictions_{kind}.csv'
        if kind!='elo':
            predictions[kind]=pd.read_csv(cache,parse_dates=['date']) if cache.exists() else predictions_for(full,kind)
        predictions[kind].to_csv(cache,index=False)
        rows,bins=model_metrics(predictions[kind],kind,baseline)
        metric_table.extend(rows);reliability.extend(bins)
    metrics=pd.DataFrame(metric_table)
    metrics.to_csv(output/'model_comparison.csv',index=False)
    pd.DataFrame(reliability).to_csv(output/'reliability.csv',index=False)
    blocks=[]
    for kind,pred in predictions.items():
        for start,_ in BLOCKS:
            part=pred[pred.block_start==start]
            for scope,data in [('total',part),('non_friendlies',part[part.competitive]),('friendlies',part[~part.competitive]),
                               ('worldcup',part[part.competition_family.eq('worldcup')])]:
                blocks.append({'model':kind,'scope':scope,'block_start':start,'matches':len(data),
                   'log_loss':float(data.log_loss.mean()) if len(data) else None,
                   'brier':float(data.brier.mean()) if len(data) else None})
    pd.DataFrame(blocks).to_csv(output/'walk_forward_blocks.csv',index=False)
    sensitivities=[]
    for kind in ['poisson','dixon_coles','xgboost_poisson']:
        for policy in ['exclude_marked','non_friendlies','strict_worldcup']:
            print(f'Sensibilidad: {kind}, {policy}',flush=True)
            cache=output/f'sensitivity_{kind}_{policy}.csv'
            if cache.exists():
                pred=pd.read_csv(cache,parse_dates=['date'])
            elif policy=='strict_worldcup':
                keys=history.loc[history.goal_training_eligible,MATCH_KEY]
                pred=predictions[kind].merge(keys,on=MATCH_KEY,validate='one_to_one')
            else:
                pred=predictions_for(clean if policy=='exclude_marked' else full,kind,train_nonfriend=policy=='non_friendlies')
            pred.to_csv(cache,index=False)
            ref=baseline.merge(pred[MATCH_KEY],on=MATCH_KEY,validate='one_to_one')
            rows,_=model_metrics(pred,kind,ref)
            for r in rows:r['policy']=policy
            sensitivities.extend(rows)
    pd.DataFrame(sensitivities).to_csv(output/'goal_sensitivity.csv',index=False)
    candidates=[k for k in NAMES if k not in ('elo','frequency') and passes(metrics[metrics.model==k].to_dict('records'))]
    best=min(candidates,key=lambda k:metrics[(metrics.model==k)&(metrics.scope=='non_friendlies')].log_loss.iloc[0]) if candidates else 'elo'
    eligible=[k for k in candidates if paired_se(predictions[k],predictions[best])[0]<=paired_se(predictions[k],predictions[best])[1]+1e-14]
    order=registered['definition']['complexity_order']
    selected=min(eligible,key=order.index) if eligible else 'elo'
    count_candidates=[k for k in ['poisson','dixon_coles','xgboost_poisson'] if k in candidates]
    # Count outputs remain available even when no count model beats the 1X2 reference.
    count_selected=min(count_candidates or ['poisson','dixon_coles','xgboost_poisson'],
        key=lambda k:metrics[(metrics.model==k)&(metrics.scope=='non_friendlies')].score_nll.iloc[0])
    decision={'selected_1x2':selected,'passing_candidates':candidates,'selected_score_model':count_selected,
              'score_model_beats_elo_criterion':count_selected in candidates,
              'score_selection':'minimum score NLL among passing count candidates, or descriptive-only count candidates',
              'form_main_passes':passes(form_rows[:3]),'form_exclude_marked_passes':passes(form_rows[3:]),
              'secondary_groups_passing':[r['model'] for r in ablations if r.get('passes_criterion') and r['scope']=='non_friendlies'],
              'reserved_results_opened':False}
    save_json(output/'model_decision.json',decision)
    train=full[full.date>='2000-01-01']
    saved=[]
    for kind in NAMES:
        columns=['elo_effective'] if kind in ('elo','ordinal','frequency') else FEATURES
        signs=[-1] if len(columns)==1 else SIGNS
        if kind in ('poisson','dixon_coles','xgboost_poisson'):
            model=GoalModel(kind,signs).fit(train[columns].to_numpy(float),train.x12_home_score,train.x12_away_score)
        else:
            model=ResultModel('logistic' if kind=='elo' else kind,signs).fit(train[columns].to_numpy(float),train.target)
        path=output/f'model_{kind}.joblib'
        joblib.dump({'model':model,'features':columns,'signs':signs,'elo_parameters':asdict(params),
                     'training_cutoff_exclusive':BOUNDARY,'goal_policy':'all_assumed'},path)
        saved.append({'path':path.relative_to(root).as_posix(),'sha256':digest_file(path)})
    frozen=datetime.now(timezone.utc).isoformat()
    manifest={'models_frozen_at_utc':frozen,'protocol_sha256':digest_file(output/'protocol.json'),
              'training_latest_result':str(history.date.max().date()),'reserved_results_opened':False,
              'models':saved,'decision':decision,'selection':selection,'retrospective':True,
              'forecast_cutoff_exclusive':'2026-06-10','training_cutoff_exclusive':BOUNDARY,
              'official_results_loaded_at_utc':None}
    manifest['code_hash_line_endings']='LF normalized'
    manifest['code_sha256']={p.relative_to(root).as_posix():code_digest(p) for p in
                            [Path(__file__),root/'src/football_forecast/selected_models.py',
                             root/'src/football_forecast/selection_review.py',root/'src/football_forecast/elo_calibration.py',
                             root/'src/football_forecast/preparation.py']}
    save_json(output/'freeze_manifest.json',manifest)
    audit=json.loads((root/'data_audit.json').read_text(encoding='utf-8'))
    if 'selection_review_before_joint_search' not in audit:
        audit['selection_review_before_joint_search']={k:audit.pop(k) for k in ['selection','features'] if k in audit}
    audit['selection']=selection
    audit['features']={'goal_window_primary_policy':'all_assumed','admitted_groups':['recent_form_all_assumed'],
                       'secondary_groups_adopted':[],'form_sensitivity':decision,
                       'market_excluded':'no dated national-team membership before 2023',
                       'ranking_2026_available':False,'ranking_used_in_final_models':False}
    audit.update(models_frozen_at_utc=frozen,official_results_loaded_at_utc=None,reserved_results_opened=False,
                 xgboost_executed=True,latest_result_admitted=str(history.date.max().date()),
                 active_workflow='reports/models_selected',model_selection=manifest,
                 pre2023_history_sha256=digest_file(source),
                 goals_primary={'policy':'all_assumed','matches':len(history),'shootouts':int(history.shootout_record.sum()),
                    'proven_extra_time':int(history.proven_extra_time_goals.gt(0).sum()),'union_flagged':int(flagged(history).sum()),
                    'flagged_fraction':float(flagged(history).mean()),'strict_independent_catalogue':int(history.goal_training_eligible.sum()),
                    'unknown_timing_matches':int(history.x12_uncertain_timing.sum())})
    write_documents(root,output,metrics,selection,decision,audit,pd.DataFrame(form_rows))
    audit['training_model_rows']=len(train)
    audit['models_git_tag']='models-selected'
    audit['artifacts_models_selected']={p.relative_to(root).as_posix():digest_file(p) for p in output.iterdir() if p.is_file() and p.name!='data_audit.json'}
    audit['final_document_sha256']={p.relative_to(root).as_posix():digest_file(p) for p in
                                  [root/'README.md',root/'RESULTADOS.md',root/'docs/DECISIONES_DE_DISEÑO.md']}
    save_json(root/'data_audit.json',audit)
    save_json(output/'data_audit.json',audit)
    print(json.dumps({'selection':selection,'models':decision},ensure_ascii=False),flush=True)
    return audit


def write_documents(root,output,metrics,selection,decision,audit,form_rows):
    nf=metrics[metrics.scope=='non_friendlies'].copy()
    nf['model']=nf.model.map(NAMES)
    fields=['model','matches','log_loss','log_loss_ci','brier','paired_log_loss_difference','paired_log_loss_ci','blocks_improving','score_nll']
    labels={'model':'Modelo','matches':'Partidos','log_loss':'Log loss','log_loss_ci':'IC log loss',
            'brier':'Brier','paired_log_loss_difference':'Diferencia frente a Elo','paired_log_loss_ci':'IC de diferencia',
            'blocks_improving':'Bloques con mejora','score_nll':'NLL marcador'}
    compact=metrics[['model','scope','matches','log_loss','brier','accuracy','ece_0','ece_1','ece_2','actual_draw_rate','predicted_draw_rate']].copy()
    compact['model']=compact.model.map(NAMES)
    compact['scope']=compact.scope.map({'total':'Total','non_friendlies':'No amistosos','friendlies':'Amistosos','worldcup':'Mundiales'})
    compact.columns=['Modelo','Estrato','Partidos','Log loss','Brier','Acierto','ECE victoria','ECE empate','ECE derrota','Empates reales','Empates previstos']
    grid=pd.read_csv(output/'elo_joint_grid.csv')
    gridcols=['home_advantage','inactivity_rate','friendly_k','nations_k','continental_k','worldcup_k','margin_strength','log_loss','excess_vs_minimum','paired_standard_error','within_one_se','selected']
    grid=grid[gridcols]
    grid.columns=['Sede','Inactividad','K amistoso','K Nations','K continental','K Mundial','Gamma','Log loss','Exceso al mínimo','Error estándar pareado','Dentro de 1 EE','Elegida']
    flags=audit['goals_primary']
    form_rows=form_rows.copy()
    form_rows['model']=form_rows.model.map({'form_all_assumed':'Forma con duración supuesta',
                                           'form_exclude_marked':'Forma sin partidos marcados'})
    form_rows['scope']=form_rows.scope.map({'total':'Total','non_friendlies':'No amistosos','friendlies':'Amistosos'})
    sensitivities=pd.read_csv(output/'goal_sensitivity.csv')
    sensitivities=sensitivities[sensitivities.scope.eq('non_friendlies')].copy()
    sensitivities['model']=sensitivities.model.map(NAMES)
    sensitivities['policy']=sensitivities.policy.map({'exclude_marked':'Sin partidos marcados',
              'non_friendlies':'Entrenamiento no amistoso','strict_worldcup':'Validación Mundial estricta'})
    sensitivity_columns=['model','policy','matches','log_loss','brier','score_nll','score_nll_ci']
    sensitivity_labels={'model':'Modelo','policy':'Política','matches':'Partidos','log_loss':'Log loss',
                        'brier':'Brier','score_nll':'NLL marcador','score_nll_ci':'IC NLL marcador'}
    for table in [nf,form_rows,sensitivities]:
        for column in table.columns:
            if column.endswith('_ci'):
                def display_interval(value):
                    if isinstance(value,str):value=json.loads(value)
                    if isinstance(value,(list,tuple,np.ndarray)):
                        return f'[{value[0]:.6f}; {value[1]:.6f}]'
                    return value
                table[column]=table[column].map(display_interval)
    form_labels={'model':'Modelo','scope':'Estrato','matches':'Partidos','log_loss':'Log loss',
                 'paired_log_loss_difference':'Diferencia frente a Elo','paired_log_loss_ci':'IC de diferencia',
                 'paired_brier_difference':'Diferencia Brier','blocks_improving':'Bloques con mejora'}
    decomposition=pd.read_csv(root/'reports/selection_review/archived_bias_decomposition.csv')
    decomposition['scope']=decomposition.scope.map({'non_friendlies':'No amistosos','friendlies':'Amistosos'})
    decomposition=decomposition.rename(columns={'scope':'Estrato','matches':'Partidos','fraction':'Participación',
         'elo_log_loss':'Log loss Elo','candidate_log_loss':'Log loss combinación sesgada',
         'mean_improvement':'Mejora media','contribution_to_pooled_improvement':'Contribución agregada'})
    report=f'''# Resultados del estudio

Construyo este estudio retrospectivo con el torneo ya jugado. No lo presento como un pronóstico publicado antes del Mundial. El corte deportivo final es exclusivo, 2026-06-10; todos los resultados usados aquí son anteriores a 2023-01-01. Mantengo 2023–corte cerrado y la evaluación del Mundial pendiente.

## Diseño y aproximación de duración

Los conjuntos de evaluación se definen sin depender del resultado. Admito los {flags['matches']:,} registros válidos tanto para 1X2 como para goles: uso 90 minutos reconstruidos cuando hay evidencia y el marcador final como aproximación cuando falta. La regla es igual para 0–0 y para cualquier otro marcador. Marco {flags['shootouts']} tandas y {flags['proven_extra_time']} partidos con goles de prórroga probados; su unión es {flags['union_flagged']} ({100*flags['flagged_fraction']:.2f}%). Esta marca identifica riesgo conocido, no certifica la duración de los demás partidos. Cuando verifico la prórroga, uso el marcador reconstruido. No convierto una tanda automáticamente en empate.

El catálogo estricto tiene {flags['strict_independent_catalogue']} Mundiales, con cero partidos en los bloques 2016 y 2020. Lo utilizo para validar la aproximación; no para entrenar un modelo general de goles. Para los modelos ajustados uso resultados desde 2000; el estado Elo y las variables de forma incorporan el historial anterior a cada partido. Las variables de todos los partidos del mismo día se calculan antes de actualizar sus resultados.

No dispongo de amistosos con duración verificada de forma independiente antes de 2023. Por eso la proporción de goles posteriores al minuto 90 en ese subconjunto no puede estimarse: no la informo como 0%. Es una limitación pendiente de los archivos de eventos, no una razón para seleccionar solo empates.

## Selección conjunta de Elo

Registro los criterios en reports/models_selected/protocol.json antes de ejecutar. Comparo 32 combinaciones en cuatro bloques temporales. Aplicando un error estándar pareado y el orden de simplicidad previamente escrito, elijo sede de {selection['parameters']['home_advantage']} puntos, regresión de {selection['parameters']['inactivity_rate']} y gamma de {selection['parameters']['margin_strength']}; los pesos K figuran en la tabla. La fila elegida y el mínimo están registrados en selected_elo.json. Inicializo en 1500 y mantengo un plazo de inactividad de 730 días. La regresión de 0.1 de la configuración de referencia procedía de su definición, no de una selección aislada por datos.

{markdown_table(grid,precision=6)}

La sensibilidad a las configuraciones que cambian una sola coordenada está en elo_neighbors.csv, con intervalos pareados por trimestres. Elegir el mínimo de esta búsqueda no demuestra una mejora fuera de estos bloques.

## Forma y variables complementarias

Admito la forma con duración supuesta en todo el historial por la decisión explícita del diseño. Repito su comprobación con el Elo elegido y omitiendo tandas/prórrogas marcadas de la historia de forma, del entrenamiento y de la evaluación; conservo esos partidos para actualizar Elo.

{markdown_table(form_rows[['model','scope','matches','log_loss','paired_log_loss_difference','paired_log_loss_ci','paired_brier_difference','blocks_improving']].rename(columns=form_labels),precision=6)}

El criterio se cumple en el historial principal: **{decision['form_main_passes']}**; al excluir marcados: **{decision['form_exclude_marked_passes']}**. Reporto las ablaciones secundarias en secondary_ablations.csv. No incorporo silenciosamente una variable adicional. El ranking semestral solo se usa con disponibilidad posterior al semestre y antigüedad máxima de 90 días; no tengo ranking vigente de 2026. Mercado queda fuera por falta de pertenencia jugador–selección fechada antes de 2023. Altitud, descanso y competición se conservan como diagnósticos de ablación.

## Modelos y selección

La referencia principal es Solo Elo con sede fija. Todos los candidatos comparten partidos y bloques. La logística usa Elo y las diferencias de goles, forma y fuerza de oponentes admitidas. La regresión ordinal utiliza dos umbrales simétricos sobre la diferencia efectiva de Elo. XGBoost usa una configuración pequeña fijada antes de ejecutar, sin ajustar parámetros con resultados del bloque evaluado.

Poisson, Dixon-Coles y XGBoost Poisson comparten una regresión orientada para las dos selecciones; su distribución de marcadores genera también el 1X2. Dixon-Coles incorpora covariables Elo/forma y una corrección conjunta de marcadores bajos; no es una estimación independiente de ataque/defensa para cada selección. Limito tasas a [exp(-6), 12] y la corrección a celdas positivas por partido; reporto activaciones en los archivos de predicción. No calibro el 1X2 de un modelo de goles por separado de sus marcadores. Reporto calibración nativa con ECE y tablas de fiabilidad, sin atribuirle una calibración posterior que no se ejecutó.

Un candidato se admite si, en no amistosos, su diferencia pareada de log loss tiene IC superior menor que cero, Brier no empeora y mejora en al menos tres bloques. Entre candidatos admisibles dentro de un error estándar del mejor, elijo el de menor complejidad según el orden registrado. El modelo seleccionado para 1X2 es **{NAMES[decision['selected_1x2']]}**. El modelo de marcadores es **{NAMES[decision['selected_score_model']]}**, con selección por NLL de marcador; cumple el criterio frente a Elo: **{decision['score_model_beats_elo_criterion']}**. Esta selección se debe confirmar en el periodo reservado.

{markdown_table(nf[fields].rename(columns=labels).fillna('No aplica'),precision=6)}

## Estratos y calibración

Brier es la suma multiclase, sin dividir. ECE utiliza diez intervalos de anchura fija por clase. Los intervalos absolutos y pareados de log loss, Brier y NLL de marcador se remuestrean por trimestres completos, con 400 réplicas y semilla fija; no tratan partidos como observaciones independientes. Pueden ser optimistas porque estos mismos bloques se usan para seleccionar; necesito el periodo reservado para confirmar. Fiabilidad por intervalo y resultados por bloque están en reliability.csv y walk_forward_blocks.csv.

{markdown_table(compact,precision=5)}

## Sensibilidades de goles y cobertura

goal_sensitivity.csv contiene: exclusión de los partidos marcados, entrenamiento solo con no amistosos y validación sobre Mundiales estrictos. Las comparaciones de cada sensibilidad usan las mismas claves para su referencia. La comprobación estricta tiene únicamente los Mundiales de 2018 y 2022 en estos bloques: no extrapolo su cobertura a amistosos o a todas las confederaciones. Las ausencias de Mundiales en los otros bloques figuran como N=0, no como rendimiento cero.

{markdown_table(sensitivities[sensitivity_columns].rename(columns=sensitivity_labels),precision=6)}

Conservo las proporciones de 0–0, empates y goles por conjunto y bloque en reports/selection_review/selection_bias_diagnostics.csv. La admisión completa conserva la composición del historial; las diferencias restantes se explican por reconstrucción de etiquetas o por el dominio Mundial. Registro la participación por confederación, competición y año de cada sensibilidad en goal_population_coverage.csv, comparada con el historial desde 2000. Las confederaciones son metadatos actuales usados solo como diagnóstico, no una validación de afiliación histórica. El entrenamiento principal de goles ya no selecciona por cobertura de eventos: comparte exactamente la población del 1X2. No uso ponderaciones actuales de confederación como variables históricas.

## Cuánto explicaba el artefacto

El diagnóstico previo permitía 0–0 sin eventos y excluía otros marcadores en la misma situación. De su mejora agregada de 0.098356, 0.064749 procedía de 197 amistosos, todos 0–0. Conservo esta descomposición para auditar el sesgo, no como resultado vigente.

{markdown_table(decomposition,precision=6)}

## Congelado y límites

Congelo modelos entrenados solo hasta 2022, parámetros y protocolo en {audit['models_frozen_at_utc']}; guardo SHA256 en freeze_manifest.json y data_audit.json. La etiqueta models-selected identifica este estado. No cargo resultados desde 2023 ni resultados oficiales del Mundial en esta fase; no existe todavía una comparación honesta en los 72 partidos. La referencia original guardada continúa intacta y su evaluación se aplaza.

Esta selección y sus intervalos no sustituyen una prueba independiente. La duración supuesta sigue siendo una limitación de medición; excluir los casos conocidos no descarta prórrogas desconocidas. Tampoco tengo composición histórica suficiente para incorporar valor de mercado ni ranking vigente de 2026. No simulo cuadros de torneo ni invento métricas del periodo reservado.
'''
    (root/'RESULTADOS.md').write_text(report,encoding='utf-8')
    (output/'RESULTADOS.md').write_text(report,encoding='utf-8')
    readme=f'''# International Football Probabilities

Construyo un estudio retrospectivo de probabilidades de fútbol para mi portafolio: victoria, empate, derrota y distribución de marcadores a 90 minutos. El torneo ya estaba jugado al construir el estudio; no lo presento como un pronóstico publicado previamente.

El corte deportivo final es exclusivo, **2026-06-10**. Selecciono y congelo modelos usando únicamente resultados anteriores a **2023-01-01**. Mantengo 2023–corte y los resultados oficiales del Mundial reservados para la evaluación posterior.

## Diseño

Los conjuntos de evaluación se definen sin depender del resultado. Admito todos los registros válidos para 1X2 y goles, reconstruyendo 90 minutos donde hay evidencia y usando el final registrado como aproximación declarada donde falta. No convierto una tanda automáticamente en empate. El catálogo estricto de Mundiales sirve como validación de esta aproximación, con sensibilidades sin partidos marcados y solo no amistosos.

Elo utiliza todas las competiciones, actualización por fecha, pesos por competición, margen de goles y ventaja real de sede. Comparo 32 configuraciones conjuntas y elijo por log loss de no amistosos con una regla pareada de un error estándar. La forma reciente procede solo de partidos anteriores. La logística con forma debe cumplir el criterio frente a Elo en esta búsqueda; no doy por válida una combinación de contexto por una evaluación sesgada.

Comparo frecuencias, Solo Elo con sede fija, logística con forma, regresión ordinal, XGBoost 1X2, Poisson, Dixon-Coles con covariables y XGBoost Poisson. Los modelos de goles producen el marcador y el 1X2 desde la misma distribución. Pruebo simetría al intercambiar equipos con tolerancia 1e-9.

Elijo **{NAMES[decision['selected_1x2']]}** para 1X2 y **{NAMES[decision['selected_score_model']]}** para marcadores. Esta es una selección anterior a 2023 que necesita confirmación independiente. [RESULTADOS.md](RESULTADOS.md) explica métricas, intervalos, sensibilidades y límites.

## Validación y reproducción

Uso bloques 2016–2017, 2018–2019, 2020–2021 y 2022, con entrenamiento anterior a cada bloque desde 2000. Reporto total, amistosos, no amistosos y Mundiales, log loss, Brier multiclase sin dividir, acierto, ECE por clase, empates previstos/reales y NLL de marcador. Remuestreo trimestres completos para los intervalos pareados. Un modelo complejo debe superar la referencia bajo el criterio escrito previamente; el periodo reservado sigue sin abrir.

```powershell
python select_models.py
python tools/verify_models_selected.py
```

No descargo datos ni simulo torneos. Uso dos hilos por defecto. Si el congelado ya existe, select_models.py verifica sus hashes sin sustituirlo. Para reproducir la selección desde cero necesito una copia de trabajo sin el directorio de congelado, las fuentes locales con los SHA256 registrados y la preparación previa. Los CSV grandes están excluidos de Git; si falta el historial preparado, lo reconstruyo con el corte anterior a 2023 y compruebo su hash. El protocolo queda guardado antes de ejecutar métricas. Los comandos históricos fix_selection_bias.py corresponden a la etiqueta selection-bias-fixed y no generan el informe vigente.

## Fuentes y límites

Uso archivos locales de martj42, Fjelstul, ranking FIFA semestral, GeoNames, Transfermarkt, StatsBomb, Openfootball y fixtures suministrados. Mantengo las fuentes separadas y en data/raw/. El ranking repetido es una fotografía excluida; el ranking semestral solo es una ablación con rezago conservador y caducidad de 90 días. No extrapolo ranking a 2026. Valor de mercado queda fuera por falta de pertenencia a selecciones fechada antes de 2023; no uso valor/club/nacionalidad actuales como históricos. StatsBomb queda para validación opcional. Openfootball y resultados de 2026 permanecen reservados.

## Trazabilidad

[data_audit.json](data_audit.json), [protocolo previo](reports/models_selected/protocol.json), [congelado](reports/models_selected/freeze_manifest.json) y [decisiones de diseño](docs/DECISIONES_DE_DISEÑO.md) registran fechas, hashes y reglas. Las etiquetas data-prepared, selection-bias-fixed y models-selected identifican preparación, definición de conjuntos y modelos congelados. Conservo los informes históricos como diagnóstico; la narrativa vigente está en RESULTADOS.md y reports/models_selected/.

Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.
'''
    (root/'README.md').write_text(readme,encoding='utf-8')
    design=f'''# Decisiones de diseño

Construyo un estudio retrospectivo con el torneo ya jugado. Distingo el corte deportivo exclusivo 2026-06-10 de las fechas reales de construcción, selección, congelado y carga de resultados. No lo presento como pronóstico publicado antes del Mundial.

## Conjuntos sin selección por marcador

Los conjuntos de evaluación se definen sin depender del resultado. Esta es una comprobación estándar: reviso 0–0 y empates por población, dominio y bloque. Una tanda no prueba empate a 90 minutos; las filas idénticas de goleadores no se eliminan automáticamente. Mantengo entidades históricas distintas, incluido Czechoslovakia respecto a Czech Republic.

Admito todo el historial válido para goles y 1X2 bajo duración supuesta donde falta evidencia. Reconstruyo 90 minutos cuando se puede verificar. Marco tandas y prórrogas probadas. El catálogo independiente Fjelstul de Mundiales valida la aproximación; no es el entrenamiento principal. Repito con exclusión de marcados y con entrenamiento solo no amistoso. La exclusión también retira esos partidos de la historia de forma, pero Elo conserva todo el historial. No uso la tasa de empates para decidir admisiones.

## Selección temporal y simplicidad

Resultados desde 2023 están reservados. Calculo variables antes de actualizar todos los resultados de una fecha. Elo tiene inicialización 1500, plazo de inactividad 730 días y una búsqueda conjunta de 32 combinaciones de sede, regresión, pesos K y margen de goles. La regresión 0.1 de la referencia era un parámetro fijado, no una elección de datos de la búsqueda aislada.

El protocolo escrito previamente está en reports/models_selected/protocol.json. Selecciono por log loss de no amistosos en los cuatro bloques. Dentro de un error estándar pareado del mínimo prefiero, por orden, ausencia de regresión, pesos de referencia, gamma menor y ventaja de sede menor. Para modelos y variables exijo IC superior de diferencia de log loss <0, Brier sin empeorar y mejora en tres bloques; entre candidatos admitidos cercanos uso el orden de complejidad escrito. Los intervalos usan trimestres completos, 400 réplicas, semilla fija. Estos bloques de selección necesitan confirmación independiente.

## Variables y modelos

La forma con duración supuesta está admitida explícitamente y se verifica al excluir marcados. No incorporo automáticamente grupos secundarios; guardo ablaciones de sede adicional, descanso, competición, altitud y ranking. El ranking está disponible después del semestre y caduca a 90 días, sin extrapolación a 2026. Mercado queda fuera: no tengo pertenencia fechada a selecciones anterior a 2023. No uso tablas actuales players/national_teams como históricos. GeoNames aporta solo altitud estática identificable; no invento viajes ni altitud de entrenamiento. No pondero por afiliaciones históricas supuestas a partir de confederaciones actuales.

Todos los clasificadores reconcilian ambos órdenes. Los modelos de goles comparten una regresión orientada de tasas y generan victoria/empate/derrota desde su distribución conjunta. Dixon-Coles usa covariables y corrección de marcadores bajos; no efectos libres por selección. Tasas y corrección tienen límites explícitos de validez. No calibro por separado el 1X2 del marcador: reporto ECE nativo por clase y fiabilidad. XGBoost tiene configuración pequeña fija, sin parada temprana usando el bloque evaluado.

## Congelado

Congelo los modelos con entrenamiento anterior a 2023 en {audit['models_frozen_at_utc']}, con hashes en freeze_manifest.json. La etiqueta models-selected precede a abrir 2023–corte. El congelado de predicciones de los 72 partidos y la carga de resultados oficiales corresponden a fases posteriores; sus fechas no se inventan. El modelo guardado original permanece intacto. Mantengo archivos fuente en data/raw/ y reportes históricos como diagnósticos separados.
'''
    (root/'docs/DECISIONES_DE_DISEÑO.md').write_text(design,encoding='utf-8')
