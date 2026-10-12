"""Seal executed final evidence; no model updates, fits or new metric calculation."""
from pathlib import Path
import sys
import json
import platform
import hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools'),str(ROOT)]
from verify_final_evaluation import frozen_checks,protocol_checks,digest,utc_now,git
from run_final_evaluation import check_prediction_commit
folder=ROOT/'reports/final_evaluation'
integrity=frozen_checks();integrity.update(protocol_checks(True));integrity.update(check_prediction_commit())
verification=json.loads((folder/'verification.json').read_text(encoding='utf-8'))
verification.pop('reserved_metrics_computed',None)
verification['integrity_check_computed_metrics']=False
verification['post2022_evaluation_executed']=True
(folder/'verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
report=json.loads((folder/'report_manifest.json').read_text(encoding='utf-8'))
import numpy,pandas,scipy,sklearn,xgboost,joblib
audit={'completed_at_utc':utc_now(),'retrospective':True,'sports_cutoff_exclusive':'2026-06-10',
       'model_training_cutoff_exclusive':'2023-01-01','evidence_status':'selection / semiconfirmatory / descriptive World Cup',
       'original_datacamp_comparator_excluded':True,'prior_exposure_matches':846,'immutable_checks':integrity,
       'protocol':json.loads((folder/'active_protocol.json').read_text(encoding='utf-8')),
       'predictions':json.loads((folder/'predictions_seal.json').read_text(encoding='utf-8')),
       'first_official_results_load_started_at_utc':json.loads((folder/'official_results_load_record.json').read_text(encoding='utf-8'))['first_official_results_load_started_at_utc'],
       'chronology_deviation':report['chronology_deviation'],'sequence_strictly_serial':False,
       'model_weights_refitted':False,'selection_or_threshold_changed_using_post2022_results':False,
       'dataset':json.loads((folder/'data_inventory.json').read_text(encoding='utf-8')),
       'semiconfirmatory':json.loads((folder/'semiconfirmatory_conclusion.json').read_text(encoding='utf-8')),
       'worldcup':json.loads((folder/'worldcup_conclusion.json').read_text(encoding='utf-8')),
       'sources':json.loads((folder/'ingestion_precut_audit.json').read_text(encoding='utf-8'))['sources'],
       'verification_at_publication':verification,
       'runtime':{'python':platform.python_version(),'numpy':numpy.__version__,'pandas':pandas.__version__,
                  'scipy':scipy.__version__,'sklearn':sklearn.__version__,'xgboost':xgboost.__version__,'joblib':joblib.__version__},
       'data_assumptions':['final score used where 90 minutes unverified, same admission for every score',
                          'no shootout-to-draw conversion','identical goal rows retained',
                          'all same-date pre-match states evaluated before outcome updates',
                          'current player value/club/nationality and undated national_teams not used',
                          'no current FIFA ranking extrapolation'],
       'source_crosswalk_2026':{'Turkiye':'Turkey','Democratic Republic of the Congo':'DR Congo'},
       'cluster_units':{'quarter_primary':2000,'month_sensitivity':2000,'seed':20261012,
                        'observed_all_quarters':14,'observed_all_months':39,'nonfriendly_observed_months':33},
       'estimability':{'minimum_matches':200,'minimum_each_class':30},
       'html_review':json.loads((folder/'html_review.json').read_text(encoding='utf-8')) if (folder/'html_review.json').exists() else {'status':'not yet recorded'}}
excluded={'data_audit.json','verification.json','history_precut.csv','features_precut.csv'}
audit['output_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in folder.iterdir() if p.is_file() and p.name not in excluded}
audit['local_intermediate_sha256']={p.name:digest(p) for p in [folder/'history_precut.csv',folder/'features_precut.csv']}
audit['documentation_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in
    [ROOT/'README.md',ROOT/'RESULTADOS.md',ROOT/'docs/DECISIONES_DE_DISEÑO.md',ROOT/'docs/DATOS_Y_DICCIONARIO.md']}
audit['asset_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'assets').iterdir() if p.is_file()}
audit['final_evaluator_code_sha256_lf_normalized']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in
    [ROOT/'src/football_forecast/final_evaluation.py',ROOT/'run_final_evaluation.py']}
(folder/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
index={'role':'audit index, not a duplicate of frozen or final audit','updated_at_utc':utc_now(),'retrospective':True,
 'post2022_evidence':'semiconfirmatory due to prior DataCamp exposure','final_evaluation_completed':True,
 'authoritative_documents':{p.relative_to(ROOT).as_posix():{'sha256':digest(p)} for p in
   [ROOT/'reports/models_selected/data_audit.json',ROOT/'reports/models_selected/freeze_manifest.json',
    folder/'data_audit.json',folder/'protocol_approved.json',folder/'active_protocol.json',folder/'predictions_seal.json']},
 'commit_authority':{'models':'models-selected','original_protocol':'phase4-protocol','approved_protocol':'phase4-protocol-approved',
                     'predictions':'phase4-predictions-frozen','results':'phase4-evaluated; resolve tag timestamp in Git'},
 'first_official_results_load_started_at_utc':audit['first_official_results_load_started_at_utc'],
 'chronology_deviation':audit['chronology_deviation']}
(ROOT/'data_audit.json').write_text(json.dumps(index,indent=2,ensure_ascii=False),encoding='utf-8')
print('Auditoría final y su índice registrados; congelados y predicciones verificados.')
