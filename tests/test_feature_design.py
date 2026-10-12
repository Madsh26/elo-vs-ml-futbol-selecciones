import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.elo_calibration import (EloParameters,causal_elo,backward_rank_join,
                                               symmetric_predictions,block_interval)
from football_forecast.context_features import squad_proxy_asof,coverage_weights,venue_sign

class FeatureDesignTests(unittest.TestCase):
    def test_ranking_join_is_past_only_and_expires(self):
        matches=pd.DataFrame({'date':pd.to_datetime(['2020-07-01','2020-07-02','2020-09-29','2020-09-30']),
                              'home_team':['A']*4,'away_team':['B']*4})
        rankings=pd.DataFrame({'team':['A','B'],'available_date':pd.to_datetime(['2020-07-01']*2),
                               'rank':[1,2],'points':[100,80]})
        joined=backward_rank_join(matches,rankings)
        self.assertTrue(pd.isna(joined.iloc[0].fifa_rank_home))
        self.assertEqual(joined.iloc[1].fifa_rank_home,1)
        self.assertEqual(joined.iloc[2].fifa_rank_home,1)
        self.assertTrue(pd.isna(joined.iloc[3].fifa_rank_home))

    def history(self):
        return pd.DataFrame({'date':pd.to_datetime(['2020-01-01','2020-01-01','2020-01-02']),
          'home_team':['A','A','A'],'away_team':['B','C','B'],'country':['X']*3,'neutral':[True]*3,
          'elo_home_score':[2,1,1],'elo_away_score':[0,0,0],'competition_family':['friendly']*3})

    def test_elo_same_day_and_future_causality(self):
        history=self.history()
        first,_=causal_elo(history,EloParameters())
        altered=history.copy(); altered.loc[1,'elo_home_score']=8
        second,_=causal_elo(altered,EloParameters())
        np.testing.assert_allclose(first.iloc[:2][['elo_home','elo_away']],second.iloc[:2][['elo_home','elo_away']])
        self.assertNotEqual(first.iloc[2].elo_home,second.iloc[2].elo_home)

    def test_initial_rating_translation_is_unidentifiable(self):
        first,_=causal_elo(self.history(),EloParameters(initial=1400))
        second,_=causal_elo(self.history(),EloParameters(initial=1600))
        np.testing.assert_allclose(first.elo_diff,second.elo_diff,atol=1e-9)

    def test_prediction_symmetry_and_probability_mass(self):
        train=pd.DataFrame({'x':[-2,-1,0,1,2,3],'target':[2,2,1,0,0,0]})
        test=pd.DataFrame({'x':[.72,-.72]})
        probabilities=symmetric_predictions(train,test,['x'],[-1])
        np.testing.assert_allclose(probabilities[0],probabilities[1,::-1],atol=1e-9,rtol=0)
        np.testing.assert_allclose(probabilities.sum(axis=1),1,atol=1e-12)

    def test_block_interval_is_reproducible(self):
        dates=pd.Series(pd.date_range('2018-01-01',periods=20,freq='MS'))
        self.assertEqual(block_interval(dates,np.arange(20)),block_interval(dates,np.arange(20)))

    def test_market_values_and_membership_are_strictly_prior(self):
        members=pd.DataFrame({'player_id':[1,2,3],'team':['A']*3,
                              'date':pd.to_datetime(['2020-01-01','2020-02-01','2020-03-01'])})
        values=pd.DataFrame({'player_id':[1,1,2],'date':pd.to_datetime(['2019-01-01','2020-02-01','2019-12-01']),
                             'market_value_in_eur':[10,999999,50]})
        proxy=squad_proxy_asof('A','2020-02-01',members,values)
        self.assertEqual(proxy['top23_value_sum'],10)
        self.assertEqual(proxy['observed_international_players_730d'],1)
        self.assertTrue(np.isnan(squad_proxy_asof('B','2020-02-01',members,values)['top23_value_sum']))

    def test_coverage_weights_reject_future_history(self):
        history=self.history()
        with self.assertRaises(ValueError):
            coverage_weights(history,history,{'A':'UEFA','B':'CAF','C':'CAF'},'2020-01-02')
        weights=coverage_weights(history,history,{'A':'UEFA','B':'CAF','C':'CAF'},'2021-01-01')
        np.testing.assert_allclose(weights,1)

    def test_venue_sign_accepts_numeric_flags_and_respects_team_order(self):
        frame=pd.DataFrame({'neutral':[1.,0.,0.],'home_team':['A','A','B'],
                            'away_team':['B','B','A'],'country':['A']*3})
        self.assertEqual(venue_sign(frame).tolist(),[0,1,-1])
        with self.assertRaises(ValueError):
            venue_sign(frame.assign(neutral=np.nan))

@unittest.skipUnless((ROOT/'reports/feature_design/context_audit.json').exists() and
                     (ROOT/'reports/feature_design/historical_features.csv').exists(),'Local executed feature artifacts required')
class ExecutedFeatureTests(unittest.TestCase):
    def test_reserved_results_not_admitted(self):
        frame=pd.read_csv(ROOT/'reports/feature_design/historical_features.csv',usecols=['date'])
        self.assertTrue((pd.to_datetime(frame.date)<pd.Timestamp('2023-01-01')).all())
        fixture=pd.read_csv(ROOT/'reports/feature_design/fixture_features.csv')
        self.assertEqual(len(fixture),72)
        self.assertTrue(fixture.historical_state_pending_phase4.all())
        self.assertTrue(fixture.elo_home.isna().all())
        self.assertTrue(fixture.fifa_rank_home.isna().all())
        self.assertNotIn('host_away',fixture.columns)

    def test_protocol_precedes_selection_and_outputs_are_aligned(self):
        import json
        folder=ROOT/'reports/feature_design'
        protocol=json.loads((folder/'elo_protocol.json').read_text(encoding='utf-8'))
        selection=json.loads((folder/'selected_elo.json').read_text(encoding='utf-8'))
        self.assertLess(pd.Timestamp(protocol['written_at_utc']),pd.Timestamp(selection['selection_completed_at_utc']))
        baseline=pd.read_csv(folder/'elo_walk_forward_predictions.csv')
        ranking=pd.read_csv(folder/'fifa_walk_forward_predictions.csv')
        pd.testing.assert_frame_equal(baseline[['date','home_team','away_team']],ranking[['date','home_team','away_team']])
        self.assertTrue((pd.to_datetime(baseline.date)<'2023-01-01').all())

if __name__=='__main__': unittest.main()
