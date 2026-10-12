import argparse
import json
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss, accuracy_score, f1_score, confusion_matrix
from .data import load_local, build_features, FEATURES
from .models import (DixonColes, fit_classifier, fit_goals, goal_rates,
                     fit_rho, score_probabilities, score_nll, score_matrix,
                     matrix_1x2, Temperature)
from .report import write_report

def evaluate(frame, probabilities, rates=None, rho=0.):
    probabilities = np.asarray(probabilities)
    assert np.isfinite(probabilities).all() and np.all(probabilities >= 0)
    assert np.allclose(probabilities.sum(axis=1), 1)
    y = frame.target.to_numpy()
    onehot = np.eye(3)[y]
    label = probabilities.argmax(axis=1)
    result = {'n_matches': len(frame), 'log_loss': float(log_loss(y, probabilities, labels=[0,1,2])),
              'brier_multiclass_unscaled': float(np.mean(np.sum((probabilities-onehot)**2, axis=1))),
              'accuracy': float(accuracy_score(y, label)),
              'f1_macro': float(f1_score(y, label, labels=[0,1,2], zero_division=0, average='macro')),
              'actual_draw_rate': float(np.mean(y == 1)),
              'mean_draw_probability': float(probabilities[:,1].mean()),
              'predicted_draw_label_rate': float(np.mean(label == 1)),
              'score_nll': None}
    if rates is not None:
        result['score_nll'] = score_nll(frame.home_score.to_numpy(), frame.away_score.to_numpy(), *rates, rho)
    return result

def refit(model, frame, target):
    # Reuse the early-stopping choice; no hyperparameter search on final test.
    estimator = clone(model).set_params(early_stopping_rounds=None,
                                       n_estimators=model.best_iteration+1)
    estimator.fit(frame[FEATURES], frame[target], verbose=False)
    return estimator

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path('.'))
    parser.add_argument('--output-dir', type=Path, default=Path('reports/probabilistic'))
    parser.add_argument('--cutoff', default='2026-06-10')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--rounds', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.threads <= 4:
        parser.error('Use 1-4 threads for the local CPU budget')
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    modeldir = out / 'models'
    modeldir.mkdir(exist_ok=True)
    started = time.perf_counter()
    print('Loading local archives; no scraping...', flush=True)
    history, fixtures, manifest = load_local(args.data_dir, args.cutoff)
    frame, future, state = build_features(history, fixtures)
    frame = frame[frame.date >= '2010-01-01'].reset_index(drop=True)
    assert frame.date.max() < pd.Timestamp(args.cutoff)
    splits = {
        'train': frame[frame.date < '2018-01-01'],
        'early_stop': frame[(frame.date >= '2018-01-01') & (frame.date < '2020-01-01')],
        'dependence': frame[(frame.date >= '2020-01-01') & (frame.date < '2022-01-01')],
        'selection_calibration': frame[(frame.date >= '2022-01-01') & (frame.date < '2023-01-01')],
        'test': frame[frame.date >= '2023-01-01'],
    }
    if any(len(v) < 30 for v in splits.values()):
        raise ValueError('Insufficient history for the requested temporal splits')
    train, valid, dep, selection, test = (splits[k] for k in splits)
    manifest['splits'] = {k: {'rows': len(v), 'from': str(v.date.min().date()),
                             'through': str(v.date.max().date())} for k,v in splits.items()}
    print('Temporal splits:', {k: len(v) for k,v in splits.items()}, flush=True)
    print('Fitting statistical references and XGBoost (CPU budget)...', flush=True)
    timings = {}
    t = time.perf_counter()
    logistic = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=600))
    logistic.fit(train[FEATURES], train.target)
    timings['logistic'] = time.perf_counter()-t
    t = time.perf_counter()
    poisson = DixonColes(correction=False).fit(train)
    timings['poisson'] = time.perf_counter()-t
    t = time.perf_counter()
    dc = DixonColes(correction=True).fit(train)
    timings['dixon_coles'] = time.perf_counter()-t
    t = time.perf_counter()
    classifier = fit_classifier(train, valid, args.rounds, args.threads)
    timings['xgboost_1x2'] = time.perf_counter()-t
    t = time.perf_counter()
    goal_models = fit_goals(train, valid, args.rounds, args.threads)
    timings['xgboost_poisson'] = time.perf_counter()-t
    rho = fit_rho(dep, *goal_rates(goal_models, dep))
    temperature = Temperature().fit(classifier.predict_proba(selection[FEATURES]), selection.target)
    models = ['logistic', 'poisson', 'dixon_coles', 'xgboost_1x2',
              'xgboost_1x2_temperature', 'xgboost_poisson', 'xgboost_dixon_coles']
    def predict(name, block):
        if name == 'logistic':
            return logistic.predict_proba(block[FEATURES]), None, 0.
        if name.startswith('xgboost_1x2'):
            p = classifier.predict_proba(block[FEATURES])
            return (temperature.apply(p) if name.endswith('temperature') else p), None, 0.
        estimator = poisson if name == 'poisson' else dc if name == 'dixon_coles' else goal_models
        rates = estimator.rates(block) if isinstance(estimator, DixonColes) else goal_rates(estimator, block)
        correction = dc.rho if name == 'dixon_coles' else rho if name == 'xgboost_dixon_coles' else 0.
        return score_probabilities(*rates, correction), rates, correction
    metrics = []
    probabilities = {}
    for split_name, block in [('selection_calibration', selection), ('test', test)]:
        for name in models:
            p, rates, r = predict(name, block)
            result = evaluate(block, p, rates, r)
            metrics.append({'model': name, 'split': split_name, **result,
                            'fit_seconds': timings.get(name, timings.get('xgboost_1x2' if '1x2' in name else 'xgboost_poisson'))})
            if split_name == 'test':
                probabilities[name] = p
    metrics = pd.DataFrame(metrics)
    # Choose by 2022 score likelihood only; final test is descriptive, never selection.
    score_candidates = ['poisson', 'dixon_coles', 'xgboost_poisson', 'xgboost_dixon_coles']
    sel = metrics[(metrics.split == 'selection_calibration') & metrics.model.isin(score_candidates)]
    selected = sel.sort_values('score_nll').iloc[0].model
    metrics.to_csv(out / 'model_comparison.csv', index=False)
    test_export = test[['date','home_team','away_team','home_score','away_score','target']].copy()
    for name, p in probabilities.items():
        for idx,label in enumerate(['home_win','draw','away_win']):
            test_export[f'{name}_{label}'] = p[:,idx]
    test_export.to_csv(out / 'backtest_predictions.csv', index=False)
    print(f'Score model selected using 2022: {selected}. Final test kept separate.', flush=True)
    print('Refitting deployment models on all eligible history...', flush=True)
    full_classifier = refit(classifier, frame, 'target')
    full_goals = [refit(m, frame, target) for m,target in zip(goal_models, ['home_score','away_score'])]
    full_poisson = DixonColes(correction=False).fit(frame)
    full_dc = DixonColes(correction=True).fit(frame)
    # Deployment calibration uses genuine out-of-time predictions, not fitted residuals.
    # It may include the archived test years AFTER the frozen benchmark is saved.
    oof_blocks, oof_lh, oof_la, oof_class = [], [], [], []
    for boundary, end in [('2022-01-01','2025-01-01'), ('2025-01-01',args.cutoff)]:
        prefix = frame[frame.date < boundary]
        block = frame[(frame.date >= boundary) & (frame.date < end)]
        gm = [refit(m, prefix, target) for m,target in zip(goal_models, ['home_score','away_score'])]
        cm = refit(classifier, prefix, 'target')
        lh,la = goal_rates(gm, block)
        oof_blocks.append(block)
        oof_lh.extend(lh)
        oof_la.extend(la)
        oof_class.extend(cm.predict_proba(block[FEATURES]))
    oof = pd.concat(oof_blocks)
    full_rho = fit_rho(oof, np.array(oof_lh), np.array(oof_la))
    full_temperature = Temperature().fit(np.array(oof_class), oof.target)
    future_rates = {
        'poisson': full_poisson.rates(future), 'dixon_coles': full_dc.rates(future),
        'xgboost_poisson': goal_rates(full_goals, future),
    }
    future_rates['xgboost_dixon_coles'] = future_rates['xgboost_poisson']
    corrections = {'poisson': 0., 'dixon_coles': full_dc.rho,
                   'xgboost_poisson': 0., 'xgboost_dixon_coles': full_rho}
    rows, team_rows, scores = [], [], []
    for name in score_candidates:
        lh,la = future_rates[name]
        for idx, match in enumerate(future.itertuples(index=False)):
            matrix, tail = score_matrix(lh[idx], la[idx], corrections[name])
            p = matrix_1x2(matrix)
            top = np.dstack(np.unravel_index(np.argsort(matrix, axis=None)[::-1][:5], matrix.shape))[0]
            base = {'match_id': match.match_id, 'group': match.group,
                    'date_utc': match.date_utc, 'home_team': match.home_team,
                    'away_team': match.away_team, 'model': name,
                    'prediction_cutoff': args.cutoff, 'target_minutes': 90}
            rows.append({**base, 'p_home_win': p[0], 'p_draw': p[1], 'p_away_win': p[2],
                         'expected_home_goals': lh[idx], 'expected_away_goals': la[idx],
                         'tail_mass_omitted': tail, 'selected_score_model': name == selected,
                         'top_scorelines': '; '.join(f'{h}-{a}: {matrix[h,a]:.6f}' for h,a in top)})
            for team,rival,win,loss in [(match.home_team,match.away_team,p[0],p[2]),
                                        (match.away_team,match.home_team,p[2],p[0])]:
                team_rows.append({**base, 'team': team, 'opponent': rival,
                                  'p_win': win, 'p_draw': p[1], 'p_loss': loss})
            for h in range(matrix.shape[0]):
                for a in range(matrix.shape[1]):
                    scores.append({**base, 'home_goals': h, 'away_goals': a,
                                   'probability': matrix[h,a]})
    match_probs = pd.DataFrame(rows)
    xp = full_classifier.predict_proba(future[FEATURES])
    for name,p in [('xgboost_1x2',xp),('xgboost_1x2_temperature',full_temperature.apply(xp))]:
        extra = future[['match_id','group','date_utc','home_team','away_team']].copy()
        extra['model'] = name
        extra['prediction_cutoff'] = args.cutoff
        extra['target_minutes'] = 90
        extra['selected_score_model'] = False
        extra[['p_home_win','p_draw','p_away_win']] = p
        match_probs = pd.concat([match_probs,extra], ignore_index=True)
    match_probs.to_csv(out / 'match_probabilities.csv', index=False)
    teams = pd.DataFrame(team_rows)
    teams.to_csv(out / 'team_match_probabilities.csv', index=False)
    pd.DataFrame(scores).to_csv(out / 'scoreline_probabilities.csv', index=False)
    summary = teams[teams.model == selected].groupby('team').agg(
        matches=('match_id','count'), average_p_win=('p_win','mean'),
        average_p_draw=('p_draw','mean'), average_p_loss=('p_loss','mean')).reset_index()
    summary['meaning'] = 'Equal-weight average over the three scheduled group opponents; not tournament qualification probability.'
    summary.to_csv(out / 'team_summary.csv', index=False)
    fixture_export = future[['match_id','group','date_utc','home_team','away_team','country','neutral']]
    fixture_export.to_csv(out / 'resolved_fixtures.csv', index=False)
    importances = pd.DataFrame({'feature': FEATURES, 'classifier_gain_importance': full_classifier.feature_importances_,
                                'home_goals_gain_importance': full_goals[0].feature_importances_,
                                'away_goals_gain_importance': full_goals[1].feature_importances_})
    importances.to_csv(out / 'feature_importance.csv', index=False)
    # Interpretation of held-out predictions; shuffle columns without refitting.
    permutation = []
    rng = np.random.default_rng(2026)
    sample = test.sample(n=min(500,len(test)), random_state=2026)
    baseline = log_loss(sample.target, classifier.predict_proba(sample[FEATURES]), labels=[0,1,2])
    for feature in FEATURES:
        x = sample[FEATURES].copy()
        x[feature] = rng.permutation(x[feature].to_numpy())
        loss = log_loss(sample.target, classifier.predict_proba(x), labels=[0,1,2])
        permutation.append({'feature': feature, 'log_loss_increase': loss-baseline})
    pd.DataFrame(permutation).to_csv(out / 'permutation_importance.csv', index=False)
    bundle = {'features': FEATURES, 'classifier': full_classifier, 'goal_models': full_goals,
              'poisson': full_poisson, 'dc': full_dc, 'rho': full_rho,
              'temperature': full_temperature, 'selected_model': selected,
              'state': state, 'cutoff': args.cutoff}
    # HistoryState contains default factories; store plain dictionaries instead.
    bundle['state'] = {'elo': dict(state.elo), 'games': dict(state.games),
                       'recent': {k:list(v) for k,v in state.recent.items()}}
    joblib.dump(bundle, modeldir / 'deployment.joblib')
    from importlib.metadata import version
    manifest.update(runtime_versions={name: version(name) for name in
                    ['numpy','pandas','scipy','scikit-learn','xgboost','matplotlib','joblib']},
                    optimizer_diagnostics={'poisson': full_poisson.optimization,
                                           'dixon_coles': full_dc.optimization},
                    selected_score_model=selected, benchmark_rho=rho,
                    deployment_hybrid_rho=full_rho, deployment_dc_rho=full_dc.rho,
                    deployment_temperature=full_temperature.value,
                    threads=args.threads, boosting_rounds_max=args.rounds,
                    chosen_classifier_rounds=classifier.best_iteration+1,
                    chosen_goal_rounds=[m.best_iteration+1 for m in goal_models],
                    simulations=0, elapsed_seconds=time.perf_counter()-started,
                    test_protocol='Frozen parameters; features updated from earlier verified results. Deployment refit and OOF calibration occur after benchmark archival; deployment predictions are not held-out benchmark predictions.',
                    calibration_selection_note='Temperature fitted in 2022; its 2022 loss is not an independent validation score. Final test remains separate.',
                    deployment_oof_boundaries=['2022-01-01','2025-01-01'])
    (out / 'data_audit.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    write_report(out, match_probs, teams, metrics, test, probabilities, manifest)
    print(metrics[metrics.split=='test'][['model','log_loss','brier_multiclass_unscaled','score_nll']].to_string(index=False), flush=True)
    print(f'Done: {out.resolve()} ({manifest["elapsed_seconds"]:.1f}s; zero tournament simulations)', flush=True)
