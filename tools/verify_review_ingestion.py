"""Recheck the executed input cohort and restore its detailed source audit."""
from pathlib import Path
import os
import sys
import json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.ingestion import load_study_data,digest_file
out=ROOT/'reports/selection_review'
data=load_study_data(ROOT,'2023-01-01')
temporary=ROOT/'tmp/review_input_verification.csv'
temporary.parent.mkdir(parents=True,exist_ok=True)
data.history.to_csv(temporary,index=False)
if digest_file(temporary)!=digest_file(out/'historical_results.csv'):
    raise RuntimeError('Input cohort changed since the executed calibration')
data.audit['reingestion_verified_at_utc']=datetime.now(timezone.utc).isoformat()
data.audit['historical_input_sha256_verified']=digest_file(temporary)
(out/'ingestion_audit.json').write_text(json.dumps(data.audit,indent=2,ensure_ascii=False),encoding='utf-8')
print('Ingreso reproducido idénticamente, sin resultados desde 2023 ni reentrenamiento.')
