"""Historical state, exclusions and sensitivity before model selection."""
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from .ingestion import load_study_data, digest_file

SCENARIO_LABELS = {
    'historial_completo_90_verificado_o_final_registrado':'Historial completo con prioridad a 90 minutos',
    'historial_completo_final_registrado':'Historial completo con marcador final registrado',
    'solo_marcadores_90_verificables':'Solo marcadores a 90 minutos admisibles',
    'incluyendo_duracion_supuesta_amistosos':'Marcadores verificables y amistosos de duración supuesta',
    'baseline_elo_amistosos':'Elo con amistosos y Mundiales',
}

def markdown_table(frame,precision=2):
    """Render ordinary tables without adding a tabulate dependency."""
    columns = list(frame.columns)
    lines = ['| '+' | '.join(columns)+' |', '| '+' | '.join(['---']*len(columns))+' |']
    for row in frame.itertuples(index=False,name=None):
        items = [f'{x:.{precision}f}' if isinstance(x,(float,np.floating)) else str(x) for x in row]
        lines.append('| '+' | '.join(items)+' |')
    return '\n'.join(lines)

class EvidenceState:
    """State updated by date; uncertain scores never enter 90-minute windows.

    Elo settings here are held fixed to isolate data-policy sensitivity. Their
    temporal calibration is a separate model-selection operation.
    """
    def __init__(self):
        self.elo = defaultdict(lambda: 1500.)
        self.games = defaultdict(int)
        self.recent = defaultdict(lambda: deque(maxlen=10))
        self.last_date = {}

    def features(self, row):
        h, a = row.home_team, row.away_team
        x = {'elo_home':self.elo[h], 'elo_away':self.elo[a],
             'elo_diff':self.elo[h]-self.elo[a], 'neutral':float(row.neutral),
             'host_home':float(not row.neutral and h==row.country),
             'host_away':float(not row.neutral and a==row.country),
             'worldcup':float(row.tournament=='FIFA World Cup')}
        for team, side in [(h,'home'),(a,'away')]:
            data = list(self.recent[team])
            x[f'games_{side}'] = min(self.games[team], 100)
            x[f'days_rest_{side}'] = ((row.date-self.last_date[team]).days
                                     if team in self.last_date else np.nan)
            x[f'opponent_elo_{side}'] = np.mean([r[3] for r in data]) if data else 1500.
            for n in [5,10]:
                block = data[-n:]
                known = [r for r in block if np.isfinite(r[0]) and np.isfinite(r[1])]
                x[f'goals_90_coverage{n}_{side}'] = len(known)/len(block) if block else 0.
                for field, idx in [('gf',0),('ga',1)]:
                    x[f'{field}{n}_{side}'] = (sum(r[idx] for r in known)+3*1.3)/(len(known)+3)
            x[f'form5_{side}'] = (sum(r[2] for r in data[-5:])+1.5)/(len(data[-5:])+3)
        return x

    def update_day(self, rows, policy='verified90_else_recorded'):
        delta = defaultdict(float)
        additions = []
        for row in rows:
            h, a = row.home_team, row.away_team
            if policy == 'recorded_all':
                gf, ga = row.recorded_home_score, row.recorded_away_score
            else:
                gf, ga = row.elo_home_score, row.elo_away_score
            host = 60*((h==row.country)-(a==row.country)) if not row.neutral else 0
            expected = 1/(1+10**(-(self.elo[h]-self.elo[a]+host)/400))
            outcome = 1. if gf>ga else 0. if gf<ga else .5
            k = 24 if row.tournament=='FIFA World Cup' else 16
            delta[h] += k*(outcome-expected)
            delta[a] -= k*(outcome-expected)
            additions.extend([(h,(row.home_score_90,row.away_score_90,outcome,self.elo[a]),row.date),
                              (a,(row.away_score_90,row.home_score_90,1-outcome,self.elo[h]),row.date)])
        for team, change in delta.items():
            self.elo[team] += change
        for team, item, date in additions:
            self.recent[team].append(item)
            self.games[team] += 1
            self.last_date[team] = date

def evidence_features(history, fixtures):
    state = EvidenceState()
    records = []
    for _, day in history.groupby('date', sort=True):
        rows = list(day.itertuples(index=False))
        for row in rows:
            records.append({**row._asdict(), **state.features(row)})
        state.update_day(rows)
    full = pd.DataFrame(records)
    training = full[full.goal_training_eligible].copy()
    training['home_score'] = training.home_score_90.astype(int)
    training['away_score'] = training.away_score_90.astype(int)
    training['target'] = np.where(training.home_score>training.away_score,0,
                                  np.where(training.home_score==training.away_score,1,2))
    future = pd.DataFrame([{**row._asdict(), **state.features(row)}
                           for row in fixtures.itertuples(index=False)])
    return full, training, future, state

def sensitivity(history, teams):
    assumed_alternative = history[history.goal_training_eligible | history.duration_assumed].copy()
    mask = assumed_alternative.duration_assumed
    assumed_alternative.loc[mask,'home_score_90'] = assumed_alternative.loc[mask,'assumed_home_score_90']
    assumed_alternative.loc[mask,'away_score_90'] = assumed_alternative.loc[mask,'assumed_away_score_90']
    cases = {
        'historial_completo_90_verificado_o_final_registrado':history,
        'historial_completo_final_registrado':history,
        'solo_marcadores_90_verificables':history[history.goal_training_eligible],
        'incluyendo_duracion_supuesta_amistosos':assumed_alternative,
        'baseline_elo_amistosos':history[history.tournament.isin(['Friendly','FIFA World Cup'])],
    }
    snapshots, rows = {}, []
    for label, frame in cases.items():
        state = EvidenceState()
        for _, day in frame.groupby('date',sort=True):
            state.update_day(list(day.itertuples(index=False)),
                             'recorded_all' if label=='historial_completo_final_registrado' else 'verified90_else_recorded')
        order = sorted(state.elo, key=state.elo.get, reverse=True)
        rank = {team:i+1 for i,team in enumerate(order)}
        snapshots[label] = {team:state.elo[team] for team in teams}
        for team in teams:
            rows.append({'scenario':label,'team':team,'elo':state.elo[team],
                         'rank_in_source_entities':rank.get(team), 'matches':state.games[team],
                         'history_rows_in_scenario':len(frame)})
    default = snapshots['historial_completo_90_verificado_o_final_registrado']
    reference = np.array([default[t] for t in teams])
    reference_ranks = rankdata(-reference,method='min')
    summaries = []
    for label, values in snapshots.items():
        diff = np.array([values[t]-default[t] for t in teams])
        ratings = np.array([values[t] for t in teams])
        ranks = rankdata(-ratings,method='min')
        centered = (ratings-ratings.mean())-(reference-reference.mean())
        summaries.append({'scenario':label,'mean_absolute_elo_difference':float(abs(diff).mean()),
                          'max_absolute_elo_difference':float(abs(diff).max()),
                          'spearman_rank_correlation_48':float(spearmanr(reference,ratings).statistic),
                          'reference_top20_teams_changing_rank':int(((reference_ranks<=20)&(ranks!=reference_ranks)).sum()),
                          'top20_membership_changes':int(((reference_ranks<=20)!=(ranks<=20)).sum()),
                          'mean_absolute_centered_difference':float(abs(centered).mean()),
                          'max_absolute_centered_difference':float(abs(centered).max()),
                          'interpretation':'Descriptive sensitivity of historical state; not a predictive-performance metric.'})
    detailed = pd.DataFrame(rows)
    detailed['elo_centered_48'] = detailed.elo-detailed.groupby('scenario').elo.transform('mean')
    detailed['rank_in_worldcup_cohort_48'] = detailed.groupby('scenario').elo.rank(ascending=False,method='min').astype(int)
    baseline = detailed[detailed.scenario=='historial_completo_90_verificado_o_final_registrado'].set_index('team').elo_centered_48
    detailed['centered_difference_from_reference'] = detailed.elo_centered_48-detailed.team.map(baseline)
    return detailed, pd.DataFrame(summaries)

def prepare_local_data(root='.', output='reports/data_preparation', cutoff='2026-06-10'):
    root, output = Path(root), Path(output)
    print('Leyendo fuentes locales con corte previo a los resultados de 2026...',flush=True)
    data = load_study_data(root, cutoff)
    output.mkdir(parents=True,exist_ok=True)
    data.history.to_csv(output/'historical_results.csv',index=False)
    data.goal_history.to_csv(output/'goal_training_90.csv',index=False)
    exclusions = data.history[~data.history.goal_training_eligible]
    exclusions.to_csv(output/'goal_exclusions.csv',index=False)
    print('Calculando estado historico por fecha y cobertura de goles...',flush=True)
    full, training, future, state = evidence_features(data.history, data.fixtures)
    full.to_csv(output/'historical_features.csv',index=False)
    training.to_csv(output/'goal_training_features.csv',index=False)
    future.to_csv(output/'fixture_features.csv',index=False)
    counts = data.history.groupby(['tournament','competition_family','duration_reason','goal_training_eligible']).size().rename('matches').reset_index()
    counts.to_csv(output/'competition_coverage.csv',index=False)
    teams = sorted(set(data.fixtures.home_team)|set(data.fixtures.away_team))
    print('Comparando cinco politicas del historial; sin entrenar modelos...',flush=True)
    snapshots, summaries = sensitivity(data.history, teams)
    snapshots.to_csv(output/'elo_policy_sensitivity.csv',index=False)
    summaries.to_csv(output/'sensitivity_summary.csv',index=False)
    coverage = []
    for team in teams:
        matches = data.history[(data.history.home_team==team)|(data.history.away_team==team)]
        coverage.append({'team':team,'history_matches':len(matches),
                         'goal_training_matches':int(matches.goal_training_eligible.sum()),
                         'competitive_matches':int(matches.competitive.sum()),
                         'market_value_coverage':np.nan,'market_value_available':False})
    pd.DataFrame(coverage).to_csv(output/'team_coverage.csv',index=False)
    aliases = []
    for source, columns, date_col, path, member in [
        ('martj42',['home_team','away_team'],'date',root/'data/raw/international_results_current.zip','international_results-master/results.csv'),
        ('fifa_semesters',['team'],None,root/'data/raw/fifa_rank_semesters.zip','fifa_mens_rank.csv')]:
        with __import__('zipfile').ZipFile(path) as archive:
            frame = pd.read_csv(archive.open(member),usecols=columns+([date_col] if date_col else []))
        if date_col:
            frame = frame[frame[date_col]<cutoff]
        raw_names = sorted(set(frame[columns].stack()))
        for raw_name in raw_names:
            canonical = data.name_registry.normalize(raw_name)
            if canonical in teams:
                aliases.append({'source':source,'raw_name':raw_name,'canonical':canonical})
    for raw_name, mappings in data.name_registry.former.items():
        for start,end,current in mappings:
            canonical = data.name_registry.normalize(current)
            aliases.append({'source':'former_names','raw_name':raw_name,'canonical':canonical,
                            'valid_from':str(start.date()),'valid_through':str(end.date())})
    pd.DataFrame(aliases).to_csv(output/'name_registry.csv',index=False)
    audit = data.audit
    audit['preparation_completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    audit['model_training_executed_in_this_step'] = False
    audit['field_definitions'] = {
        'recorded_home_score':'Local recorded final goals, including extra time if played; excludes shootout conversions.',
        'home_score_90':'Regulation score reconstructed from evidence; missing when unverified.',
        'goal_training_eligible':'Verified regulation target, including the invariant zero-score case. Assumed friendly duration is excluded.',
        'duration_assumed':'Standard friendly duration is available only as a sensitivity alternative; not admitted to primary goals training.',
        'competitive':'Non-Friendly label in the source; not a certification of FIFA-official status.',
        'country':'Venue territory normalized without historical federation-succession mapping.',
    }
    audit['sensitivity'] = summaries.to_dict('records')
    audit['elo_settings_for_data_sensitivity'] = {'initial':1500,'friendly_and_other_k':16,'worldcup_k':24,
                                                 'home_advantage':60,'calibrated':False,
                                                 'purpose':'Hold settings fixed to isolate historical-data and duration policy.'}
    audit['cutoff_assertions'] = {'history_dates_strictly_before_cutoff':bool((data.history.date<pd.Timestamp(cutoff)).all()),
                                 'same_day_features_precede_all_updates':True,
                                 'unverified_goals_excluded_from_goal_windows':True}
    audit['source_entity_scope'] = 'Ranks include all international entities in the source, not an asserted official FIFA world ranking.'
    baseline_model = root/'reports/probabilistic/models/deployment.joblib'
    audit['baseline_elo_amistosos_artifact'] = {'model_sha256':digest_file(baseline_model) if baseline_model.exists() else None,
                                               'preserved':True,
                                               'definition':'Existing saved model remains a baseline; no retraining or score overwrite in preparation.'}
    audit['outputs'] = [{'file':p.name,'sha256':digest_file(p)} for p in sorted(output.glob('*.csv'))]
    (output/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    by_family = data.history.groupby('competition_family').agg(
        historial=('date','size'), goles_90=('goal_training_eligible','sum'))
    recent = data.history[data.history.date>='2023-01-01'].groupby('competition_family').agg(
        historial=('date','size'), goles_90=('goal_training_eligible','sum'))
    selected = snapshots[snapshots.team.isin(['Colombia','Portugal'])]
    family_labels = {'friendly':'Amistosos','continental':'Campeonatos continentales',
                     'qualification':'Eliminatorias','nations_league':'Ligas de Naciones',
                     'worldcup':'Mundiales','other_tournament':'Otras competiciones','non_fifa':'Torneos no FIFA'}
    by_family.index = by_family.index.map(family_labels)
    recent.index = recent.index.map(family_labels)
    sensitivity_display = summaries[['scenario','mean_absolute_elo_difference','max_absolute_elo_difference']].copy()
    sensitivity_display['scenario'] = sensitivity_display.scenario.map(SCENARIO_LABELS)
    sensitivity_display.columns = ['Política del historial','Cambio medio de Elo','Cambio máximo de Elo']
    selected_display = selected[['scenario','team','elo','rank_in_source_entities','matches']].copy()
    selected_display['scenario'] = selected_display.scenario.map(SCENARIO_LABELS)
    selected_display.columns = ['Política del historial','Selección','Elo','Puesto en las entidades de la fuente','Partidos']
    summary = f'''# Datos y definición del resultado

Construí el estudio con archivos locales y un corte exclusivo del {cutoff}. El trabajo se realiza con el torneo ya jugado; no representa un pronóstico publicado antes del Mundial. En esta preparación no entrené modelos ni cargué resultados oficiales posteriores al corte.

## Qué representa cada resultado

Conservo {len(data.history):,} partidos en el historial. Para predecir goles a 90 minutos dispongo de {len(data.goal_history):,} marcadores con evidencia. Los {len(exclusions):,} casos restantes conservan su participación en el historial, pero no aportan etiquetas de goles ni goles a las ventanas recientes. No admito supuestos de duración en el conjunto principal. La alternativa de sensibilidad admite {int(data.history.duration_assumed.sum()):,} amistosos adicionales suponiendo duración estándar.

Uso eventos completos que coinciden con los goles de ambos equipos y que tienen minutos válidos. En martj42 el descuento se codifica como minuto 90; Fjelstul distingue los periodos de prórroga. Conservo las filas de eventos aparentemente repetidas y compruebo sus cantidades contra el marcador. Una tanda no determina automáticamente un empate en el partido.

Para Elo utilizo el marcador a 90 minutos cuando puedo reconstruirlo. Si no puedo, uso el marcador final registrado, que puede incluir prórroga. No uso al ganador de la tanda. Marco esta diferencia para medir su efecto.

## Cobertura por competición

{markdown_table(by_family.rename(columns={'historial':'Partidos del historial','goles_90':'Marcadores admisibles'}).reset_index().rename(columns={'competition_family':'Tipo de competición'}))}

El grupo «other_tournament» conserva competiciones cuya categoría requiere una clasificación más específica; no afirmo que todas sean competiciones oficiales FIFA. Las competiciones identificadas como no FIFA permanecen etiquetadas.

## Cobertura desde 2023 hasta el corte

{markdown_table(recent.rename(columns={'historial':'Partidos del historial','goles_90':'Marcadores admisibles'}).reset_index().rename(columns={'competition_family':'Tipo de competición'}))}

Estos son tamaños de conjuntos disponibles, no métricas de predicción.

## Sensibilidad de la política del historial

Mantengo los mismos parámetros Elo para comparar únicamente qué partidos y marcadores incorpora el historial. La elección y calibración temporal de esos parámetros es una operación posterior y separada.

{markdown_table(sensitivity_display)}

{markdown_table(selected_display)}

Los puestos se calculan sobre las entidades presentes en cada escenario, no son puestos del ranking FIFA. Un cambio de Elo no demuestra mejor capacidad predictiva. La evaluación de modelos debe comprobarlo en partidos que no intervienen en su ajuste.

## Fuentes disponibles y límites

No dispongo de tablas de jugadores o valoraciones de Transfermarkt. Por eso no calculo cobertura ni valor de mercado; la cobertura queda faltante, no en cero. El archivo de ranking con fotografía repetida está excluido. El ranking por semestre llega a 2024 y solo podrá estudiarse con disponibilidad conservadora posterior al semestre y antigüedad máxima de 90 días. No hay ranking vigente de 2026.

Mantengo Fjelstul y Openfootball como fuentes distintas. No leo el README ni los marcadores de 2026 de Openfootball para decidir el diseño. StatsBomb queda reservado para validación de marcadores y periodos. GeoNames se reserva para altitud estática.

No sello un modelo en esta preparación. En la auditoría dejo vacías las fechas de congelado y carga de resultados oficiales; se registrarán al ejecutar esas operaciones.
'''
    (output/'RESULTADOS.md').write_text(summary,encoding='utf-8')
    print(json.dumps({'history_rows':len(data.history),'goal_training_rows':len(data.goal_history),
                      'excluded_goal_rows':len(exclusions),'duration_methods':audit['duration_methods'],
                      'output':str(output.resolve())},indent=2,ensure_ascii=True),flush=True)
    return data, audit
