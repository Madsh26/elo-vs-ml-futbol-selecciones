"""Coherent score distributions, XGBoost and joint Dixon-Coles likelihood."""
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
from scipy.stats import poisson
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier, XGBRegressor
from .data import FEATURES

def dc_tau(h, a, lh, la, rho):
    h, a, lh, la = np.broadcast_arrays(h, a, lh, la)
    return np.where((h == 0) & (a == 0), 1-lh*la*rho,
           np.where((h == 0) & (a == 1), 1+lh*rho,
           np.where((h == 1) & (a == 0), 1+la*rho,
           np.where((h == 1) & (a == 1), 1-rho, 1.))))

def rho_bounds(lh, la):
    # Sufficient bounds for every low-score cell to be strictly positive.
    return (-.98/max(float(np.max(lh)), float(np.max(la)), 1e-6),
            min(.98, .98/float(np.max(lh*la))))

def score_matrix(lh, la, rho=0., tolerance=1e-9):
    if not (np.isfinite(lh) and np.isfinite(la) and lh > 0 and la > 0):
        raise ValueError('Goal intensities must be positive and finite')
    low, high = rho_bounds(np.array([lh]), np.array([la]))
    if not low <= rho <= high:
        raise ValueError('Invalid Dixon-Coles dependence for these rates')
    maximum = max(7, int(max(poisson.ppf(1-tolerance/2, lh),
                             poisson.ppf(1-tolerance/2, la))))
    goals = np.arange(maximum+1)
    raw = np.outer(poisson.pmf(goals, lh), poisson.pmf(goals, la))
    raw *= dc_tau(goals[:, None], goals[None, :], lh, la, rho)
    mass = raw.sum()
    assert np.all(raw >= 0) and 0 < mass <= 1+1e-10
    tail = max(0., 1-float(mass))
    return raw/mass, tail

def matrix_1x2(matrix):
    return np.array([np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum()])

def score_probabilities(lh, la, rho=0.):
    return np.vstack([matrix_1x2(score_matrix(x, y, rho)[0]) for x, y in zip(lh, la)])

def score_nll(h, a, lh, la, rho=0.):
    tau = dc_tau(h, a, lh, la, rho)
    if np.any(tau <= 0):
        raise ValueError('Negative probability in observed score likelihood')
    logp = h*np.log(lh)-lh-gammaln(h+1) + a*np.log(la)-la-gammaln(a+1)+np.log(tau)
    return -float(np.mean(logp))

def fit_rho(frame, lh, la):
    low, high = rho_bounds(lh, la)
    result = minimize_scalar(lambda r: score_nll(frame.home_score.to_numpy(),
                   frame.away_score.to_numpy(), lh, la, r),
                   bounds=(max(low, -.3), min(high, .3)), method='bounded')
    if not result.success:
        raise RuntimeError('Could not fit dependence')
    return float(result.x)

class DixonColes:
    def __init__(self, correction=True, half_life_days=1460):
        self.correction = correction
        self.half_life_days = half_life_days

    def fit(self, frame):
        self.teams = sorted(set(frame.home_team) | set(frame.away_team))
        self.lookup = {t: i for i, t in enumerate(self.teams)}
        n = len(self.teams)
        hi = frame.home_team.map(self.lookup).to_numpy()
        ai = frame.away_team.map(self.lookup).to_numpy()
        h, a = frame.home_score.to_numpy(), frame.away_score.to_numpy()
        venue = (frame.host_home-frame.host_away).to_numpy()
        weights = np.exp(-np.log(2)*(frame.date.max()-frame.date).dt.days.to_numpy()/self.half_life_days)
        weights /= weights.sum()
        # Sum-to-zero attack/defence vectors fix identifiability.
        def unpack(theta):
            attack = np.r_[theta[:n-1], -theta[:n-1].sum()]
            defence = np.r_[theta[n-1:2*n-2], -theta[n-1:2*n-2].sum()]
            intercept, home = theta[2*n-2:2*n]
            rho = theta[-1] if self.correction else 0.
            return attack, defence, intercept, home, rho
        def objective(theta):
            attack, defence, intercept, home, rho = unpack(theta)
            lh = np.exp(intercept+attack[hi]-defence[ai]+home*venue)
            la = np.exp(intercept+attack[ai]-defence[hi]-home*venue)
            tau = dc_tau(h, a, lh, la, rho)
            if not np.all(np.isfinite(lh+la)) or np.any(tau <= 0):
                return 1e10, np.zeros_like(theta)
            dlh = np.where((h==0)&(a==0), -la*rho,
                   np.where((h==0)&(a==1), rho, 0.))
            dla = np.where((h==0)&(a==0), -lh*rho,
                   np.where((h==1)&(a==0), rho, 0.))
            dr = np.where((h==0)&(a==0), -lh*la,
                 np.where((h==0)&(a==1), lh,
                 np.where((h==1)&(a==0), la,
                 np.where((h==1)&(a==1), -1., 0.))))
            logp = h*np.log(lh)-lh-gammaln(h+1)+a*np.log(la)-la-gammaln(a+1)+np.log(tau)
            gh = weights*(lh-h-dlh*lh/tau)
            ga = weights*(la-a-dla*la/tau)
            ridge = .002
            gat = np.bincount(hi, gh, minlength=n)+np.bincount(ai, ga, minlength=n)+2*ridge*attack
            gde = -np.bincount(ai, gh, minlength=n)-np.bincount(hi, ga, minlength=n)+2*ridge*defence
            grad = np.r_[gat[:-1]-gat[-1], gde[:-1]-gde[-1],
                         (gh+ga).sum(), ((gh-ga)*venue).sum()]
            if self.correction:
                grad = np.r_[grad, -np.sum(weights*dr/tau)]
            return -np.sum(weights*logp)+ridge*(attack@attack+defence@defence), grad
        initial = np.zeros(2*n+(1 if self.correction else 0))
        initial[2*n-2] = np.log((h.mean()+a.mean())/2)
        bounds = [(None, None)]*(2*n-2)+[(-2, 2), (-.5, .5)]
        if self.correction:
            bounds += [(-.25, .25)]
        result = minimize(objective, initial, jac=True, method='L-BFGS-B',
                          bounds=bounds, options={'maxiter': 250, 'ftol': 1e-9})
        self.optimization = {'success': bool(result.success), 'message': str(result.message),
                             'iterations': int(result.nit)}
        self.attack, self.defence, self.intercept, self.home, self.rho = unpack(result.x)
        if not result.success:
            raise RuntimeError(f'Dixon-Coles fitting failed: {result.message}')
        return self

    def rates(self, frame):
        def params(team, values):
            return values[self.lookup[team]] if team in self.lookup else 0.
        ah = np.array([params(t, self.attack) for t in frame.home_team])
        aa = np.array([params(t, self.attack) for t in frame.away_team])
        dh = np.array([params(t, self.defence) for t in frame.home_team])
        da = np.array([params(t, self.defence) for t in frame.away_team])
        venue = (frame.host_home-frame.host_away).to_numpy()
        return (np.exp(self.intercept+ah-da+self.home*venue),
                np.exp(self.intercept+aa-dh-self.home*venue))

def fit_classifier(train, valid, rounds=180, threads=2):
    model = XGBClassifier(objective='multi:softprob', num_class=3,
        n_estimators=rounds, max_depth=3, learning_rate=.05, min_child_weight=8,
        subsample=.85, colsample_bytree=.9, reg_lambda=3, tree_method='hist',
        n_jobs=threads, random_state=2026, eval_metric='mlogloss', early_stopping_rounds=20)
    model.fit(train[FEATURES], train.target,
              eval_set=[(valid[FEATURES], valid.target)], verbose=False)
    return model

def fit_goals(train, valid, rounds=180, threads=2):
    models = []
    for target in ['home_score', 'away_score']:
        model = XGBRegressor(objective='count:poisson', n_estimators=rounds,
            max_depth=3, learning_rate=.05, min_child_weight=8, subsample=.85,
            colsample_bytree=.9, reg_lambda=3, tree_method='hist', n_jobs=threads,
            random_state=2026, eval_metric='poisson-nloglik', early_stopping_rounds=20)
        model.fit(train[FEATURES], train[target],
                  eval_set=[(valid[FEATURES], valid[target])], verbose=False)
        models.append(model)
    return models

def goal_rates(models, frame):
    return tuple(m.predict(frame[FEATURES]).astype(float) for m in models)

class Temperature:
    """One scalar learned on a separate temporal calibration block."""
    def fit(self, probabilities, target):
        from sklearn.metrics import log_loss
        result = minimize_scalar(lambda t: log_loss(target, self.apply(probabilities, t), labels=[0,1,2]),
                                 bounds=(.5, 3.), method='bounded')
        self.value = float(result.x)
        return self

    def apply(self, probabilities, value=None):
        value = self.value if value is None else value
        logits = np.log(np.maximum(probabilities, 1e-12))/value
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p/p.sum(axis=1, keepdims=True)
