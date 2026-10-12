"""Assemble reports/audit from already executed review artifacts; no refitting."""
from pathlib import Path
from datetime import datetime,timezone
import sys
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
import pandas as pd
from football_forecast.selection_review import write_report,metric_rows,passes,bias_diagnostics
from football_forecast.ingestion import digest_file,before_cutoff_csv
out=ROOT/'reports/selection_review'
history=pd.read_csv(out/'historical_results.csv',parse_dates=['date'])
if (history.date>='2023-01-01').any():raise ValueError('Reserved results in saved review history')
protocol=json.loads((out/'selection_protocol.json').read_text(encoding='utf-8'))
selection=json.loads((out/'selected_elo.json').read_text(encoding='utf-8'))
features=json.loads((out/'feature_selection.json').read_text(encoding='utf-8'))
predictions=pd.read_csv(out/'walk_forward_predictions.csv',parse_dates=['date'])
reference=predictions[predictions.model=='elo_venue'].reset_index(drop=True)
fixed=predictions[predictions.model=='elo'].reset_index(drop=True)
venue_effect=metric_rows(reference,'elo_venue',fixed)
extra_venue=passes(venue_effect)
(out/'additional_venue_coefficient.json').write_text(json.dumps({'metrics':venue_effect,
       'passes_criterion_against_fixed_venue_elo':extra_venue},indent=2),encoding='utf-8')
features['fixed_venue_elo_vs_learned_venue_passes']=extra_venue
features['primary_x12_baseline']='elo_venue' if extra_venue else 'elo'
form=predictions[predictions.model=='form_all_assumed'].reset_index(drop=True)
features['form_all_assumed_passes_but_not_adopted']=passes(metric_rows(form,'form_all_assumed',reference))
(out/'feature_selection.json').write_text(json.dumps(features,indent=2),encoding='utf-8')
comparison=pd.read_csv(out/'feature_ablation.csv')
for col in ['log_loss_ci','brier_ci','paired_log_loss_ci','paired_brier_ci']:
    comparison[col]=comparison[col].map(lambda x:json.loads(x) if isinstance(x,str) and x.startswith('[') else x)
decomposition=pd.read_csv(out/'archived_bias_decomposition.csv').to_dict('records')
ingestion_path=out/'ingestion_audit.json'
ingestion=None
if ingestion_path.exists():
    ingestion=json.loads(ingestion_path.read_text(encoding='utf-8'))
    sources=ingestion['sources']
else:
    prior=json.loads((ROOT/'reports/data_preparation/data_audit.json').read_text(encoding='utf-8'))
    sources=prior['sources']
    for source in sources:
        source['file']=source['file'].replace('\\','/')
        if digest_file(ROOT/source['file'])!=source['sha256']:
            raise ValueError('Source changed since ingestion: '+source['file'])
audit={'correction_started_at_utc':protocol['written_at_utc'],'correction_completed_at_utc':datetime.now(timezone.utc).isoformat(),
       'review_git_tag':'selection-bias-fixed',
       'correction_date_local':str(pd.Timestamp(protocol['written_at_utc']).tz_convert('America/Bogota').date()),
       'correction_timezone':'America/Bogota',
       'prediction_cutoff_exclusive':'2026-06-10','selection_and_review_cutoff_exclusive':'2023-01-01',
       'latest_result_admitted':str(history.date.max().date()),'history_rows':len(history),
       'strict_goal_rows':int(history.goal_training_eligible.sum()),'result_1x2_rows':int(history.x12_eligible.sum()),
       'protocol_sha256':digest_file(out/'selection_protocol.json'),'sources':sources,
       'selection':selection,'features':features,'old_improvement_decomposition':decomposition,
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
if ingestion is not None:
    audit['ingestion_quality']={key:ingestion[key] for key in
        ['ambiguous_result_rows_excluded','invalid_result_rows_excluded','duplicate_looking_goal_events_kept','goal_events_missing_minute','normalization']}
if (out/'verification.json').exists():audit['verification']=json.loads((out/'verification.json').read_text(encoding='utf-8'))
legacy=None
legacy_path=ROOT/'reports/data_preparation/historical_results.csv'
if legacy_path.exists():
    with legacy_path.open('rb') as stream:legacy=before_cutoff_csv(stream,'2023-01-01')
    legacy['date']=pd.to_datetime(legacy.date)
    legacy['goal_training_eligible']=legacy.goal_training_eligible.str.casefold().eq('true')
    for col in ['recorded_home_score','recorded_away_score','home_score_90','away_score_90']:
        legacy[col]=pd.to_numeric(legacy[col],errors='coerce')
diagnostics=bias_diagnostics(history,out,legacy)
write_report(ROOT,out,audit,diagnostics,comparison)
audit['artifacts']=[{'file':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest_file(p)}
                    for p in sorted(out.iterdir()) if p.is_file() and p.name!='data_audit.json']
for target in [out/'data_audit.json',ROOT/'data_audit.json']:
    target.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
print('Informes reconstruidos a partir de resultados ejecutados; sin reentrenar.')
