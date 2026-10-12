"""Complete post-freeze source-name crosswalk without touching forecasts or scores."""
from pathlib import Path
import sys
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools'),str(ROOT)]
from verify_final_evaluation import frozen_checks,protocol_checks
from run_final_evaluation import check_prediction_commit
from football_forecast.final_evaluation import orient_match,event,write_json
check=frozen_checks();check.update(protocol_checks(True));check.update(check_prediction_commit())
folder=ROOT/'reports/final_evaluation'
transfer=pd.read_csv(folder/'transfermarkt_worldcup_results_source.csv',parse_dates=['date'])
aliases={'Turkiye':'Turkey','Democratic Republic of the Congo':'DR Congo'}
for col in ['home_team','away_team']:transfer[col]=transfer[col].replace(aliases)
transfer.to_csv(folder/'transfermarkt_worldcup_results_source.csv',index=False)
pd.DataFrame([{'source':'Transfermarkt games 2026','original':k,'canonical':v} for k,v in aliases.items()]).to_csv(folder/'source_verification_aliases.csv',index=False)
comparison=pd.read_csv(folder/'worldcup_source_comparison.csv',parse_dates=['fixture_utc_date'])
for r in comparison.itertuples():
    match=orient_match(transfer,r.home_team,r.away_team,r.fixture_utc_date)
    if match is None:raise ValueError('Supplied Transfermarkt group match missing after canonical name check')
    score=f"{int(match['recorded_home_score'])}-{int(match['recorded_away_score'])}"
    comparison.at[r.Index,'transfermarkt_score']=score
    comparison.at[r.Index,'transfermarkt_date']=str(match['date'].date())
    comparison.at[r.Index,'transfermarkt_agrees']=score==r.martj42_score
comparison.to_csv(folder/'worldcup_source_comparison.csv',index=False)
conclusion=json.loads((folder/'worldcup_conclusion.json').read_text(encoding='utf-8'))
conclusion['group_transfermarkt_matches']=int(comparison.transfermarkt_agrees.notna().sum())
conclusion['group_transfermarkt_discrepancies']=int(comparison.transfermarkt_agrees.eq(False).sum())
conclusion['source_crosswalk_completed_after_initial_comparison']=True
write_json(folder/'worldcup_conclusion.json',conclusion)
event(folder,'worldcup_source_crosswalk_completed',transfermarkt_matches=conclusion['group_transfermarkt_matches'],
      source_name_aliases=aliases,forecast_values_changed=False)
print(json.dumps(conclusion,indent=2,ensure_ascii=False))
