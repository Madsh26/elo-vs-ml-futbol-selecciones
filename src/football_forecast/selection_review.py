"""Outcome-independent cohorts, pre-2023 Elo selection and honest ablations."""
from pathlib import Path
from collections import defaultdict,deque
from dataclasses import asdict
from datetime import datetime,timezone
import json
import numpy as np
import pandas as pd
from .ingestion import load_study_data,digest_file,MATCH_KEY,before_cutoff_csv
from .elo_calibration import (EloParameters,CalibratedElo,parameter_grid,BLOCKS,
                             symmetric_predictions,per_match_metrics,block_interval,
                             backward_rank_join,semester_rankings)
from .preparation import evidence_features,markdown_table
from .context_features import venue_sign,venue_altitude,altitude_lookup,coverage_weights

BOUNDARY='2023-01-01'
POLICIES=['strict','friendly_assumed','all_assumed']
POLICY_NAMES={'strict':'Catálogo Fjelstul con duración verificada',
              'friendly_assumed':'Catálogo verificado y todos los amistosos de duración supuesta',
              'all_assumed':'Todos los partidos con duración supuesta donde falta verificación',
              'all_recorded':'Todos los marcadores registrados, sensibilidad sin reconstrucción'}
CONFIG_NAMES=['Pesos de referencia','Pesos menores','Pesos mayores','Sin multiplicador de goles',
              'Multiplicador de goles fuerte','Sede sin ventaja fija','Sede con ventaja fija mayor',
              'Sin regresión por inactividad','Regresión por inactividad mayor','Regresión tras un año',
              'Inicialización común 1400','Inicialización común 1600','Sin margen, sede ni regresión']
GROUPS={
    'recent_form':(['gf_diff','ga_diff','form_diff','opponent_diff','goal_coverage_sum'],[-1,-1,-1,-1,1]),
    'rest':(['rest_diff','rest_missing'],[-1,1]),
    'competition':(['competitive','worldcup','neutral'],[1,1,1]),
    'altitude':(['altitude_scaled','venue_altitude_missing'],[1,1]),
    'fifa_rank':(['rank_diff','ranking_missing'],[-1,1]),
    'fifa_rank_points':(['rank_diff','points_diff','ranking_missing','points_missing'],[-1,-1,1,1]),
}
LABELS={'elo':'Solo Elo con ventaja de sede fija','elo_venue':'Elo + sede',
        'recent_form':'Goles y forma reciente: catálogo verificado','rest':'Descanso observado',
        'competition':'Contexto de competición','altitude':'Altitud de sede',
        'fifa_rank':'Puesto FIFA','fifa_rank_points':'Puesto y puntos FIFA',
        'coverage_weights':'Pesos de cobertura: sensibilidad administrativa',
        'form_friendly_assumed':'Forma con todos los amistosos de duración supuesta',
        'form_all_assumed':'Forma con duración supuesta en todo el historial',
        'joint_admitted':'Grupos admitidos conjuntamente',
        'recorded_target':'Elo + sede con etiqueta final registrada'}

def goal_policy_frame(history,policy):
    """Membership is metadata-only, not determined by target score values."""
    frame=history.copy()
    if policy=='strict': eligible=frame.goal_training_eligible
    elif policy=='friendly_assumed': eligible=frame.goal_training_eligible|frame.tournament.eq('Friendly')
    elif policy in ('all_assumed','all_recorded'): eligible=pd.Series(True,index=frame.index)
    else: raise ValueError(f'Unknown goal policy: {policy}')
    frame['goal_training_eligible']=eligible
    if policy!='strict':
        h,a=('recorded_home_score','recorded_away_score') if policy=='all_recorded' else ('x12_home_score','x12_away_score')
        frame.loc[eligible,'home_score_90']=frame.loc[eligible,h]
        frame.loc[eligible,'away_score_90']=frame.loc[eligible,a]
    frame.loc[~eligible,['home_score_90','away_score_90']]=np.nan
    frame['goal_window_policy']=policy
    return frame

def outcome_frame(history,policy='reconstructed_else_recorded'):
    out=history[history.x12_eligible].copy()
    h,a=('recorded_home_score','recorded_away_score') if policy=='recorded' else ('x12_home_score','x12_away_score')
    out['target']=np.where(out[h]>out[a],0,np.where(out[h]==out[a],1,2))
    return out

def build_batches(history):
    cols=['date','home_team','away_team','country','neutral','elo_home_score','elo_away_score','competition_family']
    return [(date,list(day.itertuples(index=False))) for date,day in history[cols].groupby('date',sort=True)]

def elo_from_batches(batches,params):
    state=CalibratedElo(params)
    records=[]
    for date,rows in batches:
        state.prepare_day([t for r in rows for t in (r.home_team,r.away_team)],date)
        for r in rows:
            records.append((date,r.home_team,r.away_team,state.ratings[r.home_team],state.ratings[r.away_team]))
        state.update_day(rows)
    out=pd.DataFrame(records,columns=MATCH_KEY+['elo_home','elo_away'])
    out['elo_diff']=out.elo_home-out.elo_away
    return out

def fit_blocks(frame,columns,signs,history=None,mappings=None):
    parts=[]
    if (frame.date>=pd.Timestamp(BOUNDARY)).any(): raise ValueError('Reserved results in model input')
    for start,end in BLOCKS:
        train=frame[(frame.date>='2000-01-01')&(frame.date<start)]
        test=frame[(frame.date>=start)&(frame.date<end)]
        weights=None
        if mappings is not None:
            complete=history[(history.date>='2000-01-01')&(history.date<start)]
            weights=coverage_weights(train,complete,mappings,start).to_numpy()
        p=symmetric_predictions(train,test,columns,signs,weights)
        loss,brier=per_match_metrics(test.target.to_numpy(dtype=int),p)
        pred=test[MATCH_KEY+['competitive','competition_family','target','x12_uncertain_timing']].reset_index(drop=True)
        pred['block_start']=start
        pred[['p_home_win','p_draw','p_away_win']]=p
        pred['log_loss']=loss;pred['brier']=brier
        parts.append(pred)
    return pd.concat(parts,ignore_index=True)

def scopes(prediction):
    return {'total':prediction,'non_friendlies':prediction[prediction.competitive],
            'friendlies':prediction[~prediction.competitive]}

def metric_rows(prediction,name,reference=None):
    rows=[]
    for scope,pred in scopes(prediction).items():
        if not len(pred): continue
        row={'model':name,'scope':scope,'matches':len(pred),'log_loss':float(pred.log_loss.mean()),
             'brier':float(pred.brier.mean()),'log_loss_ci':block_interval(pred.date,pred.log_loss),
             'brier_ci':block_interval(pred.date,pred.brier),
             'actual_draw_rate':float(pred.target.eq(1).mean()),'predicted_draw_rate':float(pred.p_draw.mean())}
        if reference is not None:
            ref=scopes(reference)[scope]
            if not pred[MATCH_KEY].reset_index(drop=True).equals(ref[MATCH_KEY].reset_index(drop=True)):
                raise ValueError('Paired comparison keys differ')
            delta=pred.log_loss.to_numpy()-ref.log_loss.to_numpy()
            db=pred.brier.to_numpy()-ref.brier.to_numpy()
            improving=pd.DataFrame({'block':pred.block_start.to_numpy(),'delta':delta}).groupby('block').delta.mean()
            row.update(paired_log_loss_difference=float(delta.mean()),paired_log_loss_ci=block_interval(pred.date,delta),
                       paired_brier_difference=float(db.mean()),paired_brier_ci=block_interval(pred.date,db),
                       blocks_improving=int((improving<0).sum()))
        rows.append(row)
    return rows

def passes(rows):
    r=next(x for x in rows if x['scope']=='non_friendlies')
    return bool(r['paired_log_loss_ci'][1]<0 and r['paired_brier_difference']<=0 and r['blocks_improving']>=3)

def selection_rows(history,output,previous):
    batches=build_batches(history)
    baseline=outcome_frame(history)
    rows=[];predictions={};frames={}
    for index,params in enumerate(parameter_grid()):
        print(f'Calibracion sin seleccion por marcador: {CONFIG_NAMES[index]}',flush=True)
        # Uniform shifts are analytically invariant and are covered by tests.
        if index in (10,11):
            pred=predictions[0].copy();frame=frames[0].copy()
        else:
            ratings=elo_from_batches(batches,params)
            frame=baseline.merge(ratings,on=MATCH_KEY,validate='one_to_one')
            frame['venue_sign']=venue_sign(frame)
            frame['elo_effective']=(frame.elo_diff+params.home_advantage*frame.venue_sign)/400
            pred=fit_blocks(frame,['elo_effective'],[-1])
        predictions[index]=pred;frames[index]=frame
        entries=metric_rows(pred,CONFIG_NAMES[index])
        for entry in entries: entry.update(asdict(params))
        rows.extend(entries)
    table=pd.DataFrame(rows)
    table.to_csv(output/'elo_parameter_comparison.csv',index=False)
    nonfriendly=table[table.scope=='non_friendlies'].copy()
    nonfriendly['grid_order']=[CONFIG_NAMES.index(n) for n in nonfriendly.model]
    best=int(nonfriendly.sort_values(['log_loss','brier','grid_order']).iloc[0].grid_order)
    if best in (10,11): best=0
    selected=parameter_grid()[best]
    pred=predictions[best];frame=frames[best]
    pred.to_csv(output/'elo_walk_forward_predictions.csv',index=False)
    old=previous.get('parameters',{})
    selection={'parameters':asdict(selected),'configuration_name':CONFIG_NAMES[best],
               'selection_completed_at_utc':datetime.now(timezone.utc).isoformat(),
               'previous_parameters':old,'changed_parameters':{k:{'diagnostic_with_biased_cohort':old.get(k),'current':v}
                                                               for k,v in asdict(selected).items() if old.get(k)!=v},
               'selection_scope':'non_friendlies','training_scope':'all valid 1X2, friendlies with declared assumed duration',
               'reserved_period_opened':False,'canonical_common_initial':1500,
               'uniform_initial_shift_candidates_reuse_reference_metrics':True}
    (output/'selected_elo.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    return frame,pred,selected,selection

def form_features(history,ratings,policy):
    usable=goal_policy_frame(history,policy)
    # Empty future frame keeps all calculations strictly in the past.
    full,_,_,_=evidence_features(usable,pd.DataFrame())
    full=full.drop(columns=['elo_home','elo_away','elo_diff'])
    full=full.merge(ratings[MATCH_KEY+['elo_home','elo_away','elo_diff']],on=MATCH_KEY,validate='one_to_one')
    opponents=defaultdict(lambda:deque(maxlen=10))
    home_opponent=np.full(len(full),1500.,dtype=float)
    away_opponent=np.full(len(full),1500.,dtype=float)
    for _,day in full[['date','home_team','away_team','elo_home','elo_away']].groupby('date',sort=True):
        additions=[]
        for r in day.itertuples():
            for t,side,v in [(r.home_team,'home',r.elo_away),(r.away_team,'away',r.elo_home)]:
                destination=home_opponent if side=='home' else away_opponent
                destination[r.Index]=np.mean(opponents[t]) if opponents[t] else 1500.
                additions.append((t,v))
        for t,v in additions: opponents[t].append(v)
    full['opponent_elo_home']=home_opponent
    full['opponent_elo_away']=away_opponent
    full['gf_diff']=full.gf5_home-full.gf5_away
    full['ga_diff']=full.ga5_home-full.ga5_away
    full['form_diff']=full.form5_home-full.form5_away
    full['opponent_diff']=(full.opponent_elo_home-full.opponent_elo_away)/400
    full['goal_coverage_sum']=full.goals_90_coverage5_home+full.goals_90_coverage5_away
    full['rest_diff']=(np.log1p(full.days_rest_home)-np.log1p(full.days_rest_away))/5
    full['rest_missing']=full.days_rest_home.isna()|full.days_rest_away.isna()
    full['target']=full.x12_target.astype(int)
    full['neutral']=full.neutral.astype(bool)
    full['venue_sign']=venue_sign(full)
    full['competitive']=full.tournament.ne('Friendly')
    return full

def feature_comparison(root,output,history,frame,elo_prediction,params):
    full=form_features(history,frame,'strict')
    full['elo_effective']=(full.elo_diff+params.home_advantage*full.venue_sign)/400
    full=backward_rank_join(full,semester_rankings(root/'data/raw/fifa_rank_semesters.zip'))
    full['rank_diff']=(full.fifa_rank_away-full.fifa_rank_home).fillna(0)/200
    full['ranking_missing']=full.fifa_rank_home.isna()|full.fifa_rank_away.isna()
    full['points_diff']=((full.fifa_points_home-full.fifa_points_away)/(full.fifa_points_home+full.fifa_points_away)).replace([np.inf,-np.inf],np.nan)
    full['points_missing']=full.points_diff.isna()
    full=venue_altitude(full,altitude_lookup(root/'data/raw/geonames_cities15000.zip'))
    full['altitude_scaled']=full.venue_altitude_m/1000
    full=full.drop(columns=['host_home','host_away'],errors='ignore')
    full.to_csv(output/'historical_features.csv',index=False)
    basecols=['elo_effective','venue_sign'];basesigns=[-1,-1]
    reference=fit_blocks(full,basecols,basesigns)
    venue_effect=metric_rows(reference,'elo_venue',elo_prediction)
    (output/'additional_venue_coefficient.json').write_text(json.dumps({'metrics':venue_effect,
         'passes_criterion_against_fixed_venue_elo':passes(venue_effect)},indent=2),encoding='utf-8')
    rows=metric_rows(elo_prediction,'elo',reference)+metric_rows(reference,'elo_venue',reference)
    predictions={'elo':elo_prediction,'elo_venue':reference};admitted=[]
    for name,(columns,signs) in GROUPS.items():
        print(f'Ablacion con referencia Elo + sede: {LABELS[name]}',flush=True)
        pred=fit_blocks(full,basecols+columns,basesigns+signs)
        entries=metric_rows(pred,name,reference)
        decision=passes(entries)
        for r in entries:r['passes_primary_criterion']=decision
        rows.extend(entries);predictions[name]=pred
        if decision:admitted.append(name)
    for policy,name in [('friendly_assumed','form_friendly_assumed'),('all_assumed','form_all_assumed')]:
        sensitivity=form_features(history,frame,policy)
        sensitivity['elo_effective']=(sensitivity.elo_diff+params.home_advantage*sensitivity.venue_sign)/400
        cols,signs=GROUPS['recent_form']
        pred=fit_blocks(sensitivity,basecols+cols,basesigns+signs)
        entries=metric_rows(pred,name,reference)
        for r in entries:r['passes_primary_criterion']=passes(entries)
        rows.extend(entries);predictions[name]=pred
        sensitivity.to_csv(output/f'features_{policy}.csv',index=False)
    mappings=pd.read_csv(root/'reports/data_preparation/confederations.csv').set_index('team').confederation.to_dict()
    pred=fit_blocks(full,basecols,basesigns,history,mappings)
    entries=metric_rows(pred,'coverage_weights',reference)
    for r in entries:r.update(passes_primary_criterion=passes(entries),production_allowed=False)
    rows.extend(entries);predictions['coverage_weights']=pred
    recorded=full.copy()
    recorded['target']=np.where(recorded.recorded_home_score>recorded.recorded_away_score,0,
                               np.where(recorded.recorded_home_score==recorded.recorded_away_score,1,2))
    pred=fit_blocks(recorded,basecols,basesigns)
    # Different target semantics: absolute sensitivity, never paired selection.
    rows.extend(metric_rows(pred,'recorded_target'));predictions['recorded_target']=pred
    joint=False
    if admitted:
        columns=basecols+sum([GROUPS[g][0] for g in admitted],[])
        signs=basesigns+sum([GROUPS[g][1] for g in admitted],[])
        pred=fit_blocks(full,columns,signs)
        entries=metric_rows(pred,'joint_admitted',reference)
        joint=passes(entries)
        for r in entries:r['passes_primary_criterion']=joint
        rows.extend(entries);predictions['joint_admitted']=pred
    comparison=pd.DataFrame(rows)
    comparison.to_csv(output/'feature_ablation.csv',index=False)
    pd.concat([p.assign(model=n) for n,p in predictions.items()],ignore_index=True).to_csv(output/'walk_forward_predictions.csv',index=False)
    blocks=pd.concat([p.groupby(['block_start','competitive']).agg(matches=('log_loss','size'),log_loss=('log_loss','mean'),brier=('brier','mean')).reset_index().assign(model=n)
                      for n,p in predictions.items()],ignore_index=True)
    blocks.to_csv(output/'walk_forward_blocks.csv',index=False)
    decision={'groups_passing_against_elo_plus_venue':admitted,'combined_groups_passing':joint,
              'goal_window_primary_policy':'strict','goal_window_sensitivities_not_automatically_adopted':True,
              'coverage_weights_asof_affiliation_verified':False,'coverage_weights_production_allowed':False,
              'selection_scope':'non_friendlies','reserved_period_opened':False,
              'fixed_venue_elo_vs_learned_venue_passes':passes(venue_effect),
              'primary_x12_baseline':'elo_venue' if passes(venue_effect) else 'elo',
              'form_all_assumed_passes_but_not_adopted':passes(metric_rows(predictions['form_all_assumed'],'form_all_assumed',reference))}
    (output/'feature_selection.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    return comparison,decision,full

def bias_diagnostics(history,output,legacy=None):
    frames={'Historial completo':history,'Resultado 1X2: todos':history,
            'Resultado 1X2: no amistosos':history[history.competitive],
            'Resultado 1X2: amistosos':history[~history.competitive]}
    for policy in POLICIES+['all_recorded']:
        g=goal_policy_frame(history,policy)
        frames['Goles: '+POLICY_NAMES[policy]]=g[g.goal_training_eligible]
    if legacy is not None:
        frames['Diagnóstico archivado: excepción de 0–0']=legacy[legacy.goal_training_eligible]
    rows=[]
    for window,start,end in [('Historial anterior a 2023',None,BOUNDARY)]+[(s,s,e) for s,e in BLOCKS]:
        reference=history[(history.date<end)&((history.date>=start) if start else True)]
        rz=(reference.recorded_home_score.eq(0)&reference.recorded_away_score.eq(0)).mean()
        rd=reference.recorded_home_score.eq(reference.recorded_away_score).mean()
        for name,frame in frames.items():
            block=frame[(frame.date<end)&((frame.date>=start) if start else True)]
            if not len(block):
                rows.append({'window':window,'cohort':name,'matches':0,
                    **{col:np.nan for col in ['recorded_zero_zero_rate','recorded_draw_rate','target_zero_zero_rate','target_draw_rate',
                        'mean_recorded_total_goals','mean_target_total_goals','zero_zero_difference_vs_complete','draw_difference_vs_complete']}})
                continue
            zero=float((block.recorded_home_score.eq(0)&block.recorded_away_score.eq(0)).mean())
            draw=float(block.recorded_home_score.eq(block.recorded_away_score).mean())
            if name.startswith('Goles:') or name.startswith('Diagnóstico'):
                h,a='home_score_90','away_score_90'
            elif name=='Historial completo':h,a='recorded_home_score','recorded_away_score'
            else:h,a='x12_home_score','x12_away_score'
            rows.append({'window':window,'cohort':name,'matches':len(block),'recorded_zero_zero_rate':zero,
                         'recorded_draw_rate':draw,'target_zero_zero_rate':float((block[h].eq(0)&block[a].eq(0)).mean()),
                         'target_draw_rate':float(block[h].eq(block[a]).mean()),
                         'mean_recorded_total_goals':float((block.recorded_home_score+block.recorded_away_score).mean()),
                         'mean_target_total_goals':float((block[h]+block[a]).mean()),
                         'zero_zero_difference_vs_complete':zero-float(rz),'draw_difference_vs_complete':draw-float(rd)})
    table=pd.DataFrame(rows)
    table.to_csv(output/'selection_bias_diagnostics.csv',index=False)
    # Same-domain references distinguish selection bias from competition mix.
    domains=[]
    for window,start,end in [('Historial anterior a 2023',None,BOUNDARY)]+[(s,s,e) for s,e in BLOCKS]:
        period=history[(history.date<end)&((history.date>=start) if start else True)]
        for name,mask in [('Amistosos',~period.competitive),('No amistosos',period.competitive),
                          ('Mundiales del historial',period.competition_family.eq('worldcup'))]:
            block=period[mask]
            domains.append({'window':window,'domain':name,'matches':len(block),
                            'zero_zero_rate':float((block.recorded_home_score.eq(0)&block.recorded_away_score.eq(0)).mean()),
                            'draw_rate':float(block.recorded_home_score.eq(block.recorded_away_score).mean())})
    pd.DataFrame(domains).to_csv(output/'domain_references.csv',index=False)
    return table

def legacy_decomposition(root,history,output):
    a=root/'reports/feature_design/feature_ablation_predictions.csv'
    b=root/'reports/feature_design/elo_walk_forward_predictions.csv'
    if not a.exists() or not b.exists():return []
    old=pd.read_csv(a,parse_dates=['date']);old=old[old.group=='joint_accepted_groups']
    ref=pd.read_csv(b,parse_dates=['date'])
    if (old.date>=pd.Timestamp(BOUNDARY)).any() or (ref.date>=pd.Timestamp(BOUNDARY)).any():raise ValueError('Reserved legacy outcomes')
    pair=old.merge(ref,on=MATCH_KEY,suffixes=('_candidate','_elo'),validate='one_to_one').merge(history[MATCH_KEY+['competitive']],on=MATCH_KEY,validate='one_to_one')
    total=len(pair);rows=[]
    for name,mask in [('Amistosos',~pair.competitive),('No amistosos',pair.competitive)]:
        block=pair[mask];gain=block.log_loss_elo-block.log_loss_candidate
        rows.append({'scope':name,'matches':len(block),'fraction':len(block)/total,
                     'elo_log_loss':float(block.log_loss_elo.mean()),'candidate_log_loss':float(block.log_loss_candidate.mean()),
                     'mean_improvement':float(gain.mean()),'contribution_to_pooled_improvement':float(gain.sum()/total)})
    pd.DataFrame(rows).to_csv(output/'archived_bias_decomposition.csv',index=False)
    return rows

def run_review(root='.',output='reports/selection_review'):
    root,output=Path(root),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    protocol={'written_at_utc':started,'document':'docs/PROTOCOLO_CONJUNTOS.md',
              'document_sha256':digest_file(root/'docs/PROTOCOLO_CONJUNTOS.md'),
              'membership_independent_of_target':True,'data_cutoff_exclusive':BOUNDARY,
              'sports_forecast_cutoff_exclusive':'2026-06-10','selection_scope':'non_friendlies',
              'blocks':BLOCKS,'grid':[asdict(p) for p in parameter_grid()],
              'goal_policies':POLICIES,'ablation_groups':GROUPS,
              'baseline':'effective elo difference including fixed venue advantage; comparator effective Elo + separately learned venue coefficient',
              'acceptance':'non-friendlies paired log-loss upper CI <0, Brier not worse, >=3/4 blocks improve',
              'bootstrap':{'blocks':'calendar quarters','replicas':400,'seed':20261012},
              'xgboost_executed':False,'reserved_results_opened':False}
    (output/'selection_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    previous_path=root/'reports/feature_design/selected_elo.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    print('Leyendo exclusivamente resultados anteriores a 2023...',flush=True)
    data=load_study_data(root,BOUNDARY)
    (output/'ingestion_audit.json').write_text(json.dumps(data.audit,indent=2,ensure_ascii=False),encoding='utf-8')
    history=data.history
    history.to_csv(output/'historical_results.csv',index=False)
    legacy=None
    legacy_path=root/'reports/data_preparation/historical_results.csv'
    if legacy_path.exists():
        with legacy_path.open('rb') as stream:legacy=before_cutoff_csv(stream,BOUNDARY)
        legacy['date']=pd.to_datetime(legacy.date)
        legacy['goal_training_eligible']=legacy.goal_training_eligible.str.casefold().eq('true')
        for col in ['recorded_home_score','recorded_away_score','home_score_90','away_score_90']:
            legacy[col]=pd.to_numeric(legacy[col],errors='coerce')
    diagnostics=bias_diagnostics(history,output,legacy)
    decomposition=legacy_decomposition(root,history,output)
    for policy in POLICIES:
        g=goal_policy_frame(history,policy);g[g.goal_training_eligible].to_csv(output/f'goals_{policy}.csv',index=False)
    history[history.independent_goal_catalogue & ~history.goal_training_eligible].to_csv(output/'catalogue_integrity_exclusions.csv',index=False)
    history[history.competition_family.eq('worldcup') & ~history.independent_goal_catalogue][MATCH_KEY].to_csv(output/'catalogue_unmatched_worldcup.csv',index=False)
    frame,elo,params,selection=selection_rows(history,output,previous)
    comparison,decisions,features=feature_comparison(root,output,history,frame,elo,params)
    audit={'correction_started_at_utc':started,'correction_completed_at_utc':datetime.now(timezone.utc).isoformat(),
           'review_git_tag':'selection-bias-fixed',
           'correction_date_local':str(pd.Timestamp(started).tz_convert('America/Bogota').date()),
           'correction_timezone':'America/Bogota',
           'prediction_cutoff_exclusive':'2026-06-10','selection_and_review_cutoff_exclusive':BOUNDARY,
           'latest_result_admitted':str(history.date.max().date()),'history_rows':len(history),
           'strict_goal_rows':int(history.goal_training_eligible.sum()),'result_1x2_rows':len(data.result_history),
           'protocol_sha256':digest_file(output/'selection_protocol.json'),'sources':data.audit['sources'],
           'selection':selection,'features':decisions,'old_improvement_decomposition':decomposition,
           'zero_score_exception_removed':True,'membership_independent_of_target':True,
           'timing_uncertainty':{'1x2_unverified_count':int(history.x12_uncertain_timing.sum()),
                                 'shootouts_admitted':int(history.shootout_record.sum()),
                                 'matches_with_proven_extra_time_goals':int(history.proven_extra_time_goals.gt(0).sum())},
           'construction_context':'Retrospective study; no claim of publication before the World Cup.',
           'reserved_results_opened':False,'official_2026_results_loaded':False,'xgboost_executed':False,
           'model_frozen_at_utc':None,'official_results_loaded_at_utc':None,
           'primary_goals_policy':'strict independent Fjelstul catalogue; assumed policies remain sensitivity only',
           'market_value':'Excluded: no dated national membership before 2023; current snapshot prohibited.',
           'coverage_weights':'Current administrative confederations for sensitivity only; no verified historical affiliation dates.'}
    audit['ingestion_quality']={key:data.audit[key] for key in
        ['ambiguous_result_rows_excluded','invalid_result_rows_excluded','duplicate_looking_goal_events_kept','goal_events_missing_minute','normalization']}
    write_report(root,output,audit,diagnostics,comparison)
    audit['artifacts']=[{'file':str(p.relative_to(root)).replace('\\','/'),'sha256':digest_file(p)} for p in sorted(output.iterdir()) if p.is_file() and p.name!='data_audit.json']
    (output/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    (root/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    return audit

def write_report(root,output,audit,diagnostics,comparison):
    names={'total':'Todos','non_friendlies':'No amistosos','friendlies':'Amistosos'}
    selection=audit['selection'];params=selection['parameters']
    grid=pd.read_csv(output/'elo_parameter_comparison.csv')
    grid=grid[grid.scope=='non_friendlies'][['model','friendly_k','nations_k','continental_k','worldcup_k','other_k',
                                          'margin_strength','home_advantage','inactivity_rate','inactivity_grace_days','initial','log_loss','brier']]
    grid.columns=['Configuración','K amistosos','K Nations League','K continental/eliminatorias','K Mundial','K otros',
                  'Multiplicador γ','Ventaja sede','Regresión anual','Inactividad mínima (días)','Inicial','Log loss no amistosos','Brier no amistosos']
    current=diagnostics[diagnostics.window=='Historial anterior a 2023'].copy()
    current=current[['cohort','matches','recorded_zero_zero_rate','recorded_draw_rate','target_zero_zero_rate','target_draw_rate',
                     'zero_zero_difference_vs_complete','draw_difference_vs_complete']]
    for col in current.columns[2:]:current[col]*=100
    current.columns=['Conjunto','Partidos','0–0 registrado %','Empates registrados %','0–0 etiqueta %','Empates etiqueta %',
                     'Diferencia 0–0 (puntos porcentuales)','Diferencia empates (puntos porcentuales)']
    performance=comparison.copy()
    performance['model']=performance.model.map(LABELS)
    performance['scope']=performance.scope.map(names)
    performance['log_loss_ci']=performance.log_loss_ci.map(lambda x:'['+', '.join(f'{float(v):.4f}' for v in x)+']')
    performance['brier_ci']=performance.brier_ci.map(lambda x:'['+', '.join(f'{float(v):.4f}' for v in x)+']')
    display=performance[['model','scope','matches','log_loss','log_loss_ci','brier','brier_ci']]
    display.columns=['Modelo','Estrato','Partidos','Log loss','IC 95 %','Brier','IC 95 % Brier']
    effects=comparison[comparison.scope=='non_friendlies'].copy()
    effects=effects[effects.model!='recorded_target']
    effects['model']=effects.model.map(LABELS)
    effects['interval']=effects.paired_log_loss_ci.map(lambda x:'['+', '.join(f'{float(v):.5f}' for v in x)+']')
    effects=effects[['model','paired_log_loss_difference','interval','paired_brier_difference','blocks_improving']]
    effects.columns=['Grupo frente a Elo + sede','Cambio log loss','IC pareado','Cambio Brier','Bloques con mejora']
    per_block=diagnostics[diagnostics.window!='Historial anterior a 2023'][['window','cohort','matches','recorded_zero_zero_rate','recorded_draw_rate',
                 'target_zero_zero_rate','target_draw_rate','zero_zero_difference_vs_complete','draw_difference_vs_complete']].copy()
    for col in per_block.columns[3:]:per_block[col]*=100
    per_block.columns=['Inicio del bloque','Conjunto','Partidos','0–0 registrado %','Empates registrados %','0–0 etiqueta %','Empates etiqueta %',
                       'Diferencia 0–0 (p.p.)','Diferencia empates (p.p.)']
    per_block=per_block.astype(object).where(per_block.notna(),'No disponible')
    previous=audit['old_improvement_decomposition']
    decomposition=pd.DataFrame(previous)
    admitted=[LABELS[n] for n in audit['features']['groups_passing_against_elo_plus_venue']]
    changes=selection['changed_parameters']
    change_names={'home_advantage':'Ventaja fija de sede (puntos)','inactivity_rate':'Tasa anual de regresión por inactividad',
                  'friendly_k':'K amistosos','nations_k':'K Nations League','continental_k':'K continental/eliminatorias',
                  'worldcup_k':'K Mundial','other_k':'K otros','margin_strength':'Multiplicador de goles γ',
                  'inactivity_grace_days':'Días mínimos de inactividad','initial':'Inicialización común'}
    changes_display=pd.DataFrame([{'Parámetro':change_names.get(k,k),'Selección con cohorte sesgada':v['diagnostic_with_biased_cohort'],
                                   'Selección con conjuntos independientes':v['current']} for k,v in changes.items()])
    sensitivity=comparison[(comparison.model=='form_all_assumed') & (comparison.scope=='non_friendlies')].iloc[0]
    venue_path=output/'additional_venue_coefficient.json'
    venue_test=json.loads(venue_path.read_text(encoding='utf-8')) if venue_path.exists() else None
    venue_text=('El coeficiente adicional de sede no cumple el criterio frente a Solo Elo con ventaja fija; '
                'conservo la referencia más sencilla como baseline principal 1X2. Elo + sede permanece como control común para las ablaciones.'
                if venue_test and not venue_test['passes_criterion_against_fixed_venue_elo'] else
                'La referencia de sede se compara explícitamente con Solo Elo y sus intervalos están en additional_venue_coefficient.json.')
    fixed_summary=comparison[(comparison.model=='elo') & (comparison.scope=='non_friendlies')].iloc[0]
    source_means=diagnostics[diagnostics.window=='Historial anterior a 2023'][['cohort','mean_recorded_total_goals','mean_target_total_goals']].copy()
    source_means.columns=['Conjunto','Goles registrados por partido','Goles de la etiqueta por partido']
    report=f'''# Resultados del estudio

Construyo un estudio retrospectivo de probabilidades de fútbol. El corte deportivo final es exclusivo, 2026-06-10, pero esta selección y sus diagnósticos admiten resultados únicamente hasta 2022. No abro el periodo reservado desde 2023, no entreno XGBoost y no presento este trabajo como un pronóstico publicado antes del Mundial.

En los {int(fixed_summary['matches']):,} no amistosos de validación, Solo Elo con ventaja fija de sede obtiene log loss **{fixed_summary['log_loss']:.4f}** y Brier **{fixed_summary['brier']:.4f}**. Ningún grupo de variables con ventanas estrictas cumple el criterio de mejora frente al control Elo + sede. La forma con duración supuesta en todo el historial permanece como sensibilidad favorable, no como información de goles certificada. La selección de Elo cambia ventaja fija de sede y regresión por inactividad; los detalles e incertidumbre están a continuación.

## Principio de evaluación

Defino los conjuntos sin depender del resultado. El 0–0 no recibe una excepción de cobertura. Registro el protocolo y sus criterios antes de ejecutar la revisión: `docs/PROTOCOLO_CONJUNTOS.md` y `reports/selection_review/selection_protocol.json`.

Para 1X2 admito todos los partidos válidos. Reconstruyo 90 minutos cuando hay evidencia; en el resto uso el marcador final registrado como aproximación marcada, que puede incluir prórroga o duración no estándar. Las tandas permanecen en el conjunto y nunca convierten automáticamente la etiqueta en empate. No afirmo que todas estas etiquetas aproximadas sean resultados certificados a 90 minutos.

Para goles estrictos uso un catálogo independiente de partidos: Fjelstul. La ficha sin prórroga permite utilizar cualquier marcador a 90 minutos; los partidos con prórroga requieren reconstrucción por periodo e integridad reconciliada. El listado martj42 de goleadores no define cobertura del conjunto estricto: un partido sin filas de goles puede ser un 0–0 o un partido sin cobertura. Comparo el catálogo con la inclusión de todos los amistosos de duración supuesta y con una suposición explícita en todo el historial.

## Diagnóstico de selección

El historial completo de esta revisión contiene {audit['history_rows']:,} partidos anteriores a 2023. El conjunto 1X2 contiene esos mismos {audit['result_1x2_rows']:,} registros; el conjunto estricto de goles contiene {audit['strict_goal_rows']:,}. No leo los marcadores del periodo reservado para completar este diagnóstico.

{markdown_table(current,precision=3)}

{markdown_table(source_means,precision=4)}

La caída de goles medios en el diagnóstico archivado acompaña a la sobrerrepresentación de ceros; no la interpreto como menor capacidad ofensiva de las selecciones. Las diferencias del catálogo de Mundiales se interpretan dentro de su dominio y su política de reconstrucción.

La inclusión de todos los registros iguala exactamente las proporciones **registradas** del historial. El estrato no amistoso se compara también con todos los no amistosos; el amistoso, con todos los amistosos. Las tasas del catálogo de Mundiales pueden diferir por el dominio de competiciones; no las fuerzo a igualar las del historial mundial. La reconstrucción de una etiqueta de prórroga puede cambiar la tasa de empate sin cambiar qué partidos entran. La sensibilidad «todos los marcadores registrados» muestra igualdad de composición y de etiquetas por definición; no certifica duración a 90 minutos.

Las tasas y diferencias de **cada conjunto en cada bloque** están en `selection_bias_diagnostics.csv`; las referencias por dominio están en `domain_references.csv`. El diagnóstico archivado conserva la evidencia del sesgo, pero no se utiliza para seleccionar parámetros o variables.

{markdown_table(per_block,precision=3)}

## Cuánto explicaba el artefacto

{markdown_table(decomposition.rename(columns={'scope':'Estrato','matches':'Partidos','fraction':'Participación','elo_log_loss':'Log loss Elo','candidate_log_loss':'Log loss combinación sesgada','mean_improvement':'Mejora media','contribution_to_pooled_improvement':'Contribución a la mejora agregada'}),precision=6)}

Esta descomposición utiliza los mismos partidos de aquella validación. La aportación de los amistosos seleccionados solo por 0–0 no demuestra capacidad predictiva y retiro esa comparación como evidencia vigente de mejora. Las selecciones y ablaciones siguientes utilizan conjuntos independientes del marcador.

## Parámetros de Elo

Selecciono por log loss de no amistosos en cuatro bloques anteriores a 2023. Ajusto la logística con todos los 1X2 disponibles antes de cada bloque, incluidos amistosos de duración supuesta. El estado Elo se actualiza después de calcular todas las variables de una fecha. La tabla presenta los parámetros, no números arbitrarios de configuración.

{markdown_table(grid,precision=6)}

La configuración seleccionada es **{selection['configuration_name']}**. Comparo sus parámetros con la selección diagnosticada:

{markdown_table(changes_display,precision=3)}

Una inicialización común de 1400, 1500 o 1600 solo desplaza la escala; conservo 1500 como convención. Los pesos de partidos no FIFA usan el peso de amistosos y siguen identificados; «otros» no implica reconocimiento oficial.

El multiplicador de diferencia de goles es 1 + γ × log(1 + diferencia absoluta). La ventaja de sede configurada es {params['home_advantage']} puntos y aparece tanto en las actualizaciones del estado como en la diferencia efectiva del baseline Solo Elo. Elo + sede comparte esa ventaja y permite un coeficiente adicional aprendido en el entrenamiento. Así las ablaciones no reciben una sede que falte a su referencia.

{venue_text}

## Evaluación temporal y ablaciones

{markdown_table(display,precision=6)}

Uso Brier multiclase sin dividir. Los intervalos remuestrean trimestres completos con 400 réplicas y semilla fija. No simulo torneos. Comparo cada grupo contra **Elo + sede**; el criterio de admisión se aplica exclusivamente a no amistosos: intervalo pareado de log loss con límite superior menor que cero, Brier sin empeorar y mejora en al menos tres de cuatro bloques.

{markdown_table(effects,precision=6)}

Los grupos que pasan individualmente son: {', '.join(admitted) if admitted else 'ninguno'}. La combinación de los grupos que pasan {'cumple' if audit['features']['combined_groups_passing'] else 'no cumple o no corresponde aplicar'} el criterio. Las ventanas de goles de duración supuesta son sensibilidades y no se adoptan automáticamente por su rendimiento. La selección comparte los bloques de validación y requiere todavía la prueba reservada.

La sensibilidad de forma con duración supuesta en todo el historial obtiene log loss {sensitivity['log_loss']:.6f} en no amistosos, frente a Elo + sede {comparison[(comparison.model=='elo_venue') & (comparison.scope=='non_friendlies')].iloc[0]['log_loss']:.6f}. {'Pasa' if bool(sensitivity['passes_primary_criterion']) else 'No pasa'} el criterio estadístico, pero no la admito como información de goles certificada a 90 minutos: requiere aceptar explícitamente esa aproximación. Mantengo el catálogo verificado como política principal de goles.

Los datos por partido, los resultados de cada bloque y los intervalos de los tres estratos se conservan en `walk_forward_predictions.csv`, `walk_forward_blocks.csv` y `feature_ablation.csv`. La sensibilidad de etiqueta registrada utiliza los mismos partidos con otra definición de resultado y se informa de forma absoluta, sin presentarla como mejora pareada frente a otra etiqueta.

## Límites de información

{audit['timing_uncertainty']['1x2_unverified_count']:,} etiquetas 1X2 usan duración no verificada. Admito {audit['timing_uncertainty']['shootouts_admitted']} partidos con tanda y marco {audit['timing_uncertainty']['matches_with_proven_extra_time_goals']} con goles de prórroga probados, sin excluirlos por ese resultado. Los cruces de catálogo ausentes y los conflictos de integridad están listados por partido.

El ranking semestral tiene disponibilidad conservadora posterior al semestre y antigüedad máxima de 90 días; no extrapolo a 2026. Mercado queda fuera: no tengo pertenencia jugador–selección fechada antes de 2023. La altitud es estática; descanso significa días desde el último internacional observado, no recuperación física medida. La ponderación por confederaciones actuales es una sensibilidad administrativa, no una afiliación histórica certificada ni una política de producción.

Registro fecha de revisión, hashes, exclusiones, políticas y decisiones en `data_audit.json`. No sello predicciones ni cargo resultados oficiales de 2026. La Fase 3 queda pendiente de aprobación.
'''
    (output/'RESULTADOS.md').write_text(report,encoding='utf-8')
    (root/'RESULTADOS.md').write_text(report,encoding='utf-8')
