"""Synchronize executed feature artifacts and the retrospective audit."""
import json
from pathlib import Path
import sys
import subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
import pandas as pd
from football_forecast.ingestion import digest_file
from football_forecast.preparation import markdown_table,SCENARIO_LABELS
from football_forecast.source_audit import friendly_catalogue_evidence

if __name__=='__main__':
    preparation=ROOT/'reports/data_preparation'
    features=ROOT/'reports/feature_design'
    selection=json.loads((features/'selected_elo.json').read_text(encoding='utf-8'))
    feature_report=(features/'RESULTADOS.md').read_text(encoding='utf-8')
    feature_report=feature_report.replace('| True |','| Sí |').replace('| False |','| No |')
    feature_report=feature_report.replace('La adopción de descanso, forma y altitud depende de ablaciones temporales en Fase 3.',
                                        'Contrasto estos grupos con una logística mediante ablaciones temporales. Su evaluación con XGBoost y modelos de goles corresponde a la Fase 3.')
    calibration=pd.read_csv(features/'elo_calibration.csv')[['candidate','log_loss','brier','matches']]
    calibration.columns=['Configuración','Log loss','Brier','Partidos']
    start=feature_report.index('| Configuración |')
    end=feature_report.index('\n\nLa configuración seleccionada',start)
    feature_report=feature_report[:start]+markdown_table(calibration,precision=6)+feature_report[end:]
    folds=pd.read_csv(features/'elo_walk_forward_blocks.csv')
    folds.columns=['Inicio del bloque','Partidos','Log loss','Brier']
    start=feature_report.index('| block_start |') if '| block_start |' in feature_report else feature_report.index('| Inicio del bloque |')
    end=feature_report.index('\n\n## Inicialización',start)
    feature_report=feature_report[:start]+markdown_table(folds,precision=6)+feature_report[end:]
    parameters=selection['parameters']
    if '\n## Parámetros seleccionados' not in feature_report:
        settings=pd.DataFrame([['Amistosos',parameters['friendly_k']],['Nations League',parameters['nations_k']],
                               ['Continentales y eliminatorias',parameters['continental_k']],['Mundial',parameters['worldcup_k']],
                               ['Otras competiciones',parameters['other_k']]],columns=['Competición','Peso K'])
        info='\n## Parámetros seleccionados\n\n'+markdown_table(settings)+f"\n\nUso una ventaja de sede de {parameters['home_advantage']} puntos Elo y un multiplicador de goles de 1 + {parameters['margin_strength']} × log(1 + diferencia absoluta de goles). La puntuación inicial común es {parameters['initial']}. La tasa de regresión por inactividad seleccionada es {parameters['inactivity_rate']}: no aplico esa regresión. La diferencia de log loss entre configuraciones es pequeña; la elección no demuestra una mejora robusta.\n"
        feature_report=feature_report.replace('\n## Ranking secundario',info+'\n## Ranking secundario')
    (features/'RESULTADOS.md').write_text(feature_report,encoding='utf-8')
    context=json.loads((features/'context_audit.json').read_text(encoding='utf-8'))
    audit=json.loads((preparation/'data_audit.json').read_text(encoding='utf-8'))
    audit['friendly_duration_catalogues']=friendly_catalogue_evidence(ROOT/'data/raw')
    audit['feature_design']={'selected_elo':selection,'context':context,
                            'artifact_hashes':[{'file':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest_file(p)}
                                             for p in sorted(features.iterdir()) if p.is_file()]}
    audit['feature_design']['fifa_rank_and_points']=json.loads((features/'fifa_rank_points_ablation.json').read_text(encoding='utf-8'))
    audit['feature_design']['feature_selection']=json.loads((features/'feature_selection.json').read_text(encoding='utf-8'))
    audit['market_value']=context['market_decision']
    audit['transfermarkt']['dated_membership_context']=context
    verified=json.loads((features/'verification.json').read_text(encoding='utf-8'))
    if not verified['successful'] or verified['skipped']:
        raise RuntimeError('Successful local verification without skipped tests is required')
    audit['checks']['verification']=verified
    audit['feature_design_audited_at_utc']=datetime.now(timezone.utc).isoformat()
    roles={'international_results_current.zip':'Historical results/events filtered before target interpretation.',
           'international_results_baseline.zip':'Preserved baseline source.',
           'fjelstul_worldcup.zip':'Historical regulation period verification.',
           'openfootball_worldcup.zip':'Official 2026 results reserved until model freeze; hash only.',
           'statsbomb_open_data.zip':'Optional historical validation only; no predictive input.',
           'transfermarkt.duckdb':'Dated valuations, dated lineup coverage and undated metadata audit; current snapshot features prohibited.',
           'geonames_cities15000.zip':'Static venue altitude; exact country/city matching and explicit missingness.',
           'fifa_rank_semesters.zip':'Conservative dated secondary ablation.',
           'fifa_rank_repeated_snapshot_excluded.csv':'Excluded repeated ranking snapshot; hash only.',
           'worldcup_fixtures.zip':'Fixture and venue metadata only.'}
    for source in audit['sources']:
        source['role']=roles.get(Path(source['file']).name,source['role'])
    git=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
    command=str(git) if git.exists() else 'git'
    audit['git_preparation']={'tag':'data-prepared',
                             'commit':subprocess.check_output([command,'rev-parse','data-prepared^{commit}'],cwd=ROOT,text=True).strip()}
    (preparation/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    sensitivity=pd.read_csv(preparation/'sensitivity_summary.csv')
    detailed=pd.read_csv(preparation/'elo_policy_sensitivity.csv')
    detailed['elo_centered_48']=detailed.elo-detailed.groupby('scenario').elo.transform('mean')
    detailed['rank_in_worldcup_cohort_48']=detailed.groupby('scenario').elo.rank(ascending=False,method='min').astype(int)
    centered=detailed[detailed.scenario=='historial_completo_90_verificado_o_final_registrado'].set_index('team').elo_centered_48
    detailed['centered_difference_from_reference']=detailed.elo_centered_48-detailed.team.map(centered)
    detailed.to_csv(preparation/'elo_policy_sensitivity.csv',index=False)
    view=sensitivity[['scenario','spearman_rank_correlation_48','reference_top20_teams_changing_rank',
                      'top20_membership_changes','mean_absolute_centered_difference']].copy()
    view.scenario=view.scenario.map(SCENARIO_LABELS)
    view.columns=['Política','Spearman en 48 selecciones','Cambios de puesto del top 20 de referencia',
                  'Entradas más salidas del top 20','Cambio medio de Elo centrado']
    view['Spearman en 48 selecciones']=view['Spearman en 48 selecciones'].map(lambda x:f'{x:.4f}')
    report=(preparation/'RESULTADOS.md').read_text(encoding='utf-8')
    report=report.split('\n## Sensibilidad del orden')[0]
    report=report.replace('Para incorporar valor de una plantilla necesito una relación fechada entre jugador y selección.',
                          'Las alineaciones fechadas disponibles comienzan en 2024: permiten un diagnóstico anterior al corte, pero no validar mercado en los bloques anteriores a 2023. El conjunto de jugadores observados no equivale a una convocatoria oficial.')
    report+='\n## Sensibilidad del orden\n\nCentro cada escenario en la media de las mismas 48 selecciones. Cuento los cambios de puesto del top 20 de referencia dentro de esas 48, y las entradas más salidas por separado.\n\n'+markdown_table(view)+'\n'
    unknown=audit['coverage_bias']
    share=next(x['historical_share'] for x in unknown if x['stratum']=='Unmapped historical entity')
    report+=f'\nLa tabla administrativa local no cruza el {100*share:.2f} % de las participaciones históricas; el análisis por confederación es parcial. Las 48 selecciones del fixture sí están cruzadas. No interpreto diferencias entre confederaciones como una estimación completa del sesgo sin atender esta cobertura.\n'
    friendly= pd.read_csv(preparation/'historical_results.csv',usecols=['competition_family','goal_training_eligible','shootout_record','recorded_home_score','recorded_away_score'])
    friendlies=friendly[friendly.competition_family=='friendly']
    verified_friendlies=friendlies[friendlies.goal_training_eligible]
    audit['friendly_duration_evidence']['verified_friendlies_from_zero_score_invariant']=len(verified_friendlies)
    report+=f'\nNo hay amistosos con eventos completos en martj42, ni competiciones de amistosos en el catálogo local de StatsBomb. Los {len(verified_friendlies)} amistosos admisibles corresponden a marcadores finales 0–0 invariantes, no a una muestra representativa de goles de amistosos. En el historial, {int(friendlies.shootout_record.sum())} amistosos aparecen en tandas; esto no equivale a disponer de sus eventos completos. No interpreto la proporción no estimable de prórrogas como cero. La evaluación de amistosos con esta cobertura requiere informar ese sesgo explícitamente.\n'
    (preparation/'RESULTADOS.md').write_text(report,encoding='utf-8')
    audit['outputs']=[{'file':p.name,'sha256':digest_file(p)} for p in sorted(preparation.glob('*.csv'))]
    (preparation/'data_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    combined='# Resultados del estudio\n'+(features/'RESULTADOS.md').read_text(encoding='utf-8').split('\n',1)[1]
    combined+='\n## Auditoría y límites del historial\n'+report.split('\n',1)[1]
    (ROOT/'RESULTADOS.md').write_text(combined,encoding='utf-8')
