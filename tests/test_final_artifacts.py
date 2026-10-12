"""Executed, post-approval artifacts; never fit or choose a candidate."""
from pathlib import Path
import sys
import json
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'src'),str(ROOT/'.deps')]
from run_final_evaluation import check_prediction_commit
from verify_final_evaluation import frozen_checks,protocol_checks


@unittest.skipUnless((ROOT/'reports/final_evaluation/worldcup_conclusion.json').exists(),'Executed final evaluation artifacts required')
class ExecutedFinalTests(unittest.TestCase):
    def test_protocol_conditions_and_prediction_commit_are_preserved(self):
        frozen_checks();protocol_checks(True);check_prediction_commit()
        protocol=json.loads((ROOT/'reports/final_evaluation/protocol_approved.json').read_text(encoding='utf-8'))
        self.assertEqual(protocol['estimability']['minimum_matches'],200)
        self.assertEqual(protocol['estimability']['minimum_events_each_class'],30)
        self.assertEqual(protocol['uncertainty']['monthly_sensitivity']['bootstrap_replicates'],2000)

    def test_source_crosswalk_covers_all_72_without_score_disagreement(self):
        comparison=pd.read_csv(ROOT/'reports/final_evaluation/worldcup_source_comparison.csv')
        self.assertEqual(len(comparison),72)
        self.assertTrue(comparison.openfootball_agrees.all())
        self.assertTrue(comparison.transfermarkt_agrees.all())

    def test_metrics_population_clusters_and_small_strata(self):
        metrics=pd.read_csv(ROOT/'reports/final_evaluation/semiconfirmatory_metrics.csv')
        total=metrics[metrics.model.eq('logistic')&metrics.stratum.eq('total')].iloc[0]
        self.assertEqual((int(total.matches),int(total.quarter_clusters),int(total.month_clusters)),(3624,14,39))
        expected=metrics.matches.ge(200)&metrics[['home_wins','draws','away_wins']].ge(30).all(axis=1)
        np.testing.assert_array_equal(metrics.estimable,expected)
        world=pd.read_csv(ROOT/'reports/final_evaluation/worldcup_group_metrics.csv')
        self.assertTrue(world.matches.eq(72).all())
        self.assertFalse(world.estimable.any())

    def test_semiconfirmatory_confirmation_matches_preregistered_rule(self):
        folder=ROOT/'reports/final_evaluation'
        conclusion=json.loads((folder/'semiconfirmatory_conclusion.json').read_text(encoding='utf-8'))
        metrics=pd.read_csv(folder/'semiconfirmatory_metrics.csv')
        row=metrics[metrics.model.eq('logistic')&metrics.stratum.eq('non_friendlies')].iloc[0]
        self.assertEqual(conclusion['selection_confirmed'],bool(row.estimable and row.difference_log_loss_ci_high<0 and row.difference_brier<=0 and conclusion['blocks_improving']>=3))

    def test_public_html_contains_all_frozen_matches_and_distinct_products(self):
        text=(ROOT/'reports/final_evaluation/football_report.html').read_text(encoding='utf-8')
        encoded=text.split('const DATA=',1)[1].split(';\nconst names=',1)[0]
        data=json.loads(encoded)
        self.assertEqual(len(data['fixtures']),72)
        self.assertEqual(len({f['id'] for f in data['fixtures']}),72)
        for f in data['fixtures']:
            self.assertIn('score',f)
            for method,p in f['models'].items():
                self.assertAlmostEqual(sum(p['p']),1,places=12)
        self.assertIn('Poisson',text)
        self.assertNotEqual(data['fixtures'][0]['models']['logistic']['p'],data['fixtures'][0]['models']['poisson']['p'])


if __name__=='__main__':unittest.main()
