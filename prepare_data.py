"""Prepare cutoff-filtered local histories and data-policy sensitivity."""
import argparse
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(variable,'2')
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'.deps'))

if __name__=='__main__':
    from football_forecast.preparation import prepare_local_data
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=ROOT)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'reports/data_preparation')
    parser.add_argument('--cutoff',default='2023-01-01')
    args=parser.parse_args()
    prepare_local_data(args.data_dir,args.output_dir,args.cutoff)
    from football_forecast.source_audit import inspect_sources
    inspect_sources(args.data_dir,args.output_dir,args.cutoff)
