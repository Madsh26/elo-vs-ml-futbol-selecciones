"""Record observed browser QA without inventing a visual or metric result."""
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_final_evaluation import utc_now,digest
folder=ROOT/'reports/final_evaluation'
review={'recorded_at_utc':utc_now(),'method':'Codex browser, local 127.0.0.1 page; screenshot and live controls',
 'html_sha256':digest(folder/'football_report.html'),'javascript_syntax_check':'node tools/check_report_js.js, passed',
 'observed_matches':72,'observed_model_options':8,'search_Colombia_matches':3,
 'verified_controls':['selection search','model selector: logistic and Poisson','match detail selection'],
 'verified_match':'Colombia vs Portugal, 2026-06-27; recorded score 0-0',
 'distinct_products_visible':True,'screenshot_file':'assets/report_preview.png',
 'screenshot_sha256':digest(ROOT/'assets/report_preview.png'),
 'browser_initial_javascript_escape_error_fixed_before_delivery':True}
(folder/'html_review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False),encoding='utf-8')
print('Revisión visual observada registrada.')
