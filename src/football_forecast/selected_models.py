"""Small, reproducible candidates with explicit role reconciliation."""
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit, gammaln
from scipy.stats import skellam
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier, XGBRegressor


class ResultModel:
    def __init__(self, kind, signs):
        self.kind = kind
        self.signs = np.asarray(signs)

    def fit(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=int)
        xx = np.vstack([x, x*self.signs])
        yy = np.r_[y, 2-y]
        if self.kind == 'frequency':
            self.prob = (np.bincount(yy, minlength=3)+1)/(len(yy)+3)
        elif self.kind == 'ordinal':
            def probabilities(theta, z):
                slope, width = theta[0], np.exp(theta[1])
                away = expit(-width-slope*z)
                home = expit(slope*z-width)
                return np.column_stack([home, 1-away-home, away])
            result = minimize(lambda t: -np.log(np.clip(probabilities(t, xx[:, 0])[np.arange(len(yy)), yy], 1e-15, 1)).mean(),
                              [1., 0.], method='L-BFGS-B', bounds=[(0, 10), (-5, 3)])
            if not result.success:
                raise RuntimeError(str(result.message))
            self.theta = result.x
        else:
            if self.kind == 'xgboost':
                self.model = XGBClassifier(n_estimators=160, max_depth=2, learning_rate=.04,
                    min_child_weight=20, reg_lambda=5, subsample=1, colsample_bytree=1,
                    objective='multi:softprob', eval_metric='mlogloss', n_jobs=2,
                    tree_method='hist', random_state=20261012)
            else:
                self.model = LogisticRegression(C=1, max_iter=500)
            self.model.fit(xx, yy)
        return self

    def raw(self, x):
        if self.kind == 'frequency':
            return np.tile(self.prob, (len(x), 1))
        if self.kind == 'ordinal':
            slope, width = self.theta[0], np.exp(self.theta[1])
            away = expit(-width-slope*x[:, 0])
            home = expit(slope*x[:, 0]-width)
            return np.column_stack([home, 1-away-home, away])
        return self.model.predict_proba(x)

    def predict_proba(self, x):
        x = np.asarray(x, dtype=float)
        p = (np.asarray(self.raw(x),dtype=float)+np.asarray(self.raw(x*self.signs),dtype=float)[:, ::-1])/2
        return p/p.sum(axis=1, keepdims=True)


def effective_rho(lh, la, rho):
    """Keep all four corrected cells positive, for each match independently."""
    return np.clip(rho, -.98/np.maximum(lh, la), np.minimum(.98, .98/(lh*la)))


def tau(h, a, lh, la, rho):
    rho = effective_rho(lh, la, rho)
    return np.where((h == 0)&(a == 0), 1-lh*la*rho,
           np.where((h == 0)&(a == 1), 1+lh*rho,
           np.where((h == 1)&(a == 0), 1+la*rho,
           np.where((h == 1)&(a == 1), 1-rho, 1.))))


def score_losses(h, a, lh, la, rho=0.):
    return lh-h*np.log(lh)+gammaln(h+1)+la-a*np.log(la)+gammaln(a+1)-np.log(tau(h,a,lh,la,rho))


def rates_to_1x2(lh, la, rho=0.):
    # Infinite-support Poisson sums: no truncated score grid in evaluation.
    p = np.column_stack([skellam.sf(0, lh, la), skellam.pmf(0, lh, la), skellam.cdf(-1, lh, la)])
    correction = np.exp(-lh-la)*lh*la*effective_rho(lh,la,rho)
    p += np.column_stack([correction, -2*correction, correction])
    if np.any(p < -1e-12) or not np.all(np.isfinite(p)):
        raise ValueError('Invalid score distribution')
    p = np.maximum(p, 0)
    return p/p.sum(axis=1, keepdims=True)


class GoalModel:
    def __init__(self, kind, signs):
        self.kind = kind
        self.signs = np.asarray(signs)
        self.rho = 0.

    def fit(self, x, h, a):
        x = np.asarray(x, dtype=float)
        h, a = np.asarray(h, dtype=float), np.asarray(a, dtype=float)
        xx = np.vstack([x, x*self.signs])
        yy = np.r_[h, a]
        if self.kind == 'xgboost_poisson':
            self.model = XGBRegressor(objective='count:poisson', n_estimators=160, max_depth=2,
                learning_rate=.04, min_child_weight=20, reg_lambda=5, subsample=1,
                colsample_bytree=1, tree_method='hist', n_jobs=2, random_state=20261012)
            self.model.fit(xx, yy)
        else:
            design = np.column_stack([np.ones(len(xx)), xx])
            def loss(t):
                lograte = np.clip(design@t, -6, np.log(12))
                rate = np.exp(lograte)
                return np.mean(rate-yy*lograte)+.001*np.sum(t[1:]**2)
            initial = np.r_[np.log(max(yy.mean(), .01)), np.zeros(x.shape[1])]
            result = minimize(loss, initial, method='L-BFGS-B', options={'maxiter': 300, 'ftol': 1e-10})
            if not result.success:
                raise RuntimeError(str(result.message))
            self.coef = result.x
            if self.kind == 'dixon_coles':
                # Joint count likelihood, using the independent fit only as initialization.
                def joint(t):
                    self.coef = t[:-1]
                    lh, la = self.rates(x)
                    return score_losses(h,a,lh,la,t[-1]).mean()+.001*np.sum(t[1:-1]**2)
                result = minimize(joint, np.r_[self.coef, -.03], method='L-BFGS-B',
                                  bounds=[(None,None)]*len(self.coef)+[(-.3,.3)],
                                  options={'maxiter': 300, 'ftol': 1e-10})
                if not result.success:
                    raise RuntimeError(str(result.message))
                self.coef, self.rho = result.x[:-1], float(result.x[-1])
        return self

    def raw_rate(self, x):
        if self.kind == 'xgboost_poisson':
            return np.clip(self.model.predict(x).astype(float), np.exp(-6), 12)
        return np.exp(np.clip(self.coef[0]+x@self.coef[1:], -6, np.log(12)))

    def rates(self, x):
        x = np.asarray(x, dtype=float)
        return self.raw_rate(x), self.raw_rate(x*self.signs)

    def predict_proba(self, x):
        return rates_to_1x2(*self.rates(x), self.rho)
