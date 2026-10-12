"""Evaluation math and metadata-only strata, using synthetic fixtures."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.final_evaluation import estimable,cluster_bootstrap,rps_values,stratum_masks


class FinalEvaluationTests(unittest.TestCase):
    def test_estimability_minimum_and_each_class(self):
        self.assertFalse(estimable(np.r_[np.zeros(139,int),np.ones(30,int),np.full(30,2)]))
        self.assertTrue(estimable(np.r_[np.zeros(140,int),np.ones(30,int),np.full(30,2)]))
        self.assertFalse(estimable(np.r_[np.zeros(171,int),np.ones(29,int),np.full(30,2)]))

    def test_monthly_and_quarterly_cluster_units(self):
        dates=pd.Series(pd.to_datetime(['2023-01-01','2023-02-01','2023-04-01']))
        q,nq=cluster_bootstrap(dates,[1,2,3],'Q')
        m,nm=cluster_bootstrap(dates,[1,2,3],'M')
        self.assertEqual((nq,nm),(2,3))
        self.assertEqual(q,cluster_bootstrap(dates,[1,2,3],'Q')[0])
        self.assertEqual(m,cluster_bootstrap(dates,[1,2,3],'M')[0])

    def test_rps_perfect_and_maximally_wrong_predictions(self):
        np.testing.assert_allclose(rps_values(np.array([0,1,2]),np.eye(3)),0)
        self.assertEqual(float(rps_values(np.array([0]),np.array([[0,0,1]]))[0]),1.)

    def test_strong_threshold_strict_and_not_duration_policy(self):
        frame=pd.DataFrame({'home_team':['A']*3,'away_team':['B']*3,'competitive':[True]*3,
             'competition_family':['qualification']*3,'elo_home':[1700,1701,1800],
             'elo_away':[1800,1701,1600],'shootout_record':[False]*3,'proven_extra_time_goals':[0]*3,
             'strict_duration_verified':[False,True,False],'goal_training_eligible':[True]*3})
        masks=stratum_masks(frame,['A','B'])
        self.assertEqual(masks['strong_teams'].tolist(),[False,True,False])
        self.assertEqual(masks['strict_duration'].tolist(),[False,True,False])


if __name__=='__main__':unittest.main()
