import sys
from pathlib import Path
import unittest
import os
from types import SimpleNamespace
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'.deps'))
from football_forecast.models import score_matrix, matrix_1x2, dc_tau, score_nll
from football_forecast.data import load_local, build_features, HistoryState, FEATURES

class ProbabilityTests(unittest.TestCase):
    def test_mass_and_swap_symmetry(self):
        for h,a,r in [(1.4,.9,-.08),(.2,4.,0),(5.,6.,.01)]:
            m,tail = score_matrix(h,a,r)
            reverse,_ = score_matrix(a,h,r)
            self.assertAlmostEqual(m.sum(),1)
            self.assertLess(tail,1e-8)
            np.testing.assert_allclose(m,reverse.T)
            p=matrix_1x2(m)
            np.testing.assert_allclose(p,matrix_1x2(reverse)[::-1])

    def test_dc_only_four_cells(self):
        self.assertEqual(dc_tau(2,1,1.5,1.,-.1),1)
        self.assertGreater(dc_tau(0,0,1.5,1.,-.1),1)
        self.assertGreater(dc_tau(1,1,1.5,1.,-.1),1)
        self.assertLess(dc_tau(1,0,1.5,1.,-.1),1)
        with self.assertRaises(ValueError):
            score_matrix(5.,2.,-.3)

    def test_same_day_and_future_do_not_leak(self):
        history=pd.DataFrame([
            {'date':pd.Timestamp('2020-01-01'),'home_team':'A','away_team':'B','home_score':1,'away_score':0,'country':'X','neutral':True,'tournament':'Friendly'},
            {'date':pd.Timestamp('2020-01-01'),'home_team':'A','away_team':'C','home_score':0,'away_score':0,'country':'X','neutral':True,'tournament':'Friendly'},
            {'date':pd.Timestamp('2020-01-02'),'home_team':'A','away_team':'B','home_score':0,'away_score':2,'country':'X','neutral':True,'tournament':'Friendly'}])
        fixture=history.iloc[[2]].drop(columns=['home_score','away_score'])
        first,_,_=build_features(history,fixture)
        changed=history.copy()
        changed.loc[2,'home_score']=20
        second,_,_=build_features(changed,fixture)
        np.testing.assert_allclose(first[FEATURES],second[FEATURES])
        self.assertEqual(first.iloc[0].games_home,first.iloc[1].games_home)
        changed.loc[0,'home_score']=20
        third,_,_=build_features(changed,fixture)
        np.testing.assert_allclose(first.iloc[:2][FEATURES],third.iloc[:2][FEATURES])
        self.assertNotEqual(first.iloc[2].gf5_home,third.iloc[2].gf5_home)

@unittest.skipUnless((ROOT/'data/raw/international_results_baseline.zip').exists(), 'Local archives are not distributed in Git')
class LocalDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history,cls.fixtures,cls.audit=load_local(ROOT,'2023-01-01')

    def test_fixture_resolution(self):
        self.assertEqual(len(self.fixtures),72)
        self.assertEqual(self.fixtures[['home_team','away_team']].stack().nunique(),48)
        self.assertFalse(self.fixtures[['home_team','away_team']].stack().str.contains('Playoff').any())
        self.assertIsNone(self.audit['worldcup_2026_scored_rows'])
        self.assertLess(self.history.date.max(),pd.Timestamp('2023-01-01'))

    def test_final_2022_regulation_score(self):
        row=self.history[(self.history.date==pd.Timestamp('2022-12-18')) &
                         (self.history.home_team=='Argentina')].iloc[0]
        self.assertEqual((row.home_score,row.away_score),(2,2))

@unittest.skipUnless((ROOT/'reports/probabilistic/match_probabilities.csv').exists(), 'Run pipeline first')
class ExportTests(unittest.TestCase):
    def test_exported_probabilities_and_team_perspectives(self):
        out=ROOT/'reports/probabilistic'
        matches=pd.read_csv(out/'match_probabilities.csv')
        for _,block in matches.groupby('model'):
            self.assertEqual(len(block),72)
            np.testing.assert_allclose(block[['p_home_win','p_draw','p_away_win']].sum(axis=1),1,atol=1e-7)
        teams=pd.read_csv(out/'team_match_probabilities.csv')
        for _,block in teams.groupby(['model','match_id']):
            self.assertEqual(len(block),2)
            self.assertAlmostEqual(block.iloc[0].p_win,block.iloc[1].p_loss)
            self.assertAlmostEqual(block.iloc[0].p_draw,block.iloc[1].p_draw)
        scores=pd.read_csv(out/'scoreline_probabilities.csv')
        np.testing.assert_allclose(scores.groupby(['model','match_id']).probability.sum(),1,atol=1e-10)
        self.assertTrue((scores.probability>=0).all())

    @unittest.skipUnless(os.environ.get('ALLOW_RESERVED_EVALUATION')=='1',
                         'Baseline reproduction using reserved results is deferred to Phase 4')
    def test_saved_model_reproduces_fixture(self):
        import joblib
        from football_forecast.models import goal_rates, score_probabilities
        out=ROOT/'reports/probabilistic'
        bundle=joblib.load(out/'models/deployment.joblib')
        history,fixtures,_=load_local(ROOT,bundle['cutoff'])
        _,future,_=build_features(history,fixtures)
        rates=goal_rates(bundle['goal_models'],future)
        predicted=score_probabilities(*rates)
        saved=pd.read_csv(out/'match_probabilities.csv')
        saved=saved[saved.model=='xgboost_poisson']
        np.testing.assert_allclose(predicted,saved[['p_home_win','p_draw','p_away_win']],atol=1e-10)

if __name__=='__main__':
    unittest.main()
