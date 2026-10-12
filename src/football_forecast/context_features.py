"""Dated squad proxies and conservative static venue altitude."""
from pathlib import Path
from collections import defaultdict,deque
import json
import zipfile
import duckdb
import numpy as np
import pandas as pd
from .ingestion import NameRegistry
from .elo_calibration import dated_history,causal_elo,EloParameters,semester_rankings,backward_rank_join
from .preparation import evidence_features

ISO = dict(zip(
 ['Algeria','Argentina','Australia','Austria','Belgium','Bosnia-Herzegovina','Brazil','Cabo Verde','Canada','Colombia','Croatia','Curacao','Czech Republic','DR Congo','Ecuador','Egypt','England','France','Germany','Ghana','Haiti','IR Iran','Iraq','Ivory Coast','Japan','Jordan','Korea Republic','Mexico','Morocco','Netherlands','New Zealand','Norway','Panama','Paraguay','Portugal','Qatar','Saudi Arabia','Scotland','Senegal','South Africa','Spain','Switzerland','Tunisia','Turkey','United States','Uruguay','Uzbekistan','Wales'],
 ['DZ','AR','AU','AT','BE','BA','BR','CV','CA','CO','HR','CW','CZ','CD','EC','EG','GB','FR','DE','GH','HT','IR','IQ','CI','JP','JO','KR','MX','MA','NL','NZ','NO','PA','PY','PT','QA','SA','GB','SN','ZA','ES','CH','TN','TR','US','UY','UZ','GB']))

def altitude_lookup(path):
    with zipfile.ZipFile(path) as archive:
        member = next(n for n in archive.namelist() if n.endswith('.txt'))
        cities = pd.read_csv(archive.open(member),sep='\t',header=None,low_memory=False)
    registry = NameRegistry()
    records = []
    for r in cities.itertuples(index=False,name=None):
        altitude = r[15] if pd.notna(r[15]) else r[16]
        for name in set([str(r[1]),str(r[2])]):
            records.append({'name':registry.normalize(name).casefold(),'iso':r[8],
                            'id':r[0],'altitude':altitude,'lat':r[4],'lon':r[5],
                            'altitude_source':'elevation' if pd.notna(r[15]) else 'dem'})
    frame = pd.DataFrame(records).drop_duplicates(['name','iso','id'])
    unambiguous = frame.groupby(['name','iso']).id.transform('nunique').eq(1)
    return {(r.name,r.iso):(float(r.altitude),r.lat,r.lon,r.altitude_source)
            for r in frame[unambiguous].itertuples(index=False)}

def venue_altitude(frame,lookup):
    registry = NameRegistry()
    out = frame.copy()
    found = []
    for row in out.itertuples(index=False):
        key = (registry.normalize(getattr(row,'city','')).casefold(),ISO.get(row.country,''))
        found.append(lookup.get(key,(np.nan,np.nan,np.nan,'unmatched')))
    out[['venue_altitude_m','venue_latitude','venue_longitude','altitude_source']] = pd.DataFrame(found,index=out.index)
    out['venue_altitude_missing'] = out.venue_altitude_m.isna().astype(int)
    return out

def dated_market_tables(path,cutoff):
    c = duckdb.connect(str(path),read_only=True)
    c.execute('SET threads=2')
    valuations = c.execute('SELECT player_id,date,market_value_in_eur FROM player_valuations WHERE date < CAST(? AS DATE)',[cutoff]).df()
    # Team membership comes from historical game names, never current membership.
    # Only source-tagged international competitions contribute membership.
    memberships = c.execute('''SELECT l.player_id,l.date,
       CASE WHEN l.club_id=g.home_club_id THEN g.home_club_name ELSE g.away_club_name END team
       FROM game_lineups l JOIN games g ON CAST(l.game_id AS VARCHAR)=g.game_id
       WHERE l.date < CAST(? AS DATE) AND g.date < CAST(? AS DATE)
       AND (l.club_id=g.home_club_id OR l.club_id=g.away_club_id)
       AND g.competition_type='national_team_competition' ''',[cutoff,cutoff]).df()
    c.close()
    registry = NameRegistry()
    memberships['team'] = memberships.team.map(registry.normalize)
    memberships['date'] = pd.to_datetime(memberships.date)
    valuations['date'] = pd.to_datetime(valuations.date)
    # Contradictory valuations at the same date are inadmissible.
    conflicts = valuations.groupby(['player_id','date']).market_value_in_eur.nunique().gt(1)
    bad = set(conflicts[conflicts].index)
    valuations = valuations[[tuple(x) not in bad for x in valuations[['player_id','date']].itertuples(index=False,name=None)]]
    return memberships.drop_duplicates(),valuations.drop_duplicates(['player_id','date'])

def squad_proxy_asof(team,date,memberships,valuations,lookback_days=730):
    """Recent observed internationals, not a reconstructed official squad."""
    date = pd.Timestamp(date)
    pool = memberships[(memberships.team==team)&(memberships.date<date)&
                       (memberships.date>=date-pd.Timedelta(days=lookback_days))]
    players = pool.player_id.unique()
    values = valuations[(valuations.player_id.isin(players))&(valuations.date<date)]
    values = values.sort_values('date').drop_duplicates('player_id',keep='last')
    valid = values.market_value_in_eur.dropna().sort_values(ascending=False)
    return {'team':team,'asof_date':str(date.date()),'observed_international_players_730d':len(players),
            'players_with_prior_valuation':len(valid),'valuation_coverage_percent':100*len(valid)/len(players) if len(players) else np.nan,
            'top23_slots_available':min(23,len(valid)),'top23_value_sum':float(valid.head(23).sum()) if len(valid) else np.nan,
            'top23_value_median':float(valid.head(23).median()) if len(valid) else np.nan,
            'official_squad_coverage_percent':np.nan,'proxy_not_official_squad':True}

def venue_sign(frame):
    if not frame.neutral.isin([False,True,0,1]).all():
        raise ValueError('Neutral venue must be an observed boolean indicator')
    return (~frame.neutral.astype(bool)).astype(int)*(
        frame.home_team.eq(frame.country).astype(int)-frame.away_team.eq(frame.country).astype(int))

def coverage_weights(training,complete_history,mappings,cutoff):
    """Training-period strata only; use before the fold boundary."""
    boundary = pd.Timestamp(cutoff)
    if (pd.to_datetime(training.date)>=boundary).any() or (pd.to_datetime(complete_history.date)>=boundary).any():
        raise ValueError('Coverage weights must use training dates strictly before the fold cutoff')
    def shares(frame):
        return pd.concat([frame.home_team.map(mappings),frame.away_team.map(mappings)]).fillna('Unmapped').value_counts(normalize=True)
    ratio = (shares(complete_history)/shares(training)).replace([np.inf,-np.inf],np.nan).fillna(1).clip(.5,2)
    weights = (training.home_team.map(mappings).fillna('Unmapped').map(ratio).fillna(1)+
               training.away_team.map(mappings).fillna('Unmapped').map(ratio).fillna(1))/2
    return weights/weights.mean()

def build_context(root,output,cutoff='2026-06-10'):
    root,output = Path(root),Path(output)
    selection = json.loads((output/'selected_elo.json').read_text(encoding='utf-8'))
    history = dated_history(root/'reports/data_preparation/historical_results.csv','2023-01-01')
    # The entire reserved result period stays unopened in this phase.
    elo,state = causal_elo(history,EloParameters(**selection['parameters']))
    fixtures = pd.read_csv(root/'reports/probabilistic/resolved_fixtures.csv')
    fixtures['date'] = pd.to_datetime(fixtures.date_utc,utc=True).dt.tz_localize(None)
    fixtures['tournament'] = 'FIFA World Cup'
    fixtures['neutral'] = fixtures.neutral.astype(bool)
    with zipfile.ZipFile(root/'data/raw/worldcup_fixtures.zip') as archive:
        venues = pd.read_csv(archive.open('data/group_fixtures.csv'),usecols=['match_id','venue'])
    fixtures = fixtures.merge(venues,on='match_id',validate='one_to_one')
    fixtures['city'] = fixtures.venue.str.rsplit(', ',n=1).str[-1]
    historical,_,future,_ = evidence_features(history,fixtures)
    for col in ['elo_home','elo_away','elo_diff']:
        historical[col] = elo[col].to_numpy()
    opponents = defaultdict(lambda:deque(maxlen=10))
    for _,day in historical.groupby('date',sort=True):
        additions=[]
        for index,row in day.iterrows():
            for team,side,other in [(row.home_team,'home',row.elo_away),(row.away_team,'away',row.elo_home)]:
                historical.at[index,f'opponent_elo_{side}'] = np.mean(opponents[team]) if opponents[team] else selection['parameters']['initial']
                additions.append((team,other))
        for team,other in additions: opponents[team].append(other)
    teams = sorted(set(fixtures.home_team)|set(fixtures.away_team))
    # Do not publish stale 2022 strengths/form as current 2026 features.
    fixture_metadata = set(fixtures.columns)
    for column in future.columns:
        if column not in fixture_metadata:
            future[column] = np.nan
    future['historical_state_pending_phase4'] = True
    future['worldcup'] = 1.
    # Dead host_away is replaced by a directional venue indicator.
    for frame in [historical,future]:
        frame['neutral'] = frame.neutral.astype(bool)
        frame['home_advantage_sign'] = venue_sign(frame)
        frame.drop(columns=['host_home','host_away'],inplace=True,errors='ignore')
        frame['competitive'] = frame.tournament.ne('Friendly')
    rankings = semester_rankings(root/'data/raw/fifa_rank_semesters.zip')
    historical = backward_rank_join(historical,rankings)
    # Prediction information date is the cutoff, not a future match date.
    information_dates = future.date.copy()
    future['date'] = pd.Timestamp(cutoff)
    future = backward_rank_join(future,rankings)
    future['date'] = information_dates
    lookup = altitude_lookup(root/'data/raw/geonames_cities15000.zip')
    historical = venue_altitude(historical,lookup)
    future = venue_altitude(future,lookup)
    historical.to_csv(output/'historical_features.csv',index=False)
    future.to_csv(output/'fixture_features.csv',index=False)
    memberships,valuations = dated_market_tables(root/'data/raw/transfermarkt.duckdb',cutoff)
    memberships.to_csv(output/'dated_international_membership.csv',index=False)
    market = pd.DataFrame([squad_proxy_asof(t,cutoff,memberships,valuations) for t in teams])
    market.to_csv(output/'dated_market_coverage.csv',index=False)
    context = {'information_cutoff_exclusive':cutoff,'historical_feature_cutoff_exclusive':'2023-01-01',
               'elo_parameters_selected_before_reserved_state_extension':True,
               'reserved_result_period_opened':False,'fixture_elo_form_and_rest_pending_phase4':True,
               'reserved_period_metrics_computed':False,'fifa_missing_home_2026':int(future.fifa_missing_home.sum()),
               'fifa_missing_away_2026':int(future.fifa_missing_away.sum()),
               'historical_altitude_coverage':float(historical.venue_altitude_m.notna().mean()),
               'fixture_altitude_coverage':float(future.venue_altitude_m.notna().mean()),
               'geography_matching':'Exact normalized primary/ASCII city + explicit country ISO; ambiguous cities remain missing. Elevation with DEM fallback, provenance retained.',
               'origin_altitude_difference':'Unavailable: country identity is not training-camp altitude.',
               'travel_distance':'Unavailable: dated team travel or camp locations not provided; city coordinates are not actual itineraries.',
               'rest':'Days since last observed international match; not verified player recovery time.',
               'market_membership_first_date':str(memberships.date.min().date()) if len(memberships) else None,
               'market_membership_last_date':str(memberships.date.max().date()) if len(memberships) else None,
               'market_pre2023_membership_rows':int((memberships.date<'2023-01-01').sum()),
               'worldcup_teams_with_dated_player_pool':int(market.observed_international_players_730d.gt(0).sum()),
               'market_decision':'Excluded from primary model: no dated membership before 2023 allows feature validation without opening reserved period. As-of adapter and coverage diagnostics retained.',
               'feature_selection_pending_phase3':['recent form','rest','altitude','coverage weights'],
               'official_2026_results_loaded':False}
    (output/'context_audit.json').write_text(json.dumps(context,indent=2),encoding='utf-8')
    report_path = output/'RESULTADOS.md'
    report_path.write_text(report_path.read_text(encoding='utf-8').split('\n## Variables y cobertura')[0],encoding='utf-8')
    with report_path.open('a',encoding='utf-8') as stream:
        stream.write(f"\n## Variables y cobertura\n\nUso los parámetros Elo seleccionados para calcular estado y variables disponibles antes de cada partido. Construyo las variables históricas solo hasta 2022. Dejo Elo, forma y descanso del fixture pendientes hasta abrir el periodo reservado en Fase 4; no presento el estado de 2022 como vigente en 2026. El ranking de ambas selecciones está faltante en los 72 partidos de 2026.\n\nLa altitud se identifica en {context['historical_altitude_coverage']:.1%} del historial y {context['fixture_altitude_coverage']:.1%} de las sedes del fixture, con ciudad y país sin ambigüedad; conservo la procedencia de elevación o DEM. El descanso significa días desde el último partido internacional observado. No tengo datos para reconstruir viajes reales o altitud del lugar de entrenamiento.\n\nLas alineaciones internacionales fechadas empiezan en {context['market_membership_first_date']}; no hay ninguna antes de 2023. Identifico un conjunto de jugadores observados en los últimos 730 días para {context['worldcup_teams_with_dated_player_pool']} de las 48 selecciones. Consulto las valoraciones anteriores al corte y publico cobertura del conjunto observado, no de una convocatoria oficial, en dated_market_coverage.csv. No incorporo mercado al modelo principal: no puedo validar su aporte en los bloques de selección sin abrir el periodo reservado. El adaptador as-of queda implementado para una fuente con más historia.\n\nLa ventaja de sede se representa con signo respecto a ambos equipos; elimino host_away del conjunto de características de este diseño. La referencia independiente conserva su contrato original. La adopción de descanso, forma y altitud depende de ablaciones temporales en Fase 3.\n")
    return context
