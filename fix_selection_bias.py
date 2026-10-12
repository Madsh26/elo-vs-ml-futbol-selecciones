"""Run the declared selection review without opening results from 2023."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
if __name__=='__main__':
    from football_forecast.selection_review import run_review
    run_review(ROOT,ROOT/'reports/selection_review')
