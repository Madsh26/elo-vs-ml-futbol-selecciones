"""Select Elo and optional dated features using pre-2023 blocks only."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ.setdefault(name,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
if __name__=='__main__':
    from football_forecast.elo_calibration import calibrate
    calibrate(ROOT,ROOT/'reports/feature_design')
    from football_forecast.context_features import build_context
    build_context(ROOT,ROOT/'reports/feature_design')
    from football_forecast.elo_calibration import ablate_rank_points
    ablate_rank_points(ROOT/'reports/feature_design')
    from football_forecast.feature_ablation import ablate_feature_groups
    ablate_feature_groups(ROOT,ROOT/'reports/feature_design')
