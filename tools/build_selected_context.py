"""Build context and secondary ablation without repeating Elo selection."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ.setdefault(variable,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.context_features import build_context
from football_forecast.elo_calibration import ablate_rank_points
build_context(ROOT,ROOT/'reports/feature_design')
ablate_rank_points(ROOT/'reports/feature_design')
