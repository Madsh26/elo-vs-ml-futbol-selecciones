"""Local metadata audit. Snapshot attributes never become historical features."""
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import duckdb
from .ingestion import NameRegistry, archive_before, MATCH_KEY, digest_file
from .preparation import markdown_table

def inspect_sources(root, output, cutoff):
    root, output = Path(root), Path(output)
    raw = root/'data/raw'
    registry = NameRegistry()
    c = duckdb.connect(str(raw/'transfermarkt.duckdb'), read_only=True)
    c.execute('SET threads=2')
    metadata = {}
    for (table,) in c.execute('SHOW TABLES').fetchall():
        schema = c.execute(f'DESCRIBE "{table}"').fetchall()
        cols = [r[0] for r in schema]
        counts = c.execute(f'SELECT count(*), '+', '.join(f'count(*)-count("{col}")' for col in cols)+f' FROM "{table}"').fetchone()
        dates = {}
        for col,typ,*_ in schema:
            if typ in ('DATE','TIMESTAMP'):
                values = c.execute(f'SELECT min("{col}"),max("{col}") FROM "{table}"').fetchone()
                dates[col] = [str(v) if v is not None else None for v in values]
        duplicate_scope = f"WHERE date < DATE '{cutoff}'" if 'date' in cols else ''
        if table in ('club_games','game_events','appearances') and 'date' not in cols:
            duplicates = None  # No target-bearing post-cutoff rows are inspected.
        else:
            groups = ','.join(f'"{col}"' for col in cols)
            duplicates = c.execute(f'SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM "{table}" {duplicate_scope} GROUP BY {groups})').fetchone()[0]
        metadata[table] = {'rows':counts[0], 'schema':[{ 'column':r[0],'type':r[1]} for r in schema],
                           'nulls':dict(zip(cols,counts[1:])), 'date_ranges':dates,
                           'identical_duplicate_rows':int(duplicates) if duplicates is not None else None,
                           'duplicate_scope':'Pre-cutoff when dated; unavailable for undated event tables; otherwise metadata snapshot.'}
    # Citizenship and team membership are inspected as snapshot metadata only.
    players = c.execute('SELECT player_id,country_of_citizenship FROM players').df()
    valuations = c.execute('SELECT player_id,date,market_value_in_eur FROM player_valuations WHERE date < CAST(? AS DATE)',[cutoff]).df()
    post = c.execute('SELECT count(*) FROM player_valuations WHERE date >= CAST(? AS DATE)',[cutoff]).fetchone()[0]
    nations = c.execute('SELECT name,country_name,confederation FROM national_teams').df()
    countries = c.execute('SELECT country_name,confederation FROM countries').df()
    c.close()
    valuations['date'] = pd.to_datetime(valuations.date)
    players['team'] = players.country_of_citizenship.map(registry.normalize)
    conflicting = valuations.groupby(['player_id','date']).market_value_in_eur.nunique().gt(1)
    bad = set(conflicting[conflicting].index)
    valuations = valuations[[tuple(x) not in bad for x in valuations[['player_id','date']].itertuples(index=False,name=None)]]
    valuations = valuations.drop_duplicates(['player_id','date'])
    latest = valuations.sort_values('date').drop_duplicates('player_id',keep='last')
    snapshot = players.merge(latest,on='player_id',how='left')
    fixtures = pd.read_csv(root/'reports/probabilistic/resolved_fixtures.csv')
    teams = sorted(set(fixtures.home_team)|set(fixtures.away_team))
    market = []
    for team in teams:
        block = snapshot[snapshot.team==team]
        values = block.market_value_in_eur.dropna().sort_values(ascending=False)
        market.append({'team':team,'players_in_database_citizenship_snapshot':len(block),
                       'players_with_pre_cutoff_valuation':len(values),
                       'percent_of_database_players_valued':100*len(values)/len(block) if len(block) else np.nan,
                       'available_top23_slots':min(23,len(values)),
                       'top23_value_sum_diagnostic_only':values.head(23).sum() if len(values) else np.nan,
                       'historical_roster_coverage_percent':np.nan,
                       'historical_membership_verified':False})
    pd.DataFrame(market).to_csv(output/'transfermarkt_coverage.csv',index=False)
    mappings = {}
    for frame,column in [(countries,'country_name'),(nations,'name')]:
        for name,conf in frame[[column,'confederation']].itertuples(index=False,name=None):
            if conf in {'AFC','CAF','CONCACAF','CONMEBOL','OFC','UEFA'}:
                mappings[registry.normalize(name)] = conf
    # These administrative identities are diagnostic strata, not predictors.
    for conf,names in {'CAF':['Cabo Verde','Ivory Coast','DR Congo','South Africa','Ghana'],
                       'CONCACAF':['Curacao','Haiti'], 'AFC':['Korea Republic','IR Iran'],
                       'UEFA':['Turkey']}.items():
        mappings.update({name:conf for name in names})
    missing = sorted(set(teams)-set(mappings))
    history = pd.read_csv(output/'historical_results.csv',parse_dates=['date'])
    counts = []
    for side in ('home','away'):
        counts.append(pd.DataFrame({'confederation':history[f'{side}_team'].map(mappings).fillna('Unmapped historical entity'),
                                   'goal_training_eligible':history.goal_training_eligible,'year':history.date.dt.year,
                                   'competition':history.competition_family}))
    appearances = pd.concat(counts,ignore_index=True)
    coverage = []
    for dimension in ['confederation','competition','year']:
        grouped = appearances.groupby(dimension).goal_training_eligible.agg(['size','sum'])
        grouped['historical_share'] = grouped['size']/grouped['size'].sum()
        grouped['goal_training_share'] = grouped['sum']/grouped['sum'].sum()
        grouped['representation_ratio'] = grouped.goal_training_share/grouped.historical_share
        grouped['dimension'] = dimension
        grouped['stratum'] = grouped.index
        coverage.append(grouped.reset_index(drop=True))
    cover = pd.concat(coverage,ignore_index=True)
    cover.to_csv(output/'coverage_bias.csv',index=False)
    conf = cover[cover.dimension=='confederation']
    goals = archive_before(raw/'international_results_current.zip','international_results-master/goalscorers.csv',cutoff)
    goals = registry.frame(goals,['home_team','away_team','team'])
    goals['date'] = pd.to_datetime(goals.date)
    goals['minute'] = pd.to_numeric(goals.minute,errors='coerce')
    extras = goals.groupby(MATCH_KEY).minute.max().rename('latest_goal_minute').reset_index()
    friendly = history[(history.competition_family=='friendly')&(history.duration_reason=='martj42_complete_goal_events')].merge(extras,on=MATCH_KEY,how='left')
    stats = {'complete_event_friendlies':len(friendly),'friendlies_with_goal_after_minute90':int((friendly.latest_goal_minute>90).sum()),
             'proportion_with_goal_after_minute90':float((friendly.latest_goal_minute>90).mean()) if len(friendly) else None,
             'complete_event_friendlies_in_shootouts':int(friendly.shootout_record.sum()),
             'all_recorded_friendlies_in_shootouts':int(history.loc[history.competition_family=='friendly','shootout_record'].sum()),
             'interpretation':'Event-complete nonzero friendlies only. No claim about the duration of matches without complete events; stoppage is encoded as 90.'}
    audit_path = output/'data_audit.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    audit['transfermarkt'] = {'file':'data/raw/transfermarkt.duckdb','sha256':digest_file(raw/'transfermarkt.duckdb'),
                              'tables':metadata,'post_cutoff_valuations_excluded':post,
                              'pre_cutoff_valuations_loaded':len(valuations),'conflicting_player_date_keys_excluded':len(bad),
                              'national_teams_role':'Current undated snapshot; no historical predictor or ranking.',
                              'market_feature_decision':'Dated valuations can be joined as-of. Undated citizenship does not establish historical national-team membership; nationality aggregates are diagnostic only, excluded from primary models.',
                              'coverage_denominator':'Database players by current citizenship, not a verified national squad. True squad coverage is unavailable.',
                              'unmapped_worldcup_confederations':missing}
    audit['friendly_duration_evidence'] = stats
    audit['coverage_bias'] = conf.to_dict('records')
    audit['confederation_scope'] = 'Current administrative confederations for coverage diagnostics only; historical changes not silently asserted. Unmapped entities retained as an explicit stratum.'
    pd.DataFrame([{'team':t,'confederation':mappings.get(t)} for t in sorted(mappings)]).to_csv(output/'confederations.csv',index=False)
    audit['outputs'] = [{'file':p.name,'sha256':digest_file(p)} for p in sorted(output.glob('*.csv'))]
    audit_path.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    friendly_percentage = str(round(100*stats['proportion_with_goal_after_minute90'],2)) if len(friendly) else 'proporción no estimable: no hay amistosos con eventos completos'
    text = f'''\n## Duración observable de amistosos\n\nEntre los {len(friendly)} amistosos con eventos completos, {stats['friendlies_with_goal_after_minute90']} tienen algún gol posterior al minuto 90 ({friendly_percentage}); {stats['complete_event_friendlies_in_shootouts']} aparecen en tandas. Esta muestra seleccionada no demuestra la duración de los amistosos sin eventos. El descuento está codificado como minuto 90.\n\n## Representación del entrenamiento de goles\n\nCuento participaciones de selecciones: cada partido aporta dos. Las tablas por año, competición y confederación están en `coverage_bias.csv`. Uso la confederación actual únicamente para describir cobertura; conservo las entidades históricas sin cruce como categoría explícita.\n\n{markdown_table(conf[['stratum','size','sum','representation_ratio']].rename(columns={'stratum':'Confederación','size':'Participaciones históricas','sum':'Participaciones con goles verificables','representation_ratio':'Representación relativa'}))}\n\nLa selección de partidos con eventos puede cambiar qué selecciones y competiciones aprende el modelo. En la comparación temporal contrastaré entrenamiento ordinario con pesos por confederación calculados solo en el bloque de entrenamiento, acotados entre 0,5 y 2. El grupo sin cruce seguirá identificado; no inventaré afiliaciones históricas.\n\n## Valoraciones y pertenencia a selecciones\n\nInspeccioné el DuckDB en modo de solo lectura. Excluí {post} valoraciones del corte o posteriores. `transfermarkt_coverage.csv` informa el porcentaje de jugadores de la base con valoración anterior al corte para las 48 selecciones. El denominador es la población de jugadores registrada por nacionalidad actual; no es una plantilla oficial de 23 jugadores.\n\nNo uso valor actual, club actual, convocatorias actuales ni el ranking de `national_teams`. Las nacionalidades disponibles tampoco tienen fechas de vigencia. Por eso el agregado por nacionalidad queda como diagnóstico y adaptador experimental, sin atribuirle pertenencia histórica verificada ni usarlo en el modelo principal. Para incorporar valor de una plantilla necesito una relación fechada entre jugador y selección.\n'''
    summary_path = output/'RESULTADOS.md'
    base = summary_path.read_text(encoding='utf-8').split('\n## Duración observable de amistosos')[0]
    start = base.find('No dispongo de tablas de jugadores')
    end = base.find('\n\nMantengo Fjelstul',start)
    if start>=0 and end>=0:
        base = base[:start]+'Inspeccioné las tablas de Transfermarkt; su cobertura y límites se detallan a continuación. Excluyo el ranking de fotografía repetida. El ranking semestral termina en 2024 y no se extrapola a 2026.'+base[end:]
    summary_path.write_text(base+text,encoding='utf-8')
    return audit
