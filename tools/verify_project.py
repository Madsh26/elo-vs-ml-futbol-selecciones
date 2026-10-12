"""Execute the suite and record actual verification counts and timestamps."""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ.setdefault(variable,'2')
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'successful':result.wasSuccessful(),'command':'python tools/verify_project.py'}
out=ROOT/'reports/feature_design'
out.mkdir(exist_ok=True,parents=True)
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
sys.exit(0 if result.wasSuccessful() else 1)
