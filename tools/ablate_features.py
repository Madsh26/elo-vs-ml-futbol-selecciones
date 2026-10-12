"""Run declared feature and coverage ablations on pre-2023 artifacts."""
from pathlib import Path
import sys
import os
ROOT=Path(__file__).resolve().parents[1]
for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ.setdefault(variable,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.feature_ablation import ablate_feature_groups
ablate_feature_groups(ROOT,ROOT/'reports/feature_design')
