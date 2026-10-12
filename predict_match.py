"""Load a saved model and compare two teams, with no training or simulation."""
import argparse
from pathlib import Path
import sys
import os
import json

ROOT = Path(__file__).resolve().parent
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'2')
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'.deps'))

def main():
    import joblib
    import pandas as pd
    from collections import deque
    from types import SimpleNamespace
    from football_forecast.data import HistoryState, normalize, FEATURES
    from football_forecast.models import goal_rates, score_matrix, matrix_1x2
    parser=argparse.ArgumentParser()
    parser.add_argument('--home',required=True)
    parser.add_argument('--away',required=True)
    parser.add_argument('--host',help='Actual host team; default neutral venue')
    parser.add_argument('--model-path',type=Path,default=ROOT/'reports/probabilistic/models/deployment.joblib')
    args=parser.parse_args()
    bundle=joblib.load(args.model_path)
    home,away=normalize(args.home),normalize(args.away)
    if home==away:
        parser.error('Choose two different teams')
    known=bundle['state']['games']
    if any(known.get(t,0)<5 for t in [home,away]):
        parser.error('Each team needs at least five eligible historical matches')
    host=normalize(args.host) if args.host else 'Neutral'
    if args.host and host not in [home,away]:
        parser.error('--host must be one of the two teams')
    state=HistoryState()
    state.elo.update(bundle['state']['elo'])
    state.games.update(known)
    for t,rows in bundle['state']['recent'].items():
        state.recent[t]=deque(rows,maxlen=10)
    row=SimpleNamespace(home_team=home,away_team=away,country=host,
                        neutral=not bool(args.host),tournament='FIFA World Cup')
    frame=pd.DataFrame([{**vars(row),**state.features(row)}])
    name=bundle['selected_model']
    if name in ['poisson','dixon_coles']:
        estimator=bundle['poisson'] if name=='poisson' else bundle['dc']
        lh,la=estimator.rates(frame)
        rho=estimator.rho
    else:
        lh,la=goal_rates(bundle['goal_models'],frame)
        rho=bundle['rho'] if name=='xgboost_dixon_coles' else 0.
    matrix,tail=score_matrix(float(lh[0]),float(la[0]),rho)
    p=matrix_1x2(matrix)
    import numpy as np
    ordered=np.dstack(np.unravel_index(np.argsort(matrix,axis=None)[::-1][:5],matrix.shape))[0]
    output={'home_team':home,'away_team':away,'cutoff':bundle['cutoff'],
            'target_minutes':90,'model':name,'home_win':float(p[0]),'draw':float(p[1]),
            'away_win':float(p[2]),'tail_mass_omitted':tail,
            'top_scorelines':[{'score':f'{h}-{a}','probability':float(matrix[h,a])} for h,a in ordered],
            'xgboost_1x2':bundle['classifier'].predict_proba(frame[FEATURES])[0].tolist()}
    print(json.dumps(output,indent=2,ensure_ascii=True))

if __name__=='__main__':
    main()
