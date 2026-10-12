"""Executed data inventory and a readable dictionary for the portfolio."""
from pathlib import Path
import json
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
from verify_final_evaluation import frozen_checks,digest,utc_now
from football_forecast.preparation import markdown_table
frozen_checks()
folder=ROOT/'reports/final_evaluation'
history=pd.read_csv(folder/'history_precut.csv',parse_dates=['date'])
features=pd.read_csv(folder/'features_precut.csv',parse_dates=['date'])
training=history[history.date.ge('2000-01-01')&history.date.lt('2023-01-01')]
evaluation=history[history.date.ge('2023-01-01')]
from football_forecast.elo_calibration import semester_rankings
rank=semester_rankings(ROOT/'data/raw/fifa_rank_semesters.zip')
inventory={'executed_at_utc':utc_now(),'history_matches':len(history),'history_first_date':str(history.date.min().date()),
 'history_latest_date':str(history.date.max().date()),'historical_team_entities':len(set(history.home_team)|set(history.away_team)),
 'model_training_matches':len(training),'model_training_first_date':str(training.date.min().date()),
 'model_training_latest_date':str(training.date.max().date()),'pre2023_history_matches':int(history.date.lt('2023-01-01').sum()),
 'pre2023_walk_forward_matches':len(pd.read_csv(ROOT/'reports/models_selected/predictions_elo.csv')),
 'semiconfirmatory_matches':len(evaluation),'group_forecasts':72,'worldcup_teams':48,
 'independent_verified_duration_matches':int(history.goal_training_eligible.sum()),
 'shootouts':int(history.shootout_record.sum()),'proven_extra_time_goal_matches':int(history.proven_extra_time_goals.gt(0).sum()),
 'goals_duration_assumed_matches':int(history.x12_uncertain_timing.sum()),
 'fifa_semester_rows_used_for_diagnostic':len(rank),'fifa_last_conservative_availability':str(rank.available_date.max().date()),
 'history_sha256':digest(folder/'history_precut.csv'),'features_sha256':digest(folder/'features_precut.csv'),
 'model_features':['elo_effective','gf_diff','ga_diff','form_diff','opponent_diff','goal_coverage_sum'],
 'feature_ranges':{c:{'minimum':float(features[c].min()),'maximum':float(features[c].max()),
                     'missing':int(features[c].isna().sum()),'distinct_values':int(features[c].nunique())}
                     for c in ['elo_effective','gf_diff','ga_diff','form_diff','opponent_diff','goal_coverage_sum']}}
(folder/'data_inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False),encoding='utf-8')
population=history.groupby('competition_family').agg(partidos=('date','size'),inicio=('date','min'),fin=('date','max')).reset_index()
population.to_csv(folder/'data_competition_coverage.csv',index=False)
year=history.groupby(history.date.dt.year).size().rename('matches').reset_index()
year.to_csv(folder/'data_year_coverage.csv',index=False)
raw_fields=[
 ['date','Fecha del partido en la fuente; granularidad diaria','Corte temporal y orden causal'],
 ['home_team / away_team','Equipos A y B del registro; A no implica ser anfitrión','Identificación y orden de probabilidades'],
 ['home_score / away_score','Marcador final registrado, sin goles de la tanda','Origen de las etiquetas; puede incluir prórroga'],
 ['tournament','Nombre de competición','Pesos Elo y estratos, no variable final de la logística'],
 ['city / country','Ciudad y país de disputa','Sede real; altitud solo en ablación'],
 ['neutral','Indica campo neutral según la fuente','Desactivar ventaja de sede'],
 ['goalscorers.minute','Minuto del gol; martj42 codifica descuento como 90','Verificación de goles >90 cuando eventos completos'],
 ['goalscorers.team','Equipo al que se acredita el gol, incluidos autogoles','Reconciliación de conteos; no deduplico filas idénticas automáticamente'],
 ['shootouts.winner','Ganador de la tanda','Marca de tanda; no determina el resultado a 90 minutos'],
 ['former / current / start_date / end_date','Alias históricos con intervalos de fechas','Normalización; no fusiono Czechoslovakia con Czech Republic']]
normalized=[
 ['recorded_home_score / recorded_away_score','Marcador final original del registro'],
 ['x12_home_score / x12_away_score','90 minutos reconstruidos cuando hay evidencia; final aproximado si falta'],
 ['x12_target','0: victoria A; 1: empate; 2: victoria B'],
 ['x12_90_reconstructed','Se consiguió reconstruir o verificar el marcador de regulación'],
 ['x12_uncertain_timing','No se pudo verificar la duración; se declara la aproximación'],
 ['x12_source / duration_reason','Fuente de reconstrucción o razón del faltante'],
 ['goal_training_eligible','En history_precut: duración verificada por catálogo independiente, NO admisión principal de goles'],
 ['shootout_record','El partido aparece en el registro de tandas'],
 ['proven_extra_time_goals','Goles descontados por ocurrir en prórroga verificada'],
 ['competition_family','Amistoso, eliminatoria, continental, Mundial, Nations League u otro'],
 ['competitive','Categoría operativa: no amistoso; no certifica oficialidad FIFA'],
 ['elo_home / elo_away','Fuerza de cada selección antes del partido'],
 ['strict_duration_verified','En evaluación: copia de verificación independiente; no se confunde con ventanas de duración supuesta']]
model_fields=[
 ['elo_effective','(Elo A − Elo B + 100 × signo de sede) / 400','Baselines Elo/ordinal y cinco modelos con forma'],
 ['gf_diff','Diferencia de goles a favor en los últimos 5 partidos, con suavizado','Logística con forma, XGBoost y modelos de goles'],
 ['ga_diff','Diferencia de goles recibidos en los últimos 5 partidos, con suavizado','Mismos modelos'],
 ['form_diff','Diferencia de forma en 5 partidos: victoria=1, empate=0, derrota=−1 antes de reflejarse al otro equipo; promedio suavizado','Mismos modelos'],
 ['opponent_diff','Diferencia entre promedios de Elo previo de los últimos 10 rivales / 400','Mismos modelos'],
 ['goal_coverage_sum','Suma de coberturas observadas de ambas ventanas de 5 partidos, entre 0 y 2','Mismos modelos; sin historial previo la cobertura puede ser 0']]
# The frozen EvidenceState maps loss to 0, draw to .5, win to 1 (not -1).
model_fields[3][1]='Diferencia de forma en 5 partidos: victoria=1, empate=0,5, derrota=0; promedio suavizado'
description=f'''# Datos y diccionario de variables

Trabajo con archivos locales suministrados; no hago scraping ni descargas. El estudio es retrospectivo. Distingo datos para actualizar estados, datos para ajustar coeficientes, evidencia de selección y evaluación posterior.

## Cuántos datos utilizo

| Uso | Partidos | Rango |
| --- | --- | --- |
| Estado Elo y forma disponible al corte | {inventory['history_matches']:,} | {inventory['history_first_date']} a {inventory['history_latest_date']} |
| Historial anterior a 2023 | {inventory['pre2023_history_matches']:,} | Desde 1872, sin resultados desde 2023 |
| Ajuste final de los modelos congelados | {inventory['model_training_matches']:,} | {inventory['model_training_first_date']} a {inventory['model_training_latest_date']} |
| Validación temporal para selección | {inventory['pre2023_walk_forward_matches']:,} | Cuatro bloques, 2016–2022 |
| Evaluación semiconfirmatoria | {inventory['semiconfirmatory_matches']:,} | 2023 hasta antes de 2026-06-10 |
| Pronósticos fijos de grupos | 72 | 48 selecciones del Mundial 2026 |

El historial contiene {inventory['historical_team_entities']} entidades de selecciones, incluidas entidades históricas y competiciones no FIFA. Los 6.376 partidos de selección no son una prueba independiente del ajuste final: después de elegir el diseño, el ajuste congelado incorpora todos los partidos desde 2000 hasta 2022. Los 3.624 posteriores no reajustan los modelos; solo actualizan las variables con su pasado y permiten evaluación semiconfirmatoria.

Los resultados del Mundial se cargan únicamente después del commit de predicciones congeladas. Sus 104 registros suministrados no forman parte del entrenamiento o del estado al corte.

## Fuentes y alcance

| Fuente local | Qué contiene | Uso efectivo |
| --- | --- | --- |
| international_results_current.zip | results, goalscorers, shootouts y former_names de martj42 | Historial, objetivos, tandas y normalización, filtrados por fecha |
| fjelstul_worldcup.zip | Catálogo independiente y periodos de Mundiales | Validación de duración histórica; fuente distinta de Openfootball |
| fifa_rank_semesters.zip | Ranking y puntos por año/semestre | Ablación con disponibilidad conservadora y caducidad de 90 días; fuera del modelo final |
| transfermarkt.duckdb | Jugadores, valoraciones, juegos y alineaciones | Mercado fuera del modelo por falta de pertenencia fechada anterior a 2023; juegos de 2026 solo corroboran resultados tras el sellado |
| geonames_cities15000.zip | Ciudad, país y elevación | Altitud estática solo en ablación |
| statsbomb_open_data.zip | Eventos y xG de torneos disponibles | Validación opcional, sin incorporarlos a entrenamiento |
| openfootball_worldcup.zip | Catálogos y marcadores del Mundial, incluidas anotaciones a 90 minutos | Corroboración y duración de 2026, después del congelado |
| resolved_fixtures.csv | Equipos, grupos, sedes y fecha UTC de 72 partidos | Solo metadatos suministrados; ningún modelo o métrica del histórico DataCamp |

El ranking semestral tiene disponibilidad conservadora máxima {inventory['fifa_last_conservative_availability']}; no equivale a ranking vigente de 2026. Excluyo el archivo de fotografía FIFA repetida. No uso valor, club o nacionalidad actuales de players como información histórica ni national_teams como ranking por fecha.

## Columnas originales

{markdown_table(pd.DataFrame(raw_fields,columns=['Campo','Significado','Uso']))}

## Columnas normalizadas y marcas

{markdown_table(pd.DataFrame(normalized,columns=['Campo','Significado']))}

La política principal admite todos los marcadores. El historial al corte contiene {inventory['shootouts']} tandas, {inventory['proven_extra_time_goal_matches']} partidos con goles de prórroga probados y {inventory['goals_duration_assumed_matches']:,} etiquetas con duración no verificada. Estas marcas no certifican que los demás partidos nunca tuvieran prórroga. Una tanda tampoco demuestra un empate a 90 minutos.

## Variables que reciben los modelos

{markdown_table(pd.DataFrame(model_fields,columns=['Variable','Definición','Modelos']))}

Para goles a favor y recibidos uso un prior de tres partidos con promedio 1,3: (suma observada + 3×1,3)/(n+3). Para forma uso (suma de resultados + 1,5)/(n+3), con n≤5. El signo de sede es +1 cuando A es anfitrión, −1 cuando B lo es y 0 en neutral. Calculo todas estas ventanas antes de incorporar cualquier resultado de esa fecha.

## Salidas

Las columnas p_home_win, p_draw y p_away_win significan victoria A, empate y victoria B; suman 1. En los modelos de goles, lambda_home y lambda_away son promedios de goles estimados, no xG medido por eventos. La matriz Poisson contiene home_goals, away_goals y la probabilidad de cada marcador; reporto la masa residual truncada. rho solo corresponde a la corrección Dixon-Coles.

Logística y Poisson tienen probabilidades 1X2 distintas. Muestro cada producto con su nombre, sin fingir que las probabilidades de la logística salen de la matriz Poisson.

Los conteos, rangos y faltantes por variable se ejecutan en data_inventory.json. La cobertura por competición y año se guarda en data_competition_coverage.csv y data_year_coverage.csv. Los hashes identifican exactamente los archivos locales usados; los datos grandes no se redistribuyen automáticamente en Git.
'''
(ROOT/'docs/DATOS_Y_DICCIONARIO.md').write_text(description,encoding='utf-8')
print(json.dumps(inventory,indent=2,ensure_ascii=False))
