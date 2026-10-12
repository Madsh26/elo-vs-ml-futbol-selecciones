"""Run from the repository root; also supports locally installed dependencies."""
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ.setdefault(name, '2')
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp' / 'matplotlib'))
sys.path.insert(0, str(ROOT / 'src'))
if (ROOT / '.deps').exists():
    sys.path.insert(0, str(ROOT / '.deps'))

if __name__ == '__main__':
    from football_forecast.pipeline import main
    main()
