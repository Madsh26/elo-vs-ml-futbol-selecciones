"""Admission independence, source duration and pre-2023 review invariants."""
from pathlib import Path
from datetime import datetime
import io
import json
import sys
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.ingestion import goal_event_evidence,fjelstul_from_frames,before_cutoff_csv
from football_forecast.selection_review import goal_policy_frame,outcome_frame

class MembershipTests(unittest.TestCase):
    def history(self):
        return pd.DataFrame({'date':pd.to_datetime(['2020-01-01']*4),'home_team':['A','C','E','G'],
          'away_team':['B','D','F','H'],'tournament':['Friendly','Friendly','Qualifier','FIFA World Cup'],
          'recorded_home_score':[0,3,0,2],'recorded_away_score':[0,1,0,0],
          'x12_home_score':[0,3,0,2],'x12_away_score':[0,1,0,0],
          'home_score_90':[np.nan,np.nan,np.nan,2.],'away_score_90':[np.nan,np.nan,np.nan,0.],
          'goal_training_eligible':[False,False,False,True],'x12_eligible':[True]*4})

    def test_unknown_zero_and_positive_scores_have_identical_coverage_rule(self):
        self.assertIsNone(goal_event_evidence(None,'A','B',0,0)[0])
        self.assertIsNone(goal_event_evidence(None,'A','B',3,1)[0])
        frame=self.history()
        strict=goal_policy_frame(frame,'strict')
        self.assertEqual(strict.goal_training_eligible.tolist(),[False,False,False,True])
        self.assertEqual(goal_policy_frame(frame,'friendly_assumed').goal_training_eligible.tolist(),[True,True,False,True])
        self.assertTrue(goal_policy_frame(frame,'all_assumed').goal_training_eligible.all())

    def test_membership_survives_replacing_every_marker(self):
        original=self.history();changed=original.copy()
        changed[['recorded_home_score','recorded_away_score','x12_home_score','x12_away_score']]=0
        for policy in ['strict','friendly_assumed','all_assumed','all_recorded']:
            pd.testing.assert_series_equal(goal_policy_frame(original,policy).goal_training_eligible,
                                           goal_policy_frame(changed,policy).goal_training_eligible)
        self.assertEqual(len(outcome_frame(original)),len(outcome_frame(changed)))

    def test_match_catalogue_without_extra_time_admits_all_scores(self):
        matches=pd.DataFrame([{'match_id':'M0','match_date':'2020-01-01','home_team_name':'A','away_team_name':'B',
                               'home_team_score':0,'away_team_score':0,'extra_time':'0'},
                              {'match_id':'M1','match_date':'2020-01-02','home_team_name':'A','away_team_name':'B',
                               'home_team_score':3,'away_team_score':2,'extra_time':'0'}])
        events=pd.DataFrame(columns=['match_id','team_name','minute_regulation','match_period'])
        evidence,catalogue=fjelstul_from_frames(matches,events)
        self.assertEqual(len(catalogue),2);self.assertEqual(len(evidence),2)
        self.assertEqual(evidence[(pd.Timestamp('2020-01-02'),'A','B')][:2],(3,2))

    def test_extra_time_uses_period_not_match_winner(self):
        match=pd.DataFrame([{'match_id':'M','match_date':'2020-01-01','home_team_name':'A','away_team_name':'B',
                             'home_team_score':1,'away_team_score':1,'extra_time':'1'}])
        events=pd.DataFrame([{'match_id':'M','team_name':'A','minute_regulation':90,'match_period':'second half'},
                             {'match_id':'M','team_name':'B','minute_regulation':115,'match_period':'extra time'}])
        evidence,_=fjelstul_from_frames(match,events)
        self.assertEqual(evidence[(pd.Timestamp('2020-01-01'),'A','B')][:2],(1,0))

    def test_reserved_result_tokens_discarded_before_numeric_interpretation(self):
        stream=io.BytesIO(b'date,home_score,away_score\n2022-12-31,2,1\n2023-01-01,DO_NOT_READ,FORBIDDEN\n2026-01-01,FORBIDDEN,FORBIDDEN\n')
        frame=before_cutoff_csv(stream,'2023-01-01')
        self.assertEqual(pd.to_numeric(frame.home_score).tolist(),[2])

@unittest.skipUnless((ROOT/'reports/selection_review/data_audit.json').exists(),'Executed review required')
class ReviewArtifactTests(unittest.TestCase):
    def test_identical_evaluation_keys_for_all_main_ablations(self):
        folder=ROOT/'reports/selection_review'
        pred=pd.read_csv(folder/'walk_forward_predictions.csv')
        base=pred[pred.model=='elo_venue'][['date','home_team','away_team']].reset_index(drop=True)
        for name,group in pred.groupby('model'):
            pd.testing.assert_frame_equal(base,group[['date','home_team','away_team']].reset_index(drop=True),obj=name)
        self.assertTrue((pd.to_datetime(pred.date)<pd.Timestamp('2023-01-01')).all())
        probabilities=pred[['p_home_win','p_draw','p_away_win']].to_numpy()
        np.testing.assert_allclose(probabilities.sum(axis=1),1,atol=1e-12)

    def test_unconditional_population_preserves_marker_rates(self):
        frame=pd.read_csv(ROOT/'reports/selection_review/selection_bias_diagnostics.csv')
        all_rows=frame[frame.cohort.isin(['Resultado 1X2: todos','Goles: '+
                   'Todos los marcadores registrados, sensibilidad sin reconstrucción'])]
        np.testing.assert_allclose(all_rows.zero_zero_difference_vs_complete,0,atol=1e-15)
        np.testing.assert_allclose(all_rows.draw_difference_vs_complete,0,atol=1e-15)

    def test_protocol_written_before_selection_and_no_reserved_phase(self):
        folder=ROOT/'reports/selection_review'
        protocol=json.loads((folder/'selection_protocol.json').read_text(encoding='utf-8'))
        selected=json.loads((folder/'selected_elo.json').read_text(encoding='utf-8'))
        audit=json.loads((folder/'data_audit.json').read_text(encoding='utf-8'))
        self.assertLess(pd.Timestamp(protocol['written_at_utc']),pd.Timestamp(selected['selection_completed_at_utc']))
        self.assertFalse(audit['reserved_results_opened']);self.assertFalse(audit['xgboost_executed'])
        self.assertTrue(audit['membership_independent_of_target'])
        self.assertLess(pd.Timestamp(audit['latest_result_admitted']),pd.Timestamp('2023-01-01'))

if __name__=='__main__':unittest.main()
