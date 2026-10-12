"""Inspect supplied official-result sources only after the prediction commit."""
from pathlib import Path
import sys
import zipfile
import json
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools'),str(ROOT)]
from verify_final_evaluation import frozen_checks,protocol_checks
from run_final_evaluation import check_prediction_commit
from football_forecast.final_evaluation import event,now,write_json
from football_forecast.ingestion import load_study_data

check=frozen_checks();check.update(protocol_checks(True));check.update(check_prediction_commit())
folder=ROOT/'reports/final_evaluation'
record=folder/'official_results_load_record.json'
if not record.exists():
    stamp={'first_official_results_load_started_at_utc':now(),'prediction_commit':check['prediction_commit'],
           'prediction_commit_time':check['prediction_commit_time'],'models_refitted':False,
           'sources':['international_results_current.zip','openfootball_worldcup.zip']}
    write_json(record,stamp)
    event(folder,'official_results_load_started',**stamp)
import pandas as pd
path=folder/'official_worldcup_results_source.csv'
if path.exists():
    world=pd.read_csv(path,parse_dates=['date'])
else:
    data=load_study_data(ROOT,'2026-07-21')
    world=data.history[data.history.tournament.eq('FIFA World Cup') & data.history.date.ge('2026-06-10')]
    world.to_csv(path,index=False)
print(world[['date','home_team','away_team','recorded_home_score','recorded_away_score','x12_source']].head(6).to_string(index=False))
print('World Cup matches:',len(world),'date range:',world.date.min(),world.date.max())
with zipfile.ZipFile(ROOT/'data/raw/openfootball_worldcup.zip') as z:
    names=[name for name in z.namelist() if '/2026--' in name and name.endswith(('.txt','.json','.csv'))]
    print('Openfootball files:',names)
    for name in names[:4]:
        print('FILE:',name)
        print(z.read(name).decode('utf-8-sig')[:6500])
import duckdb
connection=duckdb.connect(str(ROOT/'data/raw/transfermarkt.duckdb'),read_only=True)
print('Transfermarkt schema:',connection.execute('DESCRIBE games').fetchall())
print('Transfermarkt dates:',connection.execute('SELECT min(date),max(date),count(*) FROM games').fetchall())
print('Transfermarkt World Cup-period games:',connection.execute("SELECT count(*) FROM games WHERE date >= DATE '2026-06-11'").fetchall())
