"""Behavioral checks for frozen candidates and the reserved-period boundary."""
from pathlib import Path
import sys
import json
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.selected_models import ResultModel, GoalModel, rates_to_1x2, effective_rho, score_losses
from football_forecast.models import score_matrix, matrix_1x2
from football_forecast.model_selection import flagged, paired_se, code_digest
from football_forecast.ingestion import digest_file


class DistributionTests(unittest.TestCase):
    def test_infinite_score_distribution_and_outcome_are_coherent(self):
        lh=np.array([.2,1.5,5.,12.]);la=np.array([4.,1.,6.,.05])
        for rho in [0.,-.2,.2]:
            actual=rates_to_1x2(lh,la,rho)
            np.testing.assert_allclose(actual.sum(axis=1),1,atol=1e-12)
            np.testing.assert_allclose(actual,rates_to_1x2(la,lh,rho)[:,::-1],atol=1e-9)
            for i,(h,a) in enumerate(zip(lh,la)):
                r=effective_rho(h,a,rho)
                grid,_=score_matrix(h,a,r,tolerance=1e-12)
                np.testing.assert_allclose(actual[i],matrix_1x2(grid),atol=1e-10)

    def test_all_candidates_swap_symmetry(self):
        rng=np.random.default_rng(123)
        x=rng.normal(size=(90,2))
        y=np.tile([0,1,2],30)
        signs=[-1,1]
        for kind in ['frequency','logistic','ordinal','xgboost']:
            model=ResultModel(kind,signs).fit(x,y)
            p=model.predict_proba(x)
            np.testing.assert_allclose(p.sum(axis=1),1,atol=1e-12)
            np.testing.assert_allclose(p,model.predict_proba(x*np.array(signs))[:,::-1],atol=1e-9)
        h=rng.poisson(np.exp(.2+.3*x[:,0]));a=rng.poisson(np.exp(.2-.3*x[:,0]))
        for kind in ['poisson','dixon_coles','xgboost_poisson']:
            model=GoalModel(kind,signs).fit(x,h,a)
            p=model.predict_proba(x)
            np.testing.assert_allclose(p,model.predict_proba(x*np.array(signs))[:,::-1],atol=1e-9)
            self.assertTrue(np.isfinite(score_losses(h,a,*model.rates(x),model.rho)).all())

    def test_flags_are_explicit_and_independent_of_zero_scores(self):
        frame=pd.DataFrame({'shootout_record':[False,True,False,True],
                            'proven_extra_time_goals':[0,0,1,1]})
        self.assertEqual(flagged(frame).tolist(),[False,True,True,True])

    def test_paired_se_uses_same_matches(self):
        frame=pd.DataFrame({'date':pd.to_datetime(['2020-01-01','2020-04-01']),
                            'home_team':['A','A'],'away_team':['B','B'],
                            'competitive':[True,True],'log_loss':[1.,2.]})
        delta,se=paired_se(frame,frame)
        self.assertEqual((delta,se),(0.,0.))
        other=frame.copy();other.at[1,'away_team']='C'
        with self.assertRaises(ValueError):paired_se(frame,other)


@unittest.skipUnless((ROOT/'reports/models_selected/freeze_manifest.json').exists(),'Frozen execution required')
class FrozenArtifactTests(unittest.TestCase):
    def test_commitments_precede_selection_and_no_reserved_results(self):
        folder=ROOT/'reports/models_selected'
        protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
        selection=json.loads((folder/'selected_elo.json').read_text(encoding='utf-8'))
        freeze=json.loads((folder/'freeze_manifest.json').read_text(encoding='utf-8'))
        self.assertLess(pd.Timestamp(protocol['written_at_utc']),pd.Timestamp(selection['selection_completed_at_utc']))
        self.assertLess(pd.Timestamp(selection['selection_completed_at_utc']),pd.Timestamp(freeze['models_frozen_at_utc']))
        self.assertFalse(freeze['reserved_results_opened'])
        self.assertIsNone(freeze['official_results_loaded_at_utc'])
        self.assertLess(pd.Timestamp(freeze['training_latest_result']),pd.Timestamp('2023-01-01'))
        for model in freeze['models']:
            self.assertEqual(model['sha256'],digest_file(ROOT/model['path']))
        self.assertEqual(freeze['protocol_sha256'],digest_file(folder/'protocol.json'))
        for path,expected in freeze['code_sha256'].items():
            self.assertEqual(expected,code_digest(ROOT/path))

    def test_frozen_command_preserves_manifest_and_models(self):
        from football_forecast.model_selection import run
        folder=ROOT/'reports/models_selected'
        before=digest_file(folder/'freeze_manifest.json')
        manifest=run(ROOT)
        self.assertEqual(before,digest_file(folder/'freeze_manifest.json'))
        self.assertFalse(manifest['reserved_results_opened'])

    def test_all_outcome_models_have_identical_pre2023_evaluation_keys(self):
        folder=ROOT/'reports/models_selected'
        reference=pd.read_csv(folder/'predictions_elo.csv')
        columns=['date','home_team','away_team']
        for path in folder.glob('predictions_*.csv'):
            pred=pd.read_csv(path)
            pd.testing.assert_frame_equal(reference[columns],pred[columns],obj=path.name)
            self.assertTrue((pd.to_datetime(pred.date)<pd.Timestamp('2023-01-01')).all())
            np.testing.assert_allclose(pred[['p_home_win','p_draw','p_away_win']].sum(axis=1),1,atol=1e-12)

    def test_joint_grid_and_simple_choice_are_reproducible(self):
        grid=pd.read_csv(ROOT/'reports/models_selected/elo_joint_grid.csv')
        self.assertEqual(len(grid),32)
        self.assertEqual(int(grid.selected.sum()),1)
        chosen=grid[grid.selected].iloc[0]
        self.assertTrue(chosen.within_one_se)
        expected=grid[grid.within_one_se].assign(inactivity_complex=lambda f:f.inactivity_rate.ne(0),
                   k_complex=lambda f:f.k_level.ne('reference')).sort_values(
                   ['inactivity_complex','k_complex','margin_strength','home_advantage','log_loss']).iloc[0]
        self.assertEqual(chosen.configuration,expected.configuration)


if __name__=='__main__':unittest.main()
