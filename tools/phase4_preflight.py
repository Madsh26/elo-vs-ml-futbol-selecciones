"""Test the fixed Elo threshold using only outcomes before 2023."""
from pathlib import Path
from datetime import datetime, timezone
import os
import sys
import json
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools')]
from verify_final_evaluation import frozen_checks, digest
from football_forecast.ingestion import load_study_data, MATCH_KEY
from football_forecast.elo_calibration import EloParameters, CalibratedElo, BLOCKS
from football_forecast.selection_review import build_batches, elo_from_batches
import pandas as pd

checks=frozen_checks()
folder=ROOT/'reports/final_evaluation'
protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
params=EloParameters(**json.loads((ROOT/'reports/models_selected/selected_elo.json').read_text(encoding='utf-8'))['parameters'])
history=load_study_data(ROOT,'2023-01-01').history
batches=build_batches(history)
ratings=elo_from_batches(batches,params)
full=history.merge(ratings,on=MATCH_KEY,validate='one_to_one')
full['strong']=full.elo_home.gt(1700)&full.elo_away.gt(1700)
rows=[]
for start,end in BLOCKS:
    block=full[full.date.ge(start)&full.date.lt(end)]
    for scope,data in [('total',block),('non_friendlies',block[block.competitive]),('friendlies',block[~block.competitive])]:
        strong=data[data.strong]
        count=strong.x12_target.value_counts()
        rows.append({'start':start,'end_exclusive':end,'scope':scope,'all_matches':len(data),'both_elo_above_1700':len(strong),
                     'home_wins':int(count.get(0,0)),'draws':int(count.get(1,0)),'away_wins':int(count.get(2,0)),
                     'estimable_under_requested_minimum':len(strong)>=200 and all(count.get(k,0)>=30 for k in range(3))})
table=pd.DataFrame(rows)
table.to_csv(folder/'threshold_pre2023_counts.csv',index=False)
state=CalibratedElo(params)
for date,day in batches:
    state.prepare_day([team for r in day for team in (r.home_team,r.away_team)],date)
    state.update_day(day)
teams=protocol['worldcup_48']
state.prepare_day(teams,pd.Timestamp('2022-12-31'))
snapshot=pd.DataFrame([{'team':team,'elo_at_2022_12_31':state.ratings[team],
                        'last_match_date':str(state.last[team].date()) if team in state.last else None,
                        'above_1700':state.ratings[team]>1700} for team in teams]).sort_values('elo_at_2022_12_31',ascending=False)
snapshot.to_csv(folder/'worldcup_48_elo_2022_12_31.csv',index=False)
nonfriendly=table[table.scope.eq('non_friendlies')]
viable=int(nonfriendly.both_elo_above_1700.sum())>=200 and int(nonfriendly.draws.sum())>=30 and int(nonfriendly.home_wins.sum())>=30 and int(nonfriendly.away_wins.sum())>=30
summary={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'data_cutoff_exclusive':'2023-01-01',
         'latest_result':str(history.date.max().date()),'threshold':1700,'rule':'both raw pre-match Elo strictly >1700',
         'viable_pooled_nonfriendlies':viable,'all_four_blocks_estimable':bool(nonfriendly.estimable_under_requested_minimum.all()),
         'nonfriendly_matches':int(nonfriendly.both_elo_above_1700.sum()),
         'worldcup_48_above_1700_at_2022_12_31':int(snapshot.above_1700.sum()),
         'hashes':{p.name:digest(p) for p in [folder/'threshold_pre2023_counts.csv',folder/'worldcup_48_elo_2022_12_31.csv']},
         'frozen_checks':checks,'post2022_metrics_computed':False}
(folder/'threshold_preflight.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(table.to_string(index=False))
print(json.dumps(summary,indent=2,ensure_ascii=False))
