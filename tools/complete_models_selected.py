"""Refresh readable documents and audit, preserving frozen model bytes."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import sys
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'2')
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
import pandas as pd
from football_forecast.model_selection import write_documents, save_json, flagged, code_digest
from football_forecast.ingestion import digest_file

folder=ROOT/'reports/models_selected'
manifest=json.loads((folder/'freeze_manifest.json').read_text(encoding='utf-8'))
for model in manifest['models']:
    if digest_file(ROOT/model['path'])!=model['sha256']:
        raise ValueError('Frozen model changed')
manifest['code_hash_line_endings']='LF normalized'
manifest['code_sha256']={path:code_digest(ROOT/path) for path in manifest['code_sha256']}
manifest['documentation_completed_at_utc']=datetime.now(timezone.utc).isoformat()
save_json(folder/'freeze_manifest.json',manifest)
audit=json.loads((ROOT/'data_audit.json').read_text(encoding='utf-8'))
audit['model_selection']=manifest
history=pd.read_csv(ROOT/'reports/selection_review/historical_results.csv',parse_dates=['date'])
if history.date.max()>=pd.Timestamp('2023-01-01'):
    raise ValueError('Reserved results found')
friend=history[history.tournament.eq('Friendly') & history.x12_90_reconstructed]
audit['friendly_duration_validation']={'independently_verified_matches':len(friend),
    'proportion_with_extra_time_goals':float(friend.proven_extra_time_goals.gt(0).mean()) if len(friend) else None,
    'shootouts_in_verified_set':int(friend.shootout_record.sum()),
    'interpretation':'No independently verified friendlies before 2023; proportions unavailable, not zero.'}
audit['training_model_rows']=int(history.date.ge('2000-01-01').sum())
audit['models_git_tag']='models-selected'
audit['score_distribution_constraints']={}
for kind in ['poisson','dixon_coles','xgboost_poisson']:
    pred=pd.read_csv(folder/f'predictions_{kind}.csv')
    audit['score_distribution_constraints'][kind]={
        'evaluated_matches':len(pred),'rho_clamped_matches':int(pred.rho_clamped.sum()),
        'upper_rate_limit_matches':int((pred.lambda_home.ge(12-1e-10)|pred.lambda_away.ge(12-1e-10)).sum())}
mapping=pd.read_csv(ROOT/'reports/data_preparation/confederations.csv').set_index('team').confederation.to_dict()
coverage=[]
training=history[history.date.ge('2000-01-01')]
for domain in ['year','competition','confederation']:
    populations={'history':training,'goals_primary':training,
        'goals_exclude_marked':training[~flagged(training)],
        'goals_non_friendlies':training[training.competitive],
        'strict_validation':training[training.goal_training_eligible]}
    counts={}
    for name,data in populations.items():
        if domain=='year':values=data.date.dt.year.astype(str)
        elif domain=='competition':values=data.competition_family
        else:
            values=pd.concat([data.home_team.map(mapping),data.away_team.map(mapping)]).fillna('Sin asignación')
        counts[name]=values.value_counts()
    categories=sorted(set().union(*(set(c.index) for c in counts.values())))
    for name,count in counts.items():
        for value in categories:
            share=float(count.get(value,0)/count.sum()) if count.sum() else None
            ref=float(counts['history'].get(value,0)/counts['history'].sum())
            coverage.append({'domain':domain,'population':name,'category':value,'count':int(count.get(value,0)),
                 'share':share,'history_share':ref,'difference':share-ref if share is not None else None,
                 'confederation_current_metadata_only':domain=='confederation'})
pd.DataFrame(coverage).to_csv(folder/'goal_population_coverage.csv',index=False)
selection=json.loads((folder/'selected_elo.json').read_text(encoding='utf-8'))
decision=json.loads((folder/'model_decision.json').read_text(encoding='utf-8'))
metrics=pd.read_csv(folder/'model_comparison.csv')
form=pd.read_csv(folder/'form_sensitivity.csv')
write_documents(ROOT,folder,metrics,selection,decision,audit,form)
audit['artifacts_models_selected']={p.relative_to(ROOT).as_posix():digest_file(p) for p in folder.iterdir()
                                    if p.is_file() and p.name!='data_audit.json'}
audit['final_document_sha256']={p.relative_to(ROOT).as_posix():digest_file(p) for p in
                              [ROOT/'README.md',ROOT/'RESULTADOS.md',ROOT/'docs/DECISIONES_DE_DISEÑO.md']}
save_json(ROOT/'data_audit.json',audit)
save_json(folder/'data_audit.json',audit)
print('Documents and coverage refreshed; frozen model bytes unchanged.')
