"""Prepare commitments and documentation; never load any post-2022 outcome."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from verify_final_evaluation import ROOT, OUTPUT, frozen_checks, utc_now, digest, git, FROZEN_COMMIT


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


checks=frozen_checks()  # Must precede even the pre-2023 probability discrepancy.
OUTPUT.mkdir(parents=True,exist_ok=True)
if (OUTPUT/'protocol.json').exists():raise RuntimeError('Protocol already exists; do not overwrite a sealed protocol')
fixtures=pd.read_csv(ROOT/'reports/probabilistic/resolved_fixtures.csv')
teams=sorted(set(fixtures.home_team)|set(fixtures.away_team))
if len(fixtures)!=72 or len(teams)!=48:raise ValueError('Invalid fixture metadata')
initial_status=git('status','--porcelain').decode()
old_untracked=[line[3:] for line in initial_status.splitlines() if line.startswith('?? ') and not line[3:].startswith(('reports/final_evaluation/','tools/prepare_phase4','tools/verify_final','tests/test_final','docs/'))]
inventory=[]
for name in old_untracked:
    path=ROOT/name
    if path.is_file():inventory.append({'path':name,'sha256':digest(path),'bytes':path.stat().st_size,'policy':'preserved locally, excluded from active Git scope'})
write_json(OUTPUT/'hygiene_inventory.json',{'checked_at_utc':utc_now(),'tracked_initially_clean':not any(not line.startswith('?? ') for line in initial_status.splitlines()),'preserved_untracked':inventory})
protocol={
 'project_title':'Probabilidades de fútbol internacional',
 'written_at_utc':utc_now(),'status':'awaiting_explicit_user_approval',
 'retrospective':True,'approval_required_before_any_post2022_metric':True,
 'frozen_reference':checks,
 'evaluation_population':{'start_inclusive':'2023-01-01','end_exclusive':'2026-06-10',
    'evidence_status':'semiconfirmatory, not untouched',
    'previous_exposure':{'pipeline':'DataCamp score-oriented historical project, excluded from every baseline and comparison',
                         'matches_previously_scored':846,'start':'2023-01-08','end':'2026-06-04',
                         'provenance':'previous documented audit; not recomputed for this protocol'},
    'admission':'all valid registered matches, independent of score; verified 90 minutes where possible, final score otherwise',
    'shootouts':'flag, never force a 90-minute draw','proven_extra_time':'flag and reconstruct where verified',
    'same_date':'calculate all features before updating any outcomes that day'},
 'subperiods':[['2023-01-01','2024-01-01'],['2024-01-01','2025-01-01'],
               ['2025-01-01','2026-01-01'],['2026-01-01','2026-06-10']],
 'primary_comparison':{'candidate':'frozen logistic with Elo and form','reference':'frozen Solo Elo with fixed venue',
    'population':'non-friendlies','endpoint':'pooled per-match log loss difference, logistic minus Elo',
    'confirmation_rule':'upper paired 95% CI < 0, mean Brier difference <= 0, log loss improves in >=3/4 subperiods',
    'decision':'confirm or fail to confirm selection; do not reselect, refit or change deployment weights from these outcomes'},
 'comparators':['frequency','elo','logistic','ordinal','xgboost','poisson','dixon_coles','xgboost_poisson'],
 'excluded_comparators':['worldcup_2026_model_pipeline.py','reports/probabilistic models and metrics'],
 'strata':{'total':'all admitted matches','friendlies':'tournament Friendly','non_friendlies':'not Friendly; operational category, not certification of official status',
    'worldcup':'FIFA World Cup, report N=0 if absent',
    'strong_teams':{'home_elo_strictly_greater_than':1700,'away_elo_strictly_greater_than':1700,
                    'rating':'raw pre-match frozen-policy Elo, without venue bonus','threshold_not_tuned':True},
    'worldcup_48_mutual':'both opponents in the fixed 48-team fixture list',
    'worldcup_48_any_opponent':'at least one opponent in the fixed 48-team fixture list'},
 'worldcup_48':teams,'fixture_metadata_sha256':digest(ROOT/'reports/probabilistic/resolved_fixtures.csv'),
 'sensitivities':{'exclude_marked':'evaluate only rows without shootout or proven extra-time goals; no refitting; main frozen form state retains all history',
    'non_friendlies':'evaluate frozen models on non-friendlies; no training restricted to the evaluation period',
    'strict_duration':'verified independent catalogue only, descriptive when sample is absent or small',
    'no_input_policy_switch':'do not rebuild different form variables for the already frozen model'},
 'metrics':{'log_loss':'natural log, clip observed outcome probability to [1e-15,1]',
    'brier':'sum of squared error across 3 classes, no division',
    'rps':'sum squared cumulative probability errors / 2; ordered away-win, draw, home-win',
    'accuracy':'argmax in home-win, draw, away-win order, deterministic tie rule',
    'draw_rates':['observed','predicted'],
    'score_nll':'joint infinite-support likelihood, count models only; unavailable for direct 1X2 classifiers',
    'reliability':'10 fixed equal-width bins [0,1], counts, mean probability and observed fraction; empty bins explicit',
    'ece':'10 fixed-bin ECE per class, supplementary only',
    'calibration_intercept_slope':'one-vs-rest binary unpenalized logistic diagnostic on logit(p), p clipped [1e-6,1-1e-6]; ideal intercept 0, slope 1; no correction applied to forecasts; failure or single-class strata reported unavailable'},
 'uncertainty':{'bootstrap_replicates':2000,'unit':'whole calendar quarters','paired':True,
    'seed':20261012,'confidence_level':.95,'means':'pool match sums/counts, not an unweighted average of quarters',
    'endpoints':['log_loss','brier','rps','accuracy','draw_rates','score_nll'],
    'multiple_comparisons_correction':False,'secondary_comparisons':'descriptive, no claim from an isolated significant comparator or stratum'},
 'product_separation':{'result_product':'logistic 1X2','score_product':'Poisson score matrix and its own derived 1X2',
    'reconciliation':'none','discrepancy':'mean over matches and 3 classes of absolute probability difference; report percentage points, per-class means and mean total variation',
    'report_for':['pre2023 selection evidence','semiconfirmatory period after approval','72 frozen group forecasts']},
 'model_drift':'model coefficients fixed since training before 2023; update only Elo/form state; report each subperiod, no recalibration or refitting',
 'chronology':['explicit human approval','update causal state using only pre-2026-06-10 results',
    'generate 72 fixed-cutoff group forecasts, score matrices and all comparator forecasts',
    'validate probability mass and neutral symmetry to 1e-9, seal SHA256 and real UTC time',
    'commit and tag phase4-predictions-frozen','compute semiconfirmatory metrics',
    'load official World Cup results only after prediction commit and seal','compute descriptive World Cup evaluation','separate results/evaluation commit'],
 'input_timing_clarification':'pre-cutoff outcomes are necessary input BEFORE sealing the 72 forecasts; after approval, before evaluation; none of the World Cup outcomes are used in this state',
 'worldcup_evaluation':{'purpose':'descriptive only, never model selection','group_matches_expected':72,
    'small_sample':'report actual uncertainty; do not hard-code a standard error or assert models are indistinguishable without calculating it',
    'bootstrap':'paired calendar-date blocks, 2000 replicates, seed 20261012; sensitivity by match, report clustering limits and actual N',
    'knockouts':'separate, 90 minutes only, if available and verifiable; no automatic shootout-to-draw'},
 'git_tags':{'protocol':'phase4-protocol','predictions':'phase4-predictions-frozen','models':'models-selected'},
 'time_authority':'Git commit timestamps and timestamped hash seals; never filesystem modification times',
 'forbidden_mutations':'all reports/models_selected artifacts and the 5 protected source files'
}
write_json(OUTPUT/'protocol.json',protocol)
seal={'sealed_at_utc':utc_now(),'protocol_sha256':digest(OUTPUT/'protocol.json'),
      'base_models_commit':FROZEN_COMMIT,'commit_reference':'resolve phase4-protocol tag; a commit cannot contain its own hash',
      'explicit_approval_received':False,'post2022_metrics_computed':False}
write_json(OUTPUT/'protocol_seal.json',seal)
(OUTPUT/'chronology.jsonl').write_text(json.dumps({'at_utc':seal['sealed_at_utc'],'event':'protocol_sealed_awaiting_approval',
    'sha256':seal['protocol_sha256'],'models_commit':FROZEN_COMMIT},ensure_ascii=False)+'\n',encoding='utf-8')

# Probability-only calculation on the already frozen PRE-2023 validation rows.
left=pd.read_csv(ROOT/'reports/models_selected/predictions_logistic.csv')
right=pd.read_csv(ROOT/'reports/models_selected/predictions_poisson.csv')
keys=['date','home_team','away_team']
if not left[keys].equals(right[keys]):raise ValueError('Probability comparison keys differ')
if pd.to_datetime(left.date).max()>=pd.Timestamp('2023-01-01'):raise ValueError('Reserved outcomes in pre-2023 comparison')
cols=['p_home_win','p_draw','p_away_win']
delta=np.abs(left[cols].to_numpy()-right[cols].to_numpy())
discrepancy={'population':'frozen pre-2023 walk-forward selection, not final evaluation','matches':len(left),
    'mean_absolute_probability_difference':float(delta.mean()),'mean_difference_percentage_points':float(100*delta.mean()),
    'mean_class_difference_percentage_points':dict(zip(['victoria','empate','derrota'],(100*delta.mean(axis=0)).tolist())),
    'mean_total_variation':float(.5*delta.sum(axis=1).mean()),'computed_at_utc':utc_now(),'post2022_metrics_computed':False}
write_json(OUTPUT/'pre2023_product_discrepancy.json',discrepancy)
print(json.dumps({'integrity':checks,'protocol_seal':seal,'pre2023_discrepancy':discrepancy},ensure_ascii=False,indent=2))
