"""Sequential guarded stages: predictions, evaluation, then official outcomes."""
from pathlib import Path
import os
import sys
import argparse
import json
ROOT=Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools')]
from verify_final_evaluation import frozen_checks,protocol_checks,git,digest

def check_prediction_commit():
    folder=ROOT/'reports/final_evaluation'
    commit=git('rev-parse','phase4-predictions-frozen^{commit}').decode().strip()
    seal_path=folder/'predictions_seal.json'
    if seal_path.read_bytes()!=git('show',f'{commit}:reports/final_evaluation/predictions_seal.json'):
        raise ValueError('Prediction seal differs from frozen commit')
    seal=json.loads(seal_path.read_text(encoding='utf-8'))
    for path,expected in seal['files'].items():
        if digest(ROOT/path)!=expected:raise ValueError(f'Prediction file changed: {path}')
        if (ROOT/path).read_bytes()!=git('show',f'{commit}:{path}'):raise ValueError('Frozen prediction differs from commit')
    return {'prediction_commit':commit,'prediction_commit_time':git('show','-s','--format=%cI',commit).decode().strip()}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','evaluate','worldcup'])
    args=parser.parse_args()
    integrity=frozen_checks();integrity.update(protocol_checks(require_tag=True))
    from football_forecast.final_evaluation import freeze_predictions,evaluate_semiconfirmatory
    if args.stage=='freeze':freeze_predictions(ROOT,integrity)
    else:
        integrity.update(check_prediction_commit())
        if args.stage=='evaluate':evaluate_semiconfirmatory(ROOT,integrity)
        else:
            from football_forecast.final_evaluation import evaluate_worldcup
            evaluate_worldcup(ROOT,integrity)
