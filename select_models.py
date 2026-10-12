"""Select and freeze candidates before opening the independent test period."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'2')
sys.path[:0]=[str(ROOT/'.deps'),str(ROOT/'src')]
if __name__=='__main__':
    from football_forecast.model_selection import run
    run(ROOT)
