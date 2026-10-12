"""Read local archives; recover 90-minute targets and build past-only features."""
from collections import defaultdict, deque
from pathlib import Path
import hashlib
import unicodedata
import zipfile
import numpy as np
import pandas as pd

ALIASES = {
    'USA': 'United States', 'South Korea': 'Korea Republic', 'Iran': 'IR Iran',
    'Cape Verde': 'Cabo Verde', 'Bosnia and Herzegovina': 'Bosnia-Herzegovina',
    'Curaçao': 'Curacao', 'Cura�ao': 'Curacao', "C�te d'Ivoire": 'Ivory Coast',
    "Côte d'Ivoire": 'Ivory Coast', "Cote d'Ivoire": 'Ivory Coast',
}

def normalize(name):
    name = str(name).strip()
    name = ALIASES.get(name, name)
    return ''.join(c for c in unicodedata.normalize('NFKD', name)
                   if not unicodedata.combining(c))

def read_archive(root, archive, member):
    names = {'international_results-master.zip':'international_results_baseline.zip',
             'worldcup-master.zip':'fjelstul_worldcup.zip', 'data.zip':'worldcup_fixtures.zip'}
    with zipfile.ZipFile(Path(root) / 'data/raw' / names.get(archive,archive)) as z:
        return pd.read_csv(z.open(member))

def load_local(root, cutoff):
    results = read_archive(root, 'international_results-master.zip',
                           'international_results-master/results.csv')
    results['date'] = pd.to_datetime(results['date'])
    for col in ['home_team', 'away_team', 'country']:
        results[col] = results[col].map(normalize)
    wc = read_archive(root, 'worldcup-master.zip', 'worldcup-master/data-csv/matches.csv')
    goals = read_archive(root, 'worldcup-master.zip', 'worldcup-master/data-csv/goals.csv')
    wc = wc[wc.tournament_name.str.contains("Men's", regex=False)].copy()
    wc['date'] = pd.to_datetime(wc.match_date)
    for col in ['home_team_name', 'away_team_name']:
        wc[col] = wc[col].map(normalize)
    # Goal events identify the credited team (including own goals).
    et_goals = goals[goals.minute_regulation > 90].groupby(['match_id', 'team_id']).size()
    verified = {}
    recovered = 0
    for row in wc.itertuples():
        h = int(row.home_team_score - et_goals.get((row.match_id, row.home_team_id), 0))
        a = int(row.away_team_score - et_goals.get((row.match_id, row.away_team_id), 0))
        assert h >= 0 and a >= 0
        key = (row.date, row.home_team_name, row.away_team_name)
        verified[key] = (h, a, row.home_team_score, row.away_team_score)
        if row.extra_time:
            recovered += 1
    scored = results.dropna(subset=['home_score', 'away_score']).copy()
    scored = scored[scored.date < pd.Timestamp(cutoff)].copy()
    ambiguous = scored.duplicated(['date', 'home_team', 'away_team'], keep=False)
    ambiguous_rows = scored.loc[ambiguous, ['date','home_team','away_team','home_score','away_score']].astype(str).to_dict('records')
    # The local archive has two conflicting Tahiti fixtures on 1974-02-17.
    # Without kickoff times, exclude both; do not arbitrarily pick a result.
    scored = scored.loc[~ambiguous].copy()
    usable = []
    mismatches = []
    for row in scored.itertuples():
        # Conservative scope: friendlies have no standard extra time;
        # World Cups have locally verified event data. Other competitions
        # lack a reliable 90-minute / extra-time flag in results.csv.
        if row.tournament == 'Friendly':
            item = row._asdict()
            item['duration_source'] = 'friendly_assumed_90'
            usable.append(item)
        elif row.tournament == 'FIFA World Cup':
            key = (row.date, row.home_team, row.away_team)
            reverse = (row.date, row.away_team, row.home_team)
            v = verified.get(key)
            if v is None and reverse in verified:
                r = verified[reverse]
                v = (r[1], r[0], r[3], r[2])
            if v is not None:
                if (row.home_score, row.away_score) != (v[2], v[3]):
                    mismatches.append(str(key))
                    continue
                item = row._asdict()
                item.update(home_score=v[0], away_score=v[1],
                            duration_source='worldcup_goal_events_90')
                usable.append(item)
    history = pd.DataFrame(usable).drop(columns=['Index'], errors='ignore')
    history = history.sort_values(['date', 'home_team', 'away_team']).reset_index(drop=True)
    history[['home_score', 'away_score']] = history[['home_score', 'away_score']].astype(int)
    fixtures = read_archive(root, 'data.zip', 'data/group_fixtures.csv')
    for col in ['home_team', 'away_team']:
        fixtures[col] = fixtures[col].map(normalize)
    scheduled = results[(results.tournament == 'FIFA World Cup') &
                        (results.date.dt.year == 2026)].copy()
    replacements = {}
    # Match on the known opposing team. Two anchors must identify exactly
    # one scheduled participant; dates can differ because the sources use
    # local dates versus UTC. No score values are used.
    for placeholder in fixtures[['home_team', 'away_team']].stack().unique():
        if 'Playoff' in placeholder:
            anchors = list(fixtures.loc[fixtures.home_team == placeholder, 'away_team'])
            anchors += list(fixtures.loc[fixtures.away_team == placeholder, 'home_team'])
            sets = []
            for anchor in anchors:
                candidates = set(scheduled.loc[scheduled.home_team == anchor, 'away_team'])
                candidates |= set(scheduled.loc[scheduled.away_team == anchor, 'home_team'])
                sets.append(candidates)
            common = set.intersection(*sets) if sets else set()
            if len(common) != 1:
                raise ValueError(f'Cannot resolve {placeholder}: {common}')
            replacements[placeholder] = common.pop()
    fixtures = fixtures.replace({'home_team': replacements, 'away_team': replacements})
    if fixtures[['home_team', 'away_team']].stack().str.contains('Playoff').any():
        raise ValueError('Unresolved fixture participant')
    fixtures['date'] = pd.to_datetime(fixtures.date_utc, utc=True).dt.tz_localize(None)
    fixtures['country'] = fixtures.venue.map(
        lambda x: 'Mexico' if any(s in x for s in ['Mexico City', 'Guadalajara', 'Monterrey'])
        else 'Canada' if any(s in x for s in ['Toronto', 'Vancouver']) else 'United States')
    fixtures['neutral'] = ~((fixtures.home_team == fixtures.country) |
                            (fixtures.away_team == fixtures.country))
    fixtures['tournament'] = 'FIFA World Cup'
    assert len(fixtures) == 72
    assert fixtures[['home_team', 'away_team']].stack().nunique() == 48
    manifest = {'prediction_cutoff_exclusive': cutoff,
                'raw_rows': len(results), 'raw_last_date': str(results.date.max().date()),
                'latest_scored_date': str(results.dropna(subset=['home_score', 'away_score']).date.max().date()),
                'worldcup_2026_scheduled_rows': len(scheduled),
                'worldcup_2026_scored_rows': int(scheduled[['home_score', 'away_score']].notna().all(axis=1).sum()),
                'verified_90_history_rows': len(history),
                'excluded_unverified_scored_rows': len(scored) - len(history),
                'worldcup_extra_time_matches_recovered': recovered,
                'worldcup_source_score_mismatches': mismatches,
                'excluded_ambiguous_same_day_rows': ambiguous_rows,
                'resolved_placeholders': replacements,
                'duration_policy': 'Friendlies assumed 90 minutes; men World Cup regulation scores reconstructed from local goal events; other competitions excluded.',
                'fixture_resolution_policy': '2026 scheduled opponents from local archive; as-of availability not independently timestamped.',
                'sources': []}
    for name in ['international_results-master.zip', 'worldcup-master.zip', 'data.zip']:
        raw_name = {'international_results-master.zip':'international_results_baseline.zip',
                    'worldcup-master.zip':'fjelstul_worldcup.zip','data.zip':'worldcup_fixtures.zip'}[name]
        path = Path(root) / 'data/raw' / raw_name
        manifest['sources'].append({'file':str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return history, fixtures, manifest

FEATURES = ['elo_home', 'elo_away', 'elo_diff', 'gf5_home', 'gf5_away',
            'ga5_home', 'ga5_away', 'gf10_home', 'gf10_away', 'ga10_home', 'ga10_away',
            'form5_home', 'form5_away', 'games_home', 'games_away',
            'opponent_elo_home', 'opponent_elo_away', 'neutral', 'host_home', 'host_away',
            'worldcup']

class HistoryState:
    def __init__(self):
        self.elo = defaultdict(lambda: 1500.)
        self.games = defaultdict(int)
        self.recent = defaultdict(lambda: deque(maxlen=10))

    def features(self, row):
        h, a = row.home_team, row.away_team
        x = {'elo_home': self.elo[h], 'elo_away': self.elo[a],
             'elo_diff': self.elo[h] - self.elo[a], 'neutral': float(row.neutral),
             'host_home': float(h == row.country and not row.neutral),
             'host_away': float(a == row.country and not row.neutral),
             'worldcup': float(row.tournament == 'FIFA World Cup')}
        for team, side in [(h, 'home'), (a, 'away')]:
            data = list(self.recent[team])
            x[f'games_{side}'] = min(self.games[team], 100)
            x[f'opponent_elo_{side}'] = np.mean([r[3] for r in data]) if data else 1500.
            for window in [5, 10]:
                block = data[-window:]
                for idx, field, prior in [(0, 'gf', 1.3), (1, 'ga', 1.3)]:
                    # Shrink tiny samples to a fixed, declared prior.
                    x[f'{field}{window}_{side}'] = (sum(r[idx] for r in block) + 3*prior)/(len(block)+3)
            x[f'form5_{side}'] = (sum(r[2] for r in data[-5:]) + 1.5)/(len(data[-5:])+3)
        return x

    def update_day(self, rows):
        delta = defaultdict(float)
        additions = []
        for row in rows:
            h, a = row.home_team, row.away_team
            gf, ga = row.home_score, row.away_score
            host = 60 * ((h == row.country) - (a == row.country)) if not row.neutral else 0
            expected = 1/(1+10**(-(self.elo[h]-self.elo[a]+host)/400))
            outcome = 1. if gf > ga else 0. if gf < ga else .5
            change = (24 if row.tournament == 'FIFA World Cup' else 16)*(outcome-expected)
            delta[h] += change
            delta[a] -= change
            additions += [(h, (gf, ga, outcome, self.elo[a])),
                          (a, (ga, gf, 1-outcome, self.elo[h]))]
        for t, d in delta.items():
            self.elo[t] += d
        for t, stats in additions:
            self.recent[t].append(stats)
            self.games[t] += 1

def build_features(history, fixtures):
    state = HistoryState()
    records = []
    for _, day in history.groupby('date', sort=True):
        rows = list(day.itertuples(index=False))
        # All predictions on a date precede updates from that same date.
        for row in rows:
            records.append({**row._asdict(), **state.features(row)})
        state.update_day(rows)
    frame = pd.DataFrame(records)
    frame['target'] = np.where(frame.home_score > frame.away_score, 0,
                               np.where(frame.home_score == frame.away_score, 1, 2))
    future = pd.DataFrame([{**r._asdict(), **state.features(r)}
                           for r in fixtures.itertuples(index=False)])
    if future[['games_home', 'games_away']].min().min() == 0:
        raise ValueError('Fixture team has no usable history')
    return frame, future, state

def load_study_local(root='.', cutoff='2026-06-10'):
    """Load separate Elo history and regulation-goal targets from local evidence."""
    from .ingestion import load_study_data
    return load_study_data(root, cutoff)
