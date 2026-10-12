"""Run local checks without admitting reserved historical targets."""
from pathlib import Path
from datetime import datetime, timezone
import os
import sys
import json
import unittest
ROOT=Path(__file__).resolve().parents[1]
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'2')
os.environ.pop('ALLOW_RESERVED_EVALUATION',None)
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
verification={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
              'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
              'skip_reasons':[reason for _,reason in result.skipped],'successful':result.wasSuccessful(),
              'command':'python tools/verify_models_selected.py','reserved_results_opened':False}
output=ROOT/'reports/models_selected'
(output/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
from football_forecast.ingestion import digest_file
for path in [ROOT/'data_audit.json',output/'data_audit.json']:
    if path.exists():
        audit=json.loads(path.read_text(encoding='utf-8'))
        audit['verification']=verification
        audit['artifacts_models_selected']={p.relative_to(ROOT).as_posix():digest_file(p) for p in output.iterdir()
                                            if p.is_file() and p.name!='data_audit.json'}
        path.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
sys.exit(0 if result.wasSuccessful() else 1)
