"""Verify the revision without executing the reserved baseline reproduction."""
from pathlib import Path
from datetime import datetime,timezone
import os
import sys
import json
import unittest
ROOT=Path(__file__).resolve().parents[1]
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
os.environ.pop('ALLOW_RESERVED_EVALUATION',None)
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
verification={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
              'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
              'skip_reasons':[reason for _,reason in result.skipped],'successful':result.wasSuccessful(),
              'command':'python tools/verify_selection_review.py'}
out=ROOT/'reports/selection_review'
out.mkdir(parents=True,exist_ok=True)
(out/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
for path in [out/'data_audit.json',ROOT/'data_audit.json']:
    if path.exists():
        audit=json.loads(path.read_text(encoding='utf-8'));audit['verification']=verification
        path.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
sys.exit(0 if result.wasSuccessful() else 1)
