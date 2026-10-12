"""Local, cutoff-aware evidence for recorded and regulation-time scores.

No model fitting and no loading of post-cutoff result labels occurs here.
Fjelstul, martj42 and the fixture metadata remain separate sources.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import csv
import hashlib
import io
import unicodedata
import zipfile
import numpy as np
import pandas as pd

MATCH_KEY = ['date', 'home_team', 'away_team']
ALIASES = {
    'USA': 'United States', 'South Korea': 'Korea Republic', 'Iran': 'IR Iran',
    'Cape Verde': 'Cabo Verde', 'Cape Verde Islands': 'Cabo Verde',
    'Bosnia and Herzegovina': 'Bosnia-Herzegovina', 'Bosnia & Herzegovina': 'Bosnia-Herzegovina',
    'Czechia': 'Czech Republic', 'Türkiye': 'Turkey', 'Côte d’Ivoire': 'Ivory Coast',
    "Côte d'Ivoire": 'Ivory Coast', "Cote d'Ivoire": 'Ivory Coast', "C�te d'Ivoire": 'Ivory Coast',
    'Curaçao': 'Curacao', 'Cura�ao': 'Curacao', 'Congo DR': 'DR Congo',
    'Aotearoa New Zealand': 'New Zealand', 'West Germany': 'Germany',
    'Republic of Ireland': 'Ireland', 'North Korea': 'Korea DPR',
    'Korea, South':'Korea Republic', 'T�rkiye':'Turkey', 'Hongkong':'Hong Kong',
}

def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def before_cutoff_csv(stream, cutoff, date_column='date'):
    """Filter dates before interpreting scores, minutes or other target fields.

    CSV tokens for rejected records are discarded. They are not converted,
    retained, aggregated as labels or passed to downstream code.
    """
    boundary = pd.Timestamp(cutoff).normalize()
    reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))
    accepted = []
    for row in reader:
        date = pd.Timestamp(row[date_column])
        if date < boundary:
            accepted.append(row)
    return pd.DataFrame(accepted)

def archive_before(path, member, cutoff, date_column='date'):
    with zipfile.ZipFile(path) as archive:
        with archive.open(member) as stream:
            return before_cutoff_csv(stream, cutoff, date_column)

class NameRegistry:
    def __init__(self, former_names=None):
        self.former = defaultdict(list)
        if former_names is not None:
            for row in former_names.itertuples(index=False):
                self.former[str(row.former)].append(
                    (pd.Timestamp(row.start_date), pd.Timestamp(row.end_date), str(row.current)))

    def normalize(self, name, date=None):
        name = str(name).strip()
        if date is not None:
            for start, end, current in self.former.get(name, []):
                if start <= pd.Timestamp(date) <= end:
                    name = current
                    break
        name = ALIASES.get(name, name)
        # Czechoslovakia remains a separate historical entity.
        return ''.join(c for c in unicodedata.normalize('NFKD', name)
                       if not unicodedata.combining(c))

    def frame(self, frame, columns, date_column='date'):
        frame = frame.copy()
        dates = frame[date_column] if date_column in frame else [None] * len(frame)
        for column in columns:
            frame[column] = [self.normalize(value, date) for value, date in zip(frame[column], dates)]
        return frame

def boolean(values):
    mapped = values.astype(str).str.casefold().map({'true': True, 'false': False,
                                                 '1': True, '0': False, '1.0':True, '0.0':False})
    if mapped.isna().any():
        raise ValueError('Unrecognized boolean token in local archive')
    return mapped.astype(bool)

def competition_family(tournament):
    if tournament == 'Friendly':
        return 'friendly'
    if tournament == 'FIFA World Cup':
        return 'worldcup'
    if 'qualification' in tournament.casefold():
        return 'qualification'
    if 'Nations League' in tournament:
        return 'nations_league'
    if tournament in {'UEFA Euro', 'Copa América', 'Copa America', 'African Cup of Nations',
                      'AFC Asian Cup', 'Gold Cup', 'Oceania Nations Cup', 'CONCACAF Championship'}:
        return 'continental'
    if any(word in tournament for word in ['CONIFA', 'ConIFA', 'Viva World', 'FIFI']):
        return 'non_fifa'
    return 'other_tournament'

def goal_event_evidence(events, home, away, full_home, full_away):
    """Keep duplicate-looking events; validate counts and credited teams first."""
    if events is None or not len(events):
        if full_home == 0 and full_away == 0:
            return (0, 0), 'zero_score_invariant'
        return None, 'no_goal_event_coverage'
    counts = Counter(events.team)
    if set(counts) - {home, away}:
        return None, 'goal_event_unknown_team'
    if counts.get(home, 0) != full_home or counts.get(away, 0) != full_away:
        return None, 'goal_event_count_conflict'
    minutes = pd.to_numeric(events.minute, errors='coerce')
    if minutes.isna().any():
        return None, 'goal_event_missing_minute'
    if ((minutes < 0) | (minutes > 120) | (minutes % 1 != 0)).any():
        return None, 'goal_event_invalid_minute'
    # martj42 encodes regulation stoppage as minute 90. StatsBomb minutes
    # must never enter this function: its period, not minute, defines time.
    et = events.loc[minutes > 90].team.value_counts()
    h90 = int(full_home - et.get(home, 0))
    a90 = int(full_away - et.get(away, 0))
    return (h90, a90), 'martj42_complete_goal_events'

def fjelstul_evidence(root, cutoff, registry):
    path = Path(root) / 'data/raw/fjelstul_worldcup.zip'
    wc = archive_before(path, 'worldcup-master/data-csv/matches.csv', cutoff, 'match_date')
    wc = wc[wc.tournament_name.str.contains("Men's", regex=False)].copy()
    wc = registry.frame(wc, ['home_team_name', 'away_team_name'], 'match_date')
    goals = archive_before(path, 'worldcup-master/data-csv/goals.csv', cutoff, 'match_date')
    goals = registry.frame(goals, ['team_name'], 'match_date')
    goals['minute_regulation'] = pd.to_numeric(goals.minute_regulation, errors='coerce')
    grouped = {key: group for key, group in goals.groupby('match_id')}
    evidence = {}
    for row in wc.itertuples(index=False):
        h, a = int(row.home_team_score), int(row.away_team_score)
        events = grouped.get(row.match_id)
        key = (pd.Timestamp(row.match_date), row.home_team_name, row.away_team_name)
        if events is None:
            if h == a == 0:
                evidence[key] = (0, 0, h, a)
            continue
        counts = events.team_name.value_counts()
        if counts.get(row.home_team_name, 0) != h or counts.get(row.away_team_name, 0) != a:
            continue
        if events.minute_regulation.isna().any():
            continue
        et = events[events.match_period.str.contains('extra time', case=False, regex=False)].team_name.value_counts()
        evidence[key] = (int(h - et.get(row.home_team_name, 0)),
                         int(a - et.get(row.away_team_name, 0)), h, a)
    return evidence

@dataclass
class StudyData:
    history: pd.DataFrame
    goal_history: pd.DataFrame
    fixtures: pd.DataFrame
    name_registry: NameRegistry
    audit: dict
    # Optional adapters attach dated enrichment tables here without changing
    # the result/goal evidence contract or requiring those sources to exist.
    enrichments: dict = field(default_factory=lambda: {
        'market_values_asof':None, 'fifa_publications_asof':None, 'venue_altitude_static':None})

def load_study_data(root='.', cutoff='2026-06-10'):
    root = Path(root)
    raw = root / 'data/raw'
    archive = raw / 'international_results_current.zip'
    with zipfile.ZipFile(archive) as z:
        former = pd.read_csv(z.open('international_results-master/former_names.csv'))
    registry = NameRegistry(former)
    history = archive_before(archive, 'international_results-master/results.csv', cutoff)
    history['date'] = pd.to_datetime(history.date)
    history = registry.frame(history, ['home_team', 'away_team'])
    # A venue territory is not a historical football federation. In
    # particular, the former Irish team must not rename an Irish venue.
    history['country'] = history.country.map(registry.normalize)
    history['neutral'] = boolean(history.neutral)
    for col in ['home_score', 'away_score']:
        history[col] = pd.to_numeric(history[col], errors='coerce')
    invalid = (history[['home_score','away_score']].isna().any(axis=1) |
               (history[['home_score','away_score']] < 0).any(axis=1) |
               (history[['home_score','away_score']] % 1 != 0).any(axis=1))
    invalid_rows = history.loc[invalid, MATCH_KEY].astype(str).to_dict('records')
    history = history.loc[~invalid].copy()
    ambiguous = history.duplicated(MATCH_KEY, keep=False)
    ambiguous_rows = history.loc[ambiguous, MATCH_KEY+['home_score','away_score']].astype(str).to_dict('records')
    history = history.loc[~ambiguous].copy()
    history[['home_score','away_score']] = history[['home_score','away_score']].astype(int)
    history = history.rename(columns={'home_score':'recorded_home_score','away_score':'recorded_away_score'})
    goals = archive_before(archive, 'international_results-master/goalscorers.csv', cutoff)
    goals['date'] = pd.to_datetime(goals.date)
    goals = registry.frame(goals, ['home_team','away_team','team'])
    goals['minute'] = pd.to_numeric(goals.minute, errors='coerce')
    grouped_goals = {key: group for key, group in goals.groupby(MATCH_KEY)}
    shootouts = archive_before(archive, 'international_results-master/shootouts.csv', cutoff)
    shootouts['date'] = pd.to_datetime(shootouts.date)
    shootouts = registry.frame(shootouts, ['home_team','away_team','winner'])
    tandas = set(shootouts[MATCH_KEY].itertuples(index=False, name=None))
    fjelstul = fjelstul_evidence(root, cutoff, registry)
    records = []
    for row in history.itertuples(index=False):
        key = (row.date, row.home_team, row.away_team)
        full_h, full_a = row.recorded_home_score, row.recorded_away_score
        recovered, reason = goal_event_evidence(grouped_goals.get(key), row.home_team, row.away_team, full_h, full_a)
        f = fjelstul.get(key)
        reverse = (row.date, row.away_team, row.home_team)
        if f is None and reverse in fjelstul:
            r = fjelstul[reverse]
            f = (r[1], r[0], r[3], r[2])
        conflict = False
        if f is not None:
            if (f[2], f[3]) != (full_h, full_a):
                recovered, reason, conflict = None, 'fjelstul_recorded_score_conflict', True
            elif recovered is not None and recovered != f[:2]:
                recovered, reason, conflict = None, 'regulation_sources_disagree', True
            else:
                recovered, reason = f[:2], 'fjelstul_verified_periods'
        # Standard friendlies can form an explicitly assumed alternative,
        # never a regulation-time label in the primary training dataset.
        # Tandas and conflicting evidence prevent even this alternative.
        assumed = False
        if recovered is None and not conflict and row.tournament == 'Friendly' and key not in tandas:
            if reason == 'no_goal_event_coverage':
                assumed, reason = True, 'friendly_duration_unverified'
        usable = recovered is not None
        item = row._asdict()
        item.update(home_score_90=recovered[0] if usable else np.nan,
                    away_score_90=recovered[1] if usable else np.nan,
                    goal_training_eligible=usable, duration_reason=reason,
                    duration_assumed=assumed,
                    assumed_home_score_90=full_h if assumed else np.nan,
                    assumed_away_score_90=full_a if assumed else np.nan,
                    shootout_record=key in tandas,
                    competition_family=competition_family(row.tournament))
        item['elo_home_score'] = recovered[0] if usable else full_h
        item['elo_away_score'] = recovered[1] if usable else full_a
        item['elo_result_source'] = 'regulation_90' if usable else 'recorded_final_without_shootout_winner'
        records.append(item)
    all_matches = pd.DataFrame(records).sort_values(MATCH_KEY).reset_index(drop=True)
    all_matches['competitive'] = all_matches.competition_family != 'friendly'
    goals_only = all_matches[all_matches.goal_training_eligible].copy()
    goals_only['home_score'] = goals_only.home_score_90.astype(int)
    goals_only['away_score'] = goals_only.away_score_90.astype(int)
    # Reuse only pre-existing fixture metadata, not Openfootball 2026 scores.
    fixture_path = root / 'reports/probabilistic/resolved_fixtures.csv'
    fixtures = pd.read_csv(fixture_path)
    fixtures = registry.frame(fixtures, ['home_team','away_team','country'], 'date_utc')
    fixtures['date'] = pd.to_datetime(fixtures.date_utc, utc=True).dt.tz_localize(None)
    fixtures['neutral'] = boolean(fixtures.neutral)
    fixtures['tournament'] = 'FIFA World Cup'
    expected = set(fixtures[['home_team','away_team']].stack())
    missing = expected-set(all_matches[['home_team','away_team']].stack())
    if len(fixtures) != 72 or len(expected) != 48 or missing:
        raise ValueError(f'Fixture coverage failure: {missing}')
    paths = [archive, raw/'fjelstul_worldcup.zip', fixture_path]
    paths = list(dict.fromkeys(paths + sorted(raw.glob('*'))))
    sources = [{'file':str(p.relative_to(root)), 'sha256':digest_file(p)} for p in paths if p.is_file()]
    roles = {
        'datos nuevos/international_results-master.zip':'Historical results, goal events and shootouts filtered by cutoff; post-cutoff target values are not admitted.',
        'worldcup-master.zip':'Fjelstul historical period verification.',
        'reports/probabilistic/resolved_fixtures.csv':'Fixture metadata only.',
        'datos nuevos/fifa men world ranking.zip':'Secondary enrichment candidate; not used in this preparation.',
        'datos nuevos/fifa_ranking_historico.csv':'Excluded repeated snapshot; fingerprint only.',
        'datos nuevos/transfermarkt-datasets-master.zip':'Repository code without valuation/player data; unavailable enrichment.',
        'datos nuevos/cities15000.zip':'Static altitude reserved for context; fingerprint only in this step.',
        'datos nuevos/open-data-master.zip':'Validation only; fingerprint only in this step.',
        'datos nuevos/worldcup-master.zip':'Openfootball reserved for sealed evaluation; fingerprint only in this step.',
    }
    for source in sources:
        renamed = {'datos nuevos/international_results-master.zip':'data/raw/international_results_current.zip',
                   'worldcup-master.zip':'data/raw/fjelstul_worldcup.zip',
                   'datos nuevos/fifa men world ranking.zip':'data/raw/fifa_rank_semesters.zip',
                   'datos nuevos/fifa_ranking_historico.csv':'data/raw/fifa_rank_repeated_snapshot_excluded.csv',
                   'datos nuevos/transfermarkt-datasets-master.zip':'data/raw/transfermarkt_repository.zip',
                   'datos nuevos/cities15000.zip':'data/raw/geonames_cities15000.zip',
                   'datos nuevos/open-data-master.zip':'data/raw/statsbomb_open_data.zip',
                   'datos nuevos/worldcup-master.zip':'data/raw/openfootball_worldcup.zip'}
        roles.update({renamed.get(k,k):v for k,v in list(roles.items())})
        roles['data/raw/transfermarkt.duckdb'] = 'Dated valuations and snapshot metadata; separate audit before enrichment.'
        source['role'] = roles.get(source['file'].replace('\\','/'), 'Not used as model input in this preparation.')
    audit = {'prediction_cutoff_exclusive':cutoff, 'sources':sources,
             'history_rows':len(all_matches), 'goal_training_rows':len(goals_only),
             'latest_training_result':str(all_matches.date.max().date()),
             'goal_exclusions':all_matches.loc[~all_matches.goal_training_eligible,'duration_reason'].value_counts().to_dict(),
             'duration_methods':all_matches.duration_reason.value_counts().to_dict(),
             'ambiguous_result_rows_excluded':ambiguous_rows,
             'invalid_result_rows_excluded':invalid_rows,
             'duplicate_looking_goal_events_kept':int(goals.duplicated().sum()),
             'normalization':{'expected_worldcup_teams':48,'matched_in_pre_cutoff_history':48,
                              'unmatched':sorted(missing), 'czechoslovakia_is_separate':True,
                              'former_name_intervals_respected':True},
             'goal_events_missing_minute':int(goals.minute.isna().sum()),
             'elo_policy':'Use verified regulation score when available; otherwise recorded final score, possibly including extra time. Never use shootout winner or force a draw from shootout membership.',
             'time_filter':'Apply exclusive date filter before numeric interpretation or retention of any target fields.',
             'market_value':'DuckDB supplied; audited and attached separately by the dated-enrichment step. Current snapshot fields are prohibited predictors.',
             'ranking_repeated_snapshot':'Excluded by approved decision; not a historical source.',
             'ranking_original':'Original archive inspected through 2024, semester 2. Future enrichment may use end-of-semester lag and age <=90 days; no 2026 extrapolation.',
             'statsbomb_role':'Validation only; not an input in this ingestion step.',
             'geonames_role':'Static altitude only; not a model input in this step.',
             'official_2026_results_loaded':False,
             'model_frozen_at_utc':None, 'official_results_loaded_at_utc':None,
             'construction_context':'Retrospective study constructed after the tournament, not a pre-tournament published forecast.',
             'competition_policy':'All valid source competitions retained for historical state; non-FIFA and other tournaments remain explicitly tagged, never silently labeled FIFA-official.',
             'fixture_provenance':'Previously resolved local fixture metadata. Historical publication availability is not independently timestamped.'}
    return StudyData(all_matches, goals_only, fixtures, registry, audit)
