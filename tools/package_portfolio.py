"""Package authored source and generated results, without private/raw archives."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
files=['README.md','LICENSE','requirements.txt','.gitignore','run_forecast.py','predict_match.py',
       'PLAN_ML_PARTIDOS_XGBOOST_DIXON_COLES.md']
folders=['src','tests','notebooks','.github','tools','reports/probabilistic']
target=root/'portfolio_github.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in files:
        archive.write(root/name,name)
    for folder in folders:
        for path in sorted((root/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                archive.write(path,path.relative_to(root).as_posix())
print(f'Portfolio package: {target.name} ({target.stat().st_size:,} bytes)')
