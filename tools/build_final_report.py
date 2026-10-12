"""Publish executed evidence as a short README, figures and standalone report."""
from pathlib import Path
import sys
import os
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/matplotlib'))
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps'),str(ROOT/'tools'),str(ROOT)]
from verify_final_evaluation import frozen_checks,protocol_checks,digest,utc_now
from run_final_evaluation import check_prediction_commit
from football_forecast.final_evaluation import MODEL_NAMES,PROBABILITY_COLUMNS,event
from football_forecast.preparation import markdown_table
frozen_checks();protocol_checks(True);check_prediction_commit()
folder=ROOT/'reports/final_evaluation'
semi=pd.read_csv(folder/'semiconfirmatory_metrics.csv')
monthly=pd.read_csv(folder/'semiconfirmatory_monthly_sensitivity.csv')
world=pd.read_csv(folder/'worldcup_group_metrics.csv')
conclusion=json.loads((folder/'semiconfirmatory_conclusion.json').read_text(encoding='utf-8'))
wc=json.loads((folder/'worldcup_conclusion.json').read_text(encoding='utf-8'))
data=json.loads((folder/'data_inventory.json').read_text(encoding='utf-8'))
active=json.loads((folder/'active_protocol.json').read_text(encoding='utf-8'))
seal=json.loads((folder/'predictions_seal.json').read_text(encoding='utf-8'))
load=json.loads((folder/'official_results_load_record.json').read_text(encoding='utf-8'))
overlap=max(0,(pd.Timestamp(conclusion['evaluation_completed_at_utc'])-pd.Timestamp(load['first_official_results_load_started_at_utc'])).total_seconds())
nf=semi[semi.stratum.eq('non_friendlies')].copy()
selected=nf[nf.model.eq('logistic')].iloc[0]
reference=nf[nf.model.eq('elo')].iloc[0]
wm=world[world.model.eq('logistic')].iloc[0]
we=world[world.model.eq('elo')].iloc[0]

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
assets=ROOT/'assets';assets.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
names=['logistic','ordinal','xgboost','poisson','dixon_coles','xgboost_poisson']
plot=nf.set_index('model').loc[names]
fig,ax=plt.subplots(figsize=(11.5,5.6))
fig.patch.set_facecolor('#f7f9fc');ax.set_facecolor('#f7f9fc')
for i,(name,row) in enumerate(plot.iterrows()):
    color='#087f6c' if name=='logistic' else '#46617d'
    ax.errorbar(row.difference_log_loss,i,xerr=[[row.difference_log_loss-row.difference_log_loss_ci_low],
                  [row.difference_log_loss_ci_high-row.difference_log_loss]],fmt='o',color=color,
                  elinewidth=2,capsize=4,markersize=8 if name=='logistic' else 6)
ax.axvline(0,color='#a3afbe',ls='--',lw=1)
ax.set_yticks(range(len(names)),[MODEL_NAMES[n] for n in names]);ax.invert_yaxis()
ax.set_xlabel('Diferencia de log loss frente a Solo Elo · menor es mejor')
ax.grid(axis='x',alpha=.18)
fig.suptitle('¿Aporta algo más que Elo?',x=.03,y=.99,ha='left',fontsize=21,fontweight='bold',color='#132c43')
fig.text(.03,.88,f"{int(selected.matches):,} no amistosos · 2023–corte · IC 95% por {int(selected.quarter_clusters)} trimestres · evidencia semiconfirmatoria",fontsize=11,color='#4c6174')
fig.tight_layout(rect=[0,0,1,.86])
fig.savefig(assets/'model_comparison.png',dpi=180,bbox_inches='tight')
fig.savefig(assets/'model_comparison.svg',bbox_inches='tight')
plt.close(fig)

reliability=pd.read_csv(folder/'semiconfirmatory_reliability.csv')
fig,axes=plt.subplots(1,3,figsize=(12,3.7),sharex=True,sharey=True)
for k,ax in enumerate(axes):
    ax.plot([0,1],[0,1],'--',color='#a3afbe')
    for model,color in [('logistic','#087f6c'),('poisson','#547a9b')]:
        points=reliability[reliability.model.eq(model)&reliability.stratum.eq('non_friendlies')&reliability['class'].eq(k)&reliability.matches.gt(0)]
        ax.plot(points.mean_probability,points.actual_rate,'o-',label=MODEL_NAMES[model],color=color)
    ax.set_title(['Victoria A','Empate','Victoria B'][k]);ax.set_xlabel('Probabilidad estimada');ax.grid(alpha=.15)
axes[0].set_ylabel('Frecuencia observada');axes[1].legend(fontsize=8,loc='upper left')
fig.suptitle('Fiabilidad por clase · no amistosos · los recuentos por intervalo están en el CSV',fontsize=12)
fig.tight_layout();fig.savefig(assets/'calibration.png',dpi=180,bbox_inches='tight');plt.close(fig)

def human_metrics(frame,descriptive=False):
    out=frame[['model','matches','log_loss','brier','rps','accuracy','actual_draw','p_draw','difference_log_loss',
               'difference_log_loss_ci_low','difference_log_loss_ci_high']].copy()
    out['model']=out.model.map(MODEL_NAMES)
    out['IC diferencia']=out.apply(lambda r:f'[{r.difference_log_loss_ci_low:.5f}; {r.difference_log_loss_ci_high:.5f}]',axis=1)
    out=out.drop(columns=['difference_log_loss_ci_low','difference_log_loss_ci_high'])
    out=out.rename(columns={'model':'Modelo','matches':'N','log_loss':'Log loss','brier':'Brier','rps':'RPS',
        'accuracy':'Acierto','actual_draw':'Empates reales','p_draw':'Empates previstos','difference_log_loss':'Diferencia vs Elo'})
    if 'score_nll' in frame:
        out['NLL marcador']=frame.score_nll.fillna('No aplica')
    return markdown_table(out,precision=5)

strata=semi[semi.model.eq('logistic')][['stratum','matches','home_wins','draws','away_wins','estimable','quarter_clusters','month_clusters',
       'log_loss','difference_log_loss','difference_log_loss_ci_low','difference_log_loss_ci_high']].copy()
stratum_labels={'total':'Total','non_friendlies':'No amistosos','friendlies':'Amistosos','worldcup':'Mundiales',
 'strong_teams':'Ambos Elo >1700','strong_non_friendlies':'Ambos Elo >1700: no amistosos','worldcup_48_mutual':'48 selecciones entre sí',
 'worldcup_48_any_opponent':'Al menos una de las 48 selecciones','exclude_marked':'Sin tandas/prórroga marcada','strict_duration':'Duración independiente verificada'}
strata['stratum']=strata.stratum.map(stratum_labels)
strata['IC diferencia']=strata.apply(lambda r:f'[{r.difference_log_loss_ci_low:.5f}; {r.difference_log_loss_ci_high:.5f}]' if r.matches else 'No disponible',axis=1)
strata=strata.drop(columns=['difference_log_loss_ci_low','difference_log_loss_ci_high'])
strata.columns=['Estrato','N','Victorias A','Empates','Victorias B','Estimable','Trimestres','Meses','Log loss','Diferencia vs Elo','IC diferencia']
subperiod=pd.read_csv(folder/'semiconfirmatory_subperiods.csv')
subperiod=subperiod[subperiod.model.eq('logistic')&subperiod.stratum.eq('non_friendlies')]
subperiod=subperiod[['start','end_exclusive','matches','estimable','quarter_clusters','month_clusters','log_loss','difference_log_loss']]
subperiod.columns=['Inicio','Fin exclusivo','N','Estimable','Trimestres','Meses','Log loss','Diferencia vs Elo']
qm=nf[nf.model.eq('logistic')].iloc[0]
mm=monthly[monthly.model.eq('logistic')&monthly.stratum.eq('non_friendlies')].iloc[0]
errors=pd.read_csv(folder/'worldcup_largest_errors.csv').head(10)
errors=errors[['home_team','away_team','actual_score','p_home_win','p_draw','p_away_win','log_loss']]
errors.columns=['Equipo A','Equipo B','Resultado 90 minutos','P victoria A','P empate','P victoria B','Log loss']
counts=pd.read_csv(folder/'threshold_pre2023_counts.csv')
elo48=pd.read_csv(folder/'worldcup_48_elo_2022_12_31.csv')
cal=pd.read_csv(folder/'semiconfirmatory_calibration.csv')
cal=cal[cal.model.isin(['logistic','poisson'])&cal.stratum.eq('non_friendlies')].copy()
cal['model']=cal.model.map(MODEL_NAMES);cal['class']=cal['class'].map({0:'Victoria A',1:'Empate',2:'Victoria B'})
cal=cal[['model','class','ece_10_bins','intercept','slope','fit_status']]
cal.columns=['Modelo','Clase','ECE complemento','Intercepto','Pendiente','Estado del ajuste']
cal['Estado del ajuste']=cal['Estado del ajuste'].replace({'diagnostic_only':'Solo diagnóstico','optimization_not_verified':'Ajuste no verificado'})

report=f'''# Evaluación final del estudio retrospectivo

Mi pregunta es si aprendizaje automático y modelos de goles mejoran a Solo Elo al pronosticar partidos de selecciones. La logística con Elo y forma confirma su aporte en la evaluación semiconfirmatoria; XGBoost no demuestra una mejora robusta. En los 72 partidos de grupos no puedo declarar superioridad de la logística frente a Elo.

El Mundial ya estaba jugado al construir el estudio. El corte deportivo exclusivo es 2026-06-10. 2023–corte es **semiconfirmatorio**, porque la entrega histórica DataCamp ya puntuó 846 partidos de ese periodo; sus modelos y métricas no son comparadores.

## Resultado principal: 2023–corte

Evalué {conclusion['matches']:,} partidos, incluidos {int(selected.matches):,} no amistosos. Frente a Elo, la logística reduce log loss en {selected.difference_log_loss:.6f}, con IC trimestral [{selected.difference_log_loss_ci_low:.6f}; {selected.difference_log_loss_ci_high:.6f}], reduce Brier en {conclusion['primary_brier_difference']:.6f} y mejora en {conclusion['blocks_improving']} de cuatro subperiodos. Cumple el criterio registrado antes de ejecutar. Esto confirma la selección dentro de evidencia con exposición previa; no la convierte en una prueba virgen.

![Aporte frente a Elo](../../assets/model_comparison.png)

{human_metrics(nf)}

Acierto y tasas de empate están expresados como proporciones. Brier suma las tres clases, sin dividir. RPS usa derrota/empate/victoria y divide la suma acumulada por dos. Las NLL de marcador están en semiconfirmatory_metrics.csv solo para modelos de goles.

## Representatividad, mínimos y sensibilidades

Fijé ambos Elo previos >1700 usando solo datos anteriores a 2023. Los cuatro bloques completos contienen {', '.join(str(x) for x in counts[counts.scope.eq('total')].both_elo_above_1700)} partidos y todos cumplen los mínimos. {int(elo48.above_1700.sum())} de las 48 selecciones superan 1700 al 2022-12-31; los 48 valores están en worldcup_48_elo_2022_12_31.csv. El cruce no amistoso de 2022 tiene N=184 y es descriptivo.

Declaro un estrato estimable solo con ≥200 partidos y ≥30 eventos de cada clase; cada subperiodo se evalúa por separado. Un grupo pequeño conserva sus puntos descriptivos y recuentos, pero no recibe una conclusión inferencial ni una regresión de calibración.

{markdown_table(strata.fillna('No disponible'),precision=6)}

La mejora global no equivale a superioridad demostrada en encuentros de mayor nivel: ambos Elo >1700 tiene N=674 y los partidos entre las 48 selecciones tienen N=406; sus intervalos de diferencia incluyen cero. El estrato de al menos una de las 48 frente a cualquier rival tiene N=1.602 e intervalo favorable, pero incluye rivales de distinta fuerza. No traslado ese resultado automáticamente a partidos entre selecciones fuertes.

El total tiene {conclusion['actual_quarter_clusters']} trimestres observados y {conclusion['actual_month_clusters']} meses; no amistosos tiene {int(selected.quarter_clusters)} trimestres y {int(selected.month_clusters)} meses. No sustituyo meses vacíos por clústeres artificiales. El protocolo preveía 14 trimestres y 42 meses posibles, incluido el último parcial.

Con 2.000 réplicas pareadas, el IC trimestral de la diferencia principal es [{qm.difference_log_loss_ci_low:.6f}; {qm.difference_log_loss_ci_high:.6f}], y el mensual es [{mm.difference_log_loss_ci_low:.6f}; {mm.difference_log_loss_ci_high:.6f}]. El criterio primario sigue siendo trimestral. Las sensibilidades no reentrenan ni cambian la política de forma del modelo congelado.

## Deriva sin reajuste

{markdown_table(subperiod,precision=6)}

Los coeficientes siguen ajustados únicamente hasta 2022. Actualizo Elo y forma con el pasado antes de cada partido, sin contaminación entre resultados del mismo día. Una mejora promedio no elimina la posibilidad de deriva o de que una población particular se comporte distinto.

## Calibración por clase

![Fiabilidad](../../assets/calibration.png)

{markdown_table(cal.fillna('No estimable'),precision=6)}

La recta de calibración es diagnóstica: idealmente intercepto 0 y pendiente 1. No la aplico a las predicciones. El ECE de diez intervalos fijos es complementario; las tablas de fiabilidad conservan el recuento de cada intervalo, incluidos los vacíos. Los estratos insuficientes quedan marcados, no reciben parámetros inventados.

## Dos productos y marcadores

Logística estima 1X2 directamente. Poisson estima tasas de goles y una matriz, de la cual sale su propio 1X2. Sus probabilidades difieren en promedio {conclusion['product_discrepancy_mean_percentage_points']:.4f} puntos porcentuales en 2023–corte y {wc['product_discrepancy_mean_percentage_points']:.4f} en los 72 pronósticos de grupos. No las reconcilio ni doy a entender que el 1X2 de la logística procede de la matriz Poisson.

Poisson es el producto descriptivo de marcadores elegido antes de 2023. Los modelos de goles no demostraron todo el criterio frente a Elo en selección; sus marcadores siguen disponibles sin afirmar que ese producto mejora el 1X2 principal. Las matrices y masas residuales se guardan con los pronósticos sellados.

## Mundial 2026: descripción de 72 partidos

{human_metrics(world,True)}

La logística obtiene {wm.log_loss:.6f} frente a {we.log_loss:.6f} de Elo. La diferencia {wm.difference_log_loss:.6f} tiene IC por fechas [{wm.difference_log_loss_ci_low:.6f}; {wm.difference_log_loss_ci_high:.6f}], que incluye cero. Los 72 partidos no cumplen el mínimo inferencial; no declaro un ganador. Reporto IC descriptivos por fecha UTC y sensibilidad por partido, con recuentos de clústeres. No supongo un error estándar fijo.

Los {wc['groups_evaluated']} marcadores de grupos coinciden con Openfootball; Transfermarkt corrobora {wc['group_transfermarkt_matches']}, con {wc['group_transfermarkt_discrepancies']} discrepancias de marcador. Hay {wc['utc_local_date_differences']} diferencias de día entre el registro local y el fixture UTC. Cruzar por pareja y fecha ±1 día resuelve la convención sin alterar pronósticos. Normalizo Turkiye y Democratic Republic of the Congo únicamente para corroborar esos registros actuales; no fusiono entidades históricas.

### Mayores errores de la logística

{markdown_table(errors,precision=5)}

Cada fila conserva la probabilidad asignada antes de ver el resultado y su pérdida. Un partido aislado no explica una mejora global; el listado completo está en worldcup_largest_errors.csv.

## Eliminatorias

Evalúo aparte {wc['knockouts_evaluated']} encuentros a 90 minutos, con catálogo independiente y pares explícitos de regulación en Openfootball para prórrogas. Se excluyen {wc['knockouts_excluded_source_disagreement']} por desacuerdo o falta de verificación. Los resultados están en worldcup_knockout_metrics.csv.

Esta evaluación es **condicional a participantes conocidos retrospectivamente**: uso los mismos coeficientes y el estado anterior al corte, sin actualizar con grupos del Mundial. Los emparejamientos se conocieron después de cargar resultados, por lo que no presento este bloque como predicciones de eliminatorias selladas previamente ni como simulación del cuadro.

## Trazabilidad y límites

El protocolo autoritativo es reports/final_evaluation/protocol_approved.json, con SHA256 `{active['protocol_sha256']}`. Ese hash cubre los bytes de ese JSON; el sello y el documento humano tienen hashes propios. La etiqueta phase4-protocol anterior se conserva; phase4-protocol-approved registra las condiciones adicionales.

Las 72 predicciones se sellaron en {seal['sealed_at_utc']} y el commit phase4-predictions-frozen precede a la carga oficial iniciada en {load['first_official_results_load_started_at_utc']}. Los 43 artefactos congelados y cinco archivos protegidos de código permanecen intactos. No reajusto modelos ni comparo el pipeline DataCamp.

Registro una incidencia de secuencia: inicié la carga de resultados oficiales {overlap:.3f} segundos antes de terminar el remuestreo semiconfirmatorio. Los pronósticos ya estaban sellados y ambos procesos usaban entradas separadas; no hubo reajuste ni cambio de criterio. Conservo las fechas reales y no afirmo cumplimiento literal de ese orden de terminación.

Otros límites: duración supuesta en parte del historial, exposición previa al periodo semiconfirmatorio, selección de parámetros y variables en los mismos bloques anteriores a 2023, dependencia entre partidos que puede superar los bloques de remuestreo, comparaciones secundarias sin corrección múltiple, ausencia de pertenencia histórica suficiente para valor de mercado y ausencia de ranking FIFA vigente de 2026. La coincidencia entre archivos suministrados no sustituye una verificación externa de publicación oficial.

## Datos y reproducción

El estado al corte usa {data['history_matches']:,} partidos desde {data['history_first_date']} hasta {data['history_latest_date']}; los coeficientes congelados usan {data['model_training_matches']:,} partidos desde 2000 hasta 2022. El diccionario explica columnas originales, etiquetas y seis variables en [DATOS_Y_DICCIONARIO.md](../../docs/DATOS_Y_DICCIONARIO.md). Las tablas, intervalos, fiabilidad y sensibilidades se generan por código, sin descargas.
'''
(folder/'RESULTADOS.md').write_text(report,encoding='utf-8')
root_report=f'''# Resultados del estudio

La logística con Elo y forma confirma su aporte frente a Solo Elo en la evaluación semiconfirmatoria 2023–corte: log loss {selected.log_loss:.6f} frente a {reference.log_loss:.6f}, diferencia {selected.difference_log_loss:.6f}, IC trimestral [{selected.difference_log_loss_ci_low:.6f}; {selected.difference_log_loss_ci_high:.6f}], Brier mejora y cuatro subperiodos favorables. XGBoost no demuestra una mejora robusta.

En los 72 partidos de grupos, logística obtiene {wm.log_loss:.6f} frente a {we.log_loss:.6f} de Elo; el intervalo de la diferencia incluye cero. Es una descripción de muestra pequeña, no una prueba de superioridad.

Logística y Poisson son productos distintos, sin reconciliación. La discrepancia media es {conclusion['product_discrepancy_mean_percentage_points']:.4f} puntos porcentuales en 2023–corte y {wc['product_discrepancy_mean_percentage_points']:.4f} en los grupos.

[Informe completo](reports/final_evaluation/RESULTADOS.md) · [Herramienta interactiva](reports/final_evaluation/football_report.html) · [Datos y diccionario](docs/DATOS_Y_DICCIONARIO.md) · [Protocolo aprobado](reports/final_evaluation/PROTOCOLO_APROBADO.md).

El estudio es retrospectivo y el periodo posterior a 2022 es semiconfirmatorio por exposición previa a DataCamp, excluido de comparaciones. Mantengo intacta la evidencia de selección en reports/models_selected/. La cronología también documenta el solapamiento operativo de {overlap:.3f} segundos entre carga oficial y cierre del remuestreo semiconfirmatorio; no modifica pronósticos, modelos o criterios.
'''
(ROOT/'RESULTADOS.md').write_text(root_report,encoding='utf-8')
readme=f'''# Probabilidades de fútbol internacional

**Pregunta:** ¿mejoran el aprendizaje automático y los modelos de goles a un Elo simple al predecir partidos de selecciones?

**Resultado:** la logística con Elo y forma mejora frente a Solo Elo en la muestra amplia y los cuatro subperiodos; XGBoost no demuestra una mejora robusta. La ventaja no queda demostrada entre selecciones fuertes ni en los 72 partidos del Mundial.

![Comparación probabilística](assets/model_comparison.png)

Estudio retrospectivo. La evidencia 2023–corte es semiconfirmatoria por exposición previa al periodo. [Explorar los 72 partidos](reports/final_evaluation/football_report.html) · [Resultados](reports/final_evaluation/RESULTADOS.md) · [Explicación sencilla](docs/COMO_ENTENDER_EL_MODELO.md).

## Datos en una mirada

- **{data['history_matches']:,} partidos** de {data['history_first_date']} a {data['history_latest_date']} para actualizar Elo y forma; {data['historical_team_entities']} entidades de selecciones, incluidas históricas.
- **{data['model_training_matches']:,} partidos de 2000–2022** para ajustar los coeficientes congelados; **6.376** para selección con validación temporal.
- **3.624 partidos de 2023–corte** para evaluación, con **2.711 no amistosos** en la comparación principal.
- **72 pronósticos de grupos**, con probabilidades y resultados registrados al lado; **48 selecciones**.

Uso results, goalscorers, shootouts y former_names de martj42; Fjelstul para duración histórica; Openfootball y juegos de Transfermarkt para corroborar 2026 después del sellado. Ranking semestral y GeoNames quedan en ablaciones. No uso mercado actual ni extrapolo ranking FIFA a 2026. StatsBomb queda como validación opcional. Todas las fuentes son archivos locales suministrados, sin scraping.

El [diccionario de datos](docs/DATOS_Y_DICCIONARIO.md) explica el contenido, las cantidades, los marcadores a 90 minutos y cada variable. La logística recibe seis variables: diferencia efectiva de Elo, diferencias de goles a favor y recibidos, forma reciente, fuerza de rivales recientes y cobertura de las ventanas. Las variables se calculan únicamente con el pasado.

## Método y lectura de resultados

La referencia Solo Elo incluye sede fija. Comparo frecuencias, logística con forma, ordinal, XGBoost 1X2, Poisson, Dixon-Coles y XGBoost Poisson. No reajusto modelos desde 2022: actualizo solo el estado Elo y forma. **Logística estima 1X2; Poisson estima marcadores y su propio 1X2. No son el mismo producto.**

En no amistosos, log loss es **{selected.log_loss:.4f}** para logística y **{reference.log_loss:.4f}** para Elo. La diferencia tiene IC trimestral **[{selected.difference_log_loss_ci_low:.4f}; {selected.difference_log_loss_ci_high:.4f}]**. Remuestreo 2.000 veces bloques trimestrales completos; el bootstrap mensual es sensibilidad. Reporto Brier, RPS, acierto, fiabilidad por clase, NLL de marcador y resultados por población.

Entre equipos con ambos Elo >1700 (674 partidos) y entre las 48 selecciones del Mundial (406), los intervalos incluyen cero. La mejora de la muestra amplia no garantiza una ventaja en el tipo de encuentro más exigente.

Para inferencia exijo ≥200 partidos y ≥30 eventos por clase. Los 72 grupos y las eliminatorias son descriptivos. Las eliminatorias usan participantes conocidos retrospectivamente y no representan simulación ni pronósticos sellados antes del torneo.

## Reproducibilidad y documentación técnica

```powershell
python tools/verify_final_evaluation.py
```

La verificación comprueba modelos, protocolo y predicciones frente a sus hashes y commits; el CI informa pruebas y omisiones por datos locales. Los archivos grandes están fuera de Git y necesito las mismas fuentes para repetir el procesamiento. Uso dos hilos por defecto y no simulo cuadros de torneo.

- [Protocolo aprobado y umbral](reports/final_evaluation/PROTOCOLO_APROBADO.md).
- [Decisiones y límites](docs/DECISIONES_DE_DISEÑO.md), incluido el periodo semiconfirmatorio y la incidencia de secuencia registrada.
- [Datos, diccionario y cobertura](docs/DATOS_Y_DICCIONARIO.md).
- [Índice de auditorías](data_audit.json); cada protocolo y sello identifica el archivo exacto cubierto por SHA256.

models-selected conserva la selección anterior a 2023; phase4-protocol y phase4-protocol-approved son protocolos distintos; phase4-predictions-frozen identifica las predicciones anteriores a cargar resultados oficiales. Los modelos y métricas históricos de DataCamp están excluidos de comparaciones. El trabajo se construyó con el Mundial ya jugado y no se presenta como pronóstico publicado antes del torneo.

Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.
'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
decision=(ROOT/'docs/DECISIONES_DE_DISEÑO.md').read_text(encoding='utf-8')
marker='\n\n## Resultado de evaluación semiconfirmatoria'
decision=decision.split(marker)[0]
decision+=f'''{marker}

La selección se confirma bajo el protocolo aprobado: logística mejora log loss y Brier frente a Solo Elo en no amistosos, con cuatro subperiodos favorables. No cambio modelos ni criterios. XGBoost sigue siendo comparador porque su intervalo incluye cero. El estrato de equipos fuertes mantiene >1700 y el mínimo inferencial es 200 partidos/30 eventos por clase. Reporto clústeres reales, remuestreo mensual como sensibilidad y exposición previa de DataCamp.

Las 72 predicciones se sellaron y se comprometieron antes de la carga oficial. En grupos, el intervalo frente a Elo incluye cero; no declaro superioridad. Las eliminatorias se condicionan a participantes conocidos retrospectivamente y al estado anterior al corte. La logística y Poisson mantienen productos separados.

Registro el solapamiento de {overlap:.3f} segundos entre inicio de carga oficial y cierre del bootstrap semiconfirmatorio, sin cambios de modelos o entradas del cálculo. Conservo los tiempos reales y no afirmo una ejecución estrictamente secuencial de ese cierre. Los resultados y la incidencia están en reports/final_evaluation/RESULTADOS.md.
'''
(ROOT/'docs/DECISIONES_DE_DISEÑO.md').write_text(decision,encoding='utf-8')
write={'generated_at_utc':utc_now(),'chronology_deviation':{'worldcup_load_overlapped_semiconfirmatory_completion_seconds':overlap,
 'forecast_commit_preceded_load':True,'models_changed':False,'semiconfirmatory_inputs_changed':False},
 'primary_result':conclusion,'worldcup_result':wc,'input_inventory':data,'protocol':active,
 'figure_sources':['semiconfirmatory_metrics.csv','semiconfirmatory_reliability.csv']}
(folder/'report_manifest.json').write_text(json.dumps(write,indent=2,ensure_ascii=False),encoding='utf-8')
event(folder,'reports_and_figures_generated',chronology_overlap_seconds=overlap)
print('README breve, informe técnico y figuras generados desde tablas ejecutadas.')
