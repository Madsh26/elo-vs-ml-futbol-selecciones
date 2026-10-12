import io
from pathlib import Path
import sys
import unittest
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
from football_forecast.ingestion import before_cutoff_csv, NameRegistry, goal_event_evidence, load_study_data
from football_forecast.preparation import evidence_features

class EvidenceUnitTests(unittest.TestCase):
    def test_cutoff_before_score_interpretation(self):
        stream=io.BytesIO(b'date,home_score,away_score\n2026-06-09,1,0\n2026-06-10,INVALID,SECRET\n2026-07-01,INVALID,SECRET\n')
        frame=before_cutoff_csv(stream,'2026-06-10')
        self.assertEqual(len(frame),1)
        self.assertEqual(pd.to_numeric(frame.home_score).iloc[0],1)

    def test_aliases_preserve_entities_and_dates(self):
        former=pd.DataFrame([{'former':'Zaïre','current':'DR Congo','start_date':'1971-01-10','end_date':'1997-04-27'}])
        registry=NameRegistry(former)
        for raw,canonical in [('Czechia','Czech Republic'),('Türkiye','Turkey'),("Côte d'Ivoire",'Ivory Coast'),('Cape Verde','Cabo Verde'),('Curaçao','Curacao')]:
            self.assertEqual(registry.normalize(raw),canonical)
        self.assertEqual(registry.normalize('Zaïre','1980-01-01'),'DR Congo')
        self.assertEqual(registry.normalize('Zaïre','2000-01-01'),'Zaire')
        self.assertNotEqual(registry.normalize('Czechoslovakia'),registry.normalize('Czechia'))

    def test_keep_identical_goal_events_if_score_agrees(self):
        events=pd.DataFrame([{'team':'A','minute':60},{'team':'A','minute':60}])
        score,reason=goal_event_evidence(events,'A','B',2,0)
        self.assertEqual(score,(2,0))
        self.assertEqual(len(events),2)

    def test_missing_minutes_conflicts_and_extra_time(self):
        self.assertEqual(goal_event_evidence(pd.DataFrame([{'team':'A','minute':90},{'team':'B','minute':117}]),'A','B',1,1)[0],(1,0))
        self.assertIsNone(goal_event_evidence(pd.DataFrame([{'team':'A','minute':np.nan}]),'A','B',1,0)[0])
        self.assertIsNone(goal_event_evidence(pd.DataFrame([{'team':'A','minute':60}]),'A','B',2,0)[0])
        self.assertEqual(goal_event_evidence(None,'A','B',0,0)[0],(0,0))

    def test_unverified_goals_do_not_enter_windows_or_leak_same_day(self):
        rows=[]
        for date,home,away,score,known in [('2020-01-01','A','B',9,False),('2020-01-01','A','C',0,True),('2020-01-02','A','B',1,True)]:
            rows.append({'date':pd.Timestamp(date),'home_team':home,'away_team':away,'country':'X','neutral':True,'tournament':'Friendly',
                         'recorded_home_score':score,'recorded_away_score':0,'elo_home_score':score,'elo_away_score':0,
                         'home_score_90':score if known else np.nan,'away_score_90':0 if known else np.nan,'goal_training_eligible':known})
        history=pd.DataFrame(rows)
        fixture=pd.DataFrame([{'date':pd.Timestamp('2020-02-01'),'home_team':'A','away_team':'B','country':'X','neutral':True,'tournament':'FIFA World Cup'}])
        full,training,future,_=evidence_features(history,fixture)
        self.assertEqual(len(training),2)
        self.assertEqual(full.iloc[0].elo_home,full.iloc[1].elo_home)
        self.assertAlmostEqual(full.iloc[2].gf5_home,.975)
        self.assertAlmostEqual(full.iloc[2].goals_90_coverage5_home,.5)
        changed=history.copy();changed.loc[2,'elo_home_score']=20
        altered,_,_,_=evidence_features(changed,fixture)
        np.testing.assert_allclose(full[['elo_home','elo_away','gf5_home']],altered[['elo_home','elo_away','gf5_home']])

@unittest.skipUnless((ROOT/'data/raw/international_results_current.zip').exists(),'Local inputs required')
class EvidenceLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_study_data(ROOT,'2026-06-10')

    def test_official_competitions_retained_and_no_future_labels(self):
        h=self.data.history
        for tournament in ['FIFA World Cup qualification','UEFA Euro','Copa América','UEFA Nations League','CONCACAF Nations League']:
            self.assertTrue((h.tournament==tournament).any(),tournament)
        self.assertTrue((h.date<pd.Timestamp('2026-06-10')).all())
        self.assertFalse(self.data.audit['official_2026_results_loaded'])
        teams=set(self.data.fixtures[['home_team','away_team']].stack())
        self.assertEqual(len(teams),48)
        self.assertTrue(teams<=set(h[['home_team','away_team']].stack()))
        assumed=h[h.duration_assumed]
        self.assertGreater(len(assumed),0)
        self.assertFalse(assumed.goal_training_eligible.any())
        self.assertTrue(assumed.home_score_90.isna().all())
        self.assertIsNone(self.data.enrichments['market_values_asof'])

    def test_tanda_not_forced_to_draw(self):
        h=self.data.history
        row=h[(h.date==pd.Timestamp('2023-11-21'))&(h.home_team=='Mexico')&(h.away_team=='Honduras')].iloc[0]
        self.assertTrue(row.shootout_record)
        # This archive has no complete goal events for this match. Its
        # recorded 2-0 must neither become a draw nor an invented 90' label.
        self.assertFalse(row.goal_training_eligible)
        self.assertTrue(pd.isna(row.home_score_90))
        self.assertEqual(row.duration_reason,'no_goal_event_coverage')
        self.assertEqual((row.elo_home_score,row.elo_away_score),(2,0))

    def test_verified_worldcup_extra_time(self):
        h=self.data.history
        row=h[(h.date==pd.Timestamp('2022-12-09'))&(h.home_team=='Croatia')&(h.away_team=='Brazil')].iloc[0]
        self.assertEqual((row.recorded_home_score,row.recorded_away_score),(1,1))
        self.assertEqual((row.home_score_90,row.away_score_90),(0,0))
        row=h[(h.date==pd.Timestamp('2022-12-18'))&(h.home_team=='Argentina')].iloc[0]
        self.assertEqual((row.home_score_90,row.away_score_90),(2,2))

if __name__=='__main__':
    unittest.main()
