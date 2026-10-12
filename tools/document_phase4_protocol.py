"""Refresh non-frozen entry points without copying the frozen reports."""
from pathlib import Path
import json
import sys
import pandas as pd
from verify_final_evaluation import ROOT,OUTPUT,frozen_checks,digest,utc_now
sys.path.insert(0,str(ROOT/'src'))
from football_forecast.preparation import markdown_table

frozen_checks()
protocol=json.loads((OUTPUT/'protocol.json').read_text(encoding='utf-8'))
seal=json.loads((OUTPUT/'protocol_seal.json').read_text(encoding='utf-8'))
discrepancy=json.loads((OUTPUT/'pre2023_product_discrepancy.json').read_text(encoding='utf-8'))
selection=pd.read_csv(ROOT/'reports/models_selected/model_comparison.csv')
selection=selection[selection.scope.eq('non_friendlies')][['model','log_loss','brier']]
selection['model']=selection.model.map({'frequency':'Frecuencias','elo':'Solo Elo con sede fija','logistic':'Logística con Elo y forma',
 'ordinal':'Regresión ordinal','xgboost':'XGBoost 1X2','poisson':'Poisson independiente','dixon_coles':'Dixon-Coles','xgboost_poisson':'XGBoost Poisson'})
selection.columns=['Modelo','Log loss','Brier']
bias=pd.read_csv(ROOT/'reports/selection_review/archived_bias_decomposition.csv')
bias=bias.rename(columns={'scope':'Estrato','matches':'Partidos','fraction':'Participación','elo_log_loss':'Log loss Elo',
 'candidate_log_loss':'Log loss combinación sesgada','mean_improvement':'Mejora media','contribution_to_pooled_improvement':'Contribución agregada'})

readme='''# Probabilidades de fútbol internacional

Evaluación retrospectiva de Elo, aprendizaje automático y modelos de goles.

Construyo un estudio de victoria, empate, derrota y marcadores a 90 minutos. El Mundial 2026 ya estaba jugado al construirlo; no lo presento como un pronóstico publicado previamente. El corte deportivo es exclusivo, **2026-06-10**.

## Estado de la evidencia

Seleccioné los modelos con resultados anteriores a 2023: **logística con Elo y forma** para 1X2 y **Poisson** para marcadores. Son modelos distintos: el 1X2 de Poisson procede de su propia matriz de marcadores y no coincide con el 1X2 de la logística. No mezclo sus probabilidades ni las reconcilio artificialmente.

El periodo 2023–corte es **semiconfirmatorio, no virgen**: la entrega histórica para DataCamp ya puntuó 846 partidos de 2023-01-08 a 2026-06-04. Sus modelos y métricas están excluidos de todas las líneas base y comparaciones del estudio actual. Que esos resultados no hayan intervenido en esta selección no elimina la exposición previa.

La Fase 4 está en la puerta de aprobación. Ya escribí y sellé su protocolo; todavía no calculo métricas desde 2023 ni genero las predicciones finales de los 72 encuentros. Los resultados oficiales del Mundial se cargarán después de congelar las predicciones y su commit.

## Diseño

Los conjuntos se definen sin depender del marcador. Admito todos los registros válidos, reconstruyendo 90 minutos cuando hay evidencia y usando el marcador final como aproximación declarada cuando falta. Una tanda no demuestra empate a 90 minutos. Las marcas de tanda y prórroga permiten análisis de sensibilidad; el catálogo independiente de Mundiales permite comprobar la duración.

Elo utiliza todas las competiciones, pesos por competición, margen de goles y sede real. Los parámetros congelados son sede 100, gamma 1, K de referencia y tasa de regresión 0; con tasa cero, el plazo de inactividad de 730 días no tiene efecto. Las variables de una fecha se calculan antes de actualizar sus resultados. La forma reciente usa únicamente el pasado.

Entrené y comparé frecuencias, Solo Elo, logística con forma, ordinal, XGBoost 1X2, Poisson, Dixon-Coles y XGBoost Poisson. XGBoost permanece como comparador: no demostró una mejora robusta en los bloques de selección. Descanso, competición, altitud y ranking FIFA no cumplieron el criterio de admisión; mercado no tiene pertenencia histórica fechada suficiente. No extrapolo ranking a 2026 ni uso valores actuales de jugadores.

## Documentación y reproducción

- [Resultados y estado actual](RESULTADOS.md): entrada al informe, sin duplicar el congelado.
- [Protocolo de evaluación](reports/final_evaluation/PROTOCOLO.md): población, métricas, incertidumbre y puerta de aprobación.
- [Decisiones de diseño](docs/DECISIONES_DE_DISEÑO.md).
- [Cómo entiendo los modelos](docs/COMO_ENTENDER_EL_MODELO.md): explicación sin conocimientos previos.
- [Índice de auditorías](data_audit.json): enlaces y hashes de los documentos de autoridad.

```powershell
python tools/verify_final_evaluation.py
```

Este comando verifica el congelado y ejecuta pruebas que no evalúan resultados desde 2023. Solo escribe la verificación en reports/final_evaluation/. El CI informa pruebas ejecutadas y omitidas por falta de datos o por exclusión del histórico. Para verificar los commits y etiquetas necesito el historial de Git y la etiqueta models-selected, no solo una copia de los archivos.

Mantengo intactos reports/models_selected/ y sus cinco archivos de código protegidos. No ejecuto los antiguos scripts que regeneran esos informes. La reproducción de selección desde cero corresponde a una copia de trabajo independiente, con las fuentes locales y sus hashes.

Uso archivos locales, sin descargas ni scraping. Los datos grandes permanecen fuera de Git. Conservo metadatos de fixture del archivo histórico como fuente suministrada; no utilizo sus modelos ni sus resultados de evaluación. Cada fuente conserva sus condiciones y el código nuevo tiene licencia MIT.
'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
report=f'''# Resultados y estado del estudio

Este es un estudio retrospectivo, construido con el Mundial 2026 ya jugado. El corte deportivo exclusivo es 2026-06-10. Distingo tres niveles de evidencia: selección anterior a 2023, evaluación semiconfirmatoria 2023–corte y descripción posterior de los 72 partidos. Los dos últimos niveles siguen pendientes de aprobación y ejecución.

## Evidencia de selección anterior a 2023

En los 4.473 no amistosos de los cuatro bloques elegí logística con Elo y forma. Elo es la referencia, no el ganador de todos los candidatos. Poisson es el producto descriptivo de marcadores; ningún modelo de goles cumplió todo el criterio frente a Elo.

{markdown_table(selection,precision=6)}

El resultado completo y sus intervalos están en [el informe congelado](reports/models_selected/RESULTADOS.md). Lo conservo intacto como evidencia de selección. Sus expresiones de periodo «cerrado» o «reservado» describen la separación usada en esa selección, no la virginidad de 2023–corte: el proyecto DataCamp ya había puntuado 846 partidos de ese periodo. Ese trabajo es histórico y superado, no un comparador.

## Dos productos distintos

La logística calcula victoria/empate/derrota directamente. Poisson estima goles y genera una matriz de marcadores, de la cual derivo su propio 1X2. Sus probabilidades no coinciden y no aplico una reconciliación.

En los {discrepancy['matches']} partidos anteriores a 2023, la diferencia absoluta media entre sus tres probabilidades es **{discrepancy['mean_difference_percentage_points']:.4f} puntos porcentuales**. Por clase: victoria {discrepancy['mean_class_difference_percentage_points']['victoria']:.4f}, empate {discrepancy['mean_class_difference_percentage_points']['empate']:.4f}, derrota {discrepancy['mean_class_difference_percentage_points']['derrota']:.4f}. Esta es evidencia de selección, no una evaluación desde 2023. El cálculo está en [pre2023_product_discrepancy.json](reports/final_evaluation/pre2023_product_discrepancy.json).

## Comprobación del sesgo archivado

Uso las etiquetas originales del CSV de descomposición; no etiquetas faltantes del generador histórico. Esta tabla documenta el artefacto, no una mejora vigente.

{markdown_table(bias,precision=6)}

## Evaluación semiconfirmatoria pendiente

El protocolo [PROTOCOLO.md](reports/final_evaluation/PROTOCOLO.md) queda sellado antes de ejecutar métricas y requiere aprobación explícita. Compararé principalmente logística contra Solo Elo en no amistosos; reportaré además partidos con ambos Elo previos >1700 y partidos de las 48 selecciones entre sí o contra cualquier rival.

No reajusto modelos desde 2022 ni cambio umbrales a partir de esta evaluación. La sede tiene ventaja fija 100 y la **tasa de regresión por inactividad es 0**: el plazo 730 días es inerte. La adopción anterior solo se confirma o no se confirma; no selecciono un sustituto con estos resultados.

Después de la aprobación actualizaré solo el estado Elo y forma hasta el corte para generar y congelar los 72 pronósticos. Esta actualización es necesaria antes de sellar las predicciones y no modifica los modelos. No usaré resultados del Mundial. Los commits de protocolo, predicciones congeladas y evaluación serán distintos; usaré sus fechas y los sellos de hash, no las fechas de modificación de archivos.

El informe definitivo de Fase 4 se publicará en reports/final_evaluation/RESULTADOS.md cuando se ejecute. No existe todavía una cifra de rendimiento para ese periodo o el Mundial en esta fase.
'''
(ROOT/'RESULTADOS.md').write_text(report,encoding='utf-8')

human=f'''# Protocolo de evaluación pendiente de aprobación

Construyo un estudio retrospectivo. Este protocolo se escribió en {protocol['written_at_utc']} y se selló en {seal['sealed_at_utc']}, con SHA256 `{seal['protocol_sha256']}`. La autoridad de su registro será el commit de la etiqueta phase4-protocol y este sello, nunca el tiempo de modificación del archivo.

**No calculo métricas con resultados desde 2023 hasta recibir aprobación explícita.** No ejecuto la reproducción del pipeline DataCamp: queda fuera de todas las líneas base y comparaciones. Su exposición previa a 846 partidos convierte 2023–corte en evidencia semiconfirmatoria, no virgen.

## Población, referencia y criterio

Admito todos los registros válidos desde 2023-01-01 hasta antes de 2026-06-10, sin seleccionar por marcador. Uso 90 minutos verificados donde haya evidencia y el final registrado como aproximación donde falte. Marco tandas y prórrogas probadas; una tanda no se transforma automáticamente en empate.

La comparación principal es logística congelada con Elo y forma frente a Solo Elo congelado con sede fija, en no amistosos. Calculo la diferencia pareada de log loss. Confirmo la selección únicamente si el IC superior del 95% es <0, Brier no empeora y la diferencia mejora en al menos tres de estos cuatro periodos: 2023, 2024, 2025 y 2026-01-01 hasta antes de 2026-06-10. No ajusto ni selecciono otro modelo con esta prueba.

## Representatividad

Reporto total, amistosos, no amistosos y Mundiales —con N=0 cuando no existan—. Además:

- Ambos equipos con Elo previo **estrictamente >1700**, sin sumar la ventaja de sede. Fijo el umbral antes de observar esta evaluación.
- Partidos entre dos de las 48 selecciones del fixture de 2026.
- Partidos de al menos una de esas 48 selecciones contra cualquier rival.

Estos estratos se solapan y son secundarios. No cambio el umbral ni la lista de selecciones a partir de los resultados. El umbral absoluto depende de la escala Elo congelada y no define por sí mismo calidad universal.

## Métricas e incertidumbre

Reporto log loss, Brier multiclase sumado, RPS —orden derrota/empate/victoria, suma acumulada dividida por dos—, acierto, tasas de empate reales y previstas, y NLL conjunta de marcador solo en los modelos de goles. Los clasificadores 1X2 no tienen una NLL de marcador inventada.

Uso tablas de fiabilidad con diez intervalos fijos y recuentos, más pendiente e intercepto de calibración por clase. El ECE de diez intervalos es complementario. Ajustar la recta diagnóstica no recalibra las predicciones. Un estrato sin clases suficientes o sin ajuste fiable se informa como no estimable.

Obtengo IC del 95% con **2.000 réplicas de trimestres completos**, semilla 20261012, remuestreo pareado y medias ponderadas por número de partidos. No aplico corrección por comparaciones múltiples: las comparaciones secundarias y los estratos son descriptivos. Informo deriva por cada subperiodo porque los coeficientes siguen entrenados solo hasta 2022.

## Sensibilidades y productos

Evalúo por separado sin tandas/prórrogas marcadas, solo no amistosos y duración estrictamente verificada cuando exista muestra. No reentreno ni cambio la historia de forma del modelo congelado para estas sensibilidades.

Muestro separadamente el 1X2 de la logística, el 1X2 de Poisson y la matriz de marcadores Poisson. No aplico reconciliación. Reporto la diferencia absoluta media por probabilidad, en puntos porcentuales, diferencias por clase y variación total media.

## Orden de ejecución tras aprobar

1. Verifico hashes y registro aprobación real.
2. Actualizo solo Elo y forma con resultados anteriores al corte. Esta entrada es necesaria **antes** de generar las 72 predicciones.
3. Genero todos los pronósticos con el estado fijo al corte, sin actualizar con partidos del Mundial. Compruebo simetría neutral a 1e-9 y probabilidades que suman 1.
4. Sello predicciones y matrices con SHA256 y fecha UTC; creo el commit y la etiqueta phase4-predictions-frozen.
5. Calculo las métricas semiconfirmatorias del protocolo.
6. Cargo resultados oficiales del Mundial después del congelado y evalúo descriptivamente los grupos. Uso bootstrap pareado por fecha, con sensibilidad por partido, y reporto la incertidumbre real de N=72; no fijo un error estándar supuesto ni declaro superioridad por una diferencia pequeña.
7. Evalúo eliminatorias aparte y a 90 minutos solo si existen datos verificables. Creo un commit separado de resultados y evaluación.

Ningún archivo de reports/models_selected/ ni sus cinco archivos de código con hash se modifica. El JSON es el registro completo y autoritativo de estas reglas.
'''
(OUTPUT/'PROTOCOLO.md').write_text(human,encoding='utf-8')
seal['human_protocol_sha256']=digest(OUTPUT/'PROTOCOLO.md')
seal['human_protocol_sealed_at_utc']=utc_now()
(OUTPUT/'protocol_seal.json').write_text(json.dumps(seal,indent=2,ensure_ascii=False),encoding='utf-8')
with (OUTPUT/'chronology.jsonl').open('a',encoding='utf-8') as stream:
    stream.write(json.dumps({'at_utc':seal['human_protocol_sealed_at_utc'],'event':'human_protocol_sealed',
                 'sha256':seal['human_protocol_sha256']},ensure_ascii=False)+'\n')

design=(ROOT/'docs/DECISIONES_DE_DISEÑO.md').read_text(encoding='utf-8')
design=design.replace('Resultados desde 2023 están reservados.','El periodo desde 2023 es semiconfirmatorio: el pipeline histórico DataCamp ya puntuó 846 partidos de 2023-01-08 a 2026-06-04. No uso sus modelos ni métricas como comparadores. La selección vigente solo utilizó resultados anteriores a 2023; esta separación no convierte el periodo posterior en virgen.')
design=design.replace('Elo tiene inicialización 1500, plazo de inactividad 730 días','Elo tiene inicialización 1500, tasa de regresión por inactividad 0 —el plazo de 730 días es inerte con esa tasa—')
design=design.replace('El modelo guardado original permanece intacto.','El modelo guardado de DataCamp permanece histórico y superado, excluido de todas las comparaciones.')
design=design.split('\n\n## Evaluación semiconfirmatoria y puerta de aprobación')[0]
design+='''

## Evaluación semiconfirmatoria y puerta de aprobación

El protocolo nuevo vive en reports/final_evaluation/protocol.json, con sello y commit phase4-protocol. No abro métricas desde 2023 antes de aprobación explícita. Después actualizaré solo el estado causal para congelar 72 predicciones; los modelos no se reajustan. Los commits de protocolo, predicciones y evaluación son separados. Logística y Poisson son productos distintos, sin reconciliación; reporto su discrepancia media.

Los documentos de models_selected se conservan literalmente como registros congelados. Su lenguaje de periodo reservado se interpreta con la salvedad semiconfirmatoria de este registro vigente. README y RESULTADOS son entradas, y data_audit es un índice; no duplico el informe o auditoría congelados.
'''
(ROOT/'docs/DECISIONES_DE_DISEÑO.md').write_text(design,encoding='utf-8')

beginner='''# Cómo entiendo los modelos

Mi modelo elegido no es Solo Elo: es una regresión logística que utiliza Elo y forma reciente. Elo es una medida de fuerza y la referencia contra la que compruebo si algo más complejo merece utilizarse.

Elo se parece a una clasificación que aprende después de cada partido. Ganar contra un rival fuerte aporta más que ganar contra uno débil. Perder contra un favorito suele restar menos que perder contra un rival débil. Mi cálculo también distingue competiciones, margen de goles y sede. No es el ranking FIFA.

La logística aprende a convertir la diferencia de fuerza y la forma reciente en tres probabilidades. Si imagino un marcador de fuerza como un termómetro, Elo es la lectura; la logística es la regla aprendida para traducirla a victoria, empate y derrota. El baseline Solo Elo también ajusta una logística, pero solo con la diferencia efectiva de Elo y sede.

Sí entrené otras alternativas: ordinal, XGBoost, Poisson y Dixon-Coles, además de frecuencias y las dos logísticas. XGBoost puede aprender relaciones más complejas, pero eso no garantiza que sus probabilidades sean mejores fuera del entrenamiento. Con esta configuración y estos datos no mostró una mejora robusta; eso no demuestra que XGBoost sea inferior en cualquier problema.

Elo resume mucha información: resultados anteriores y fuerza de los rivales. Una variable adicional puede repetir lo que ya resume o añadir ruido. Las métricas no identifican por sí solas la causa de cada diferencia; lo que sí muestran es qué mejora se sostuvo en mis bloques y con qué incertidumbre.

No elimino variables por intuición. Probé descanso, competición, altitud y ranking mediante ablación: añadí cada grupo y medí si aportaba. No cumplieron el criterio. El valor de mercado tiene otro problema: no tengo pertenencia histórica fechada suficiente a las selecciones, y usar el club o valor actual introduciría información del futuro.

Poisson responde a otra pregunta: cuántos goles puede marcar cada equipo. A partir de esas tasas genero probabilidades de 0–0, 1–0, 1–1 y otros marcadores; al sumarlas obtengo su propio 1X2. La logística y Poisson no tienen por qué coincidir. Muestro ambos como productos distintos y no hago que parezcan un único modelo.

Nombré el trabajo **Probabilidades de fútbol internacional**, con el subtítulo **Evaluación retrospectiva de Elo, aprendizaje automático y modelos de goles**. Para el repositorio mantengo international-football-probabilities. El nombre describe lo que estudio sin prometer un ganador o una precisión que todavía no he demostrado.
'''
(ROOT/'docs/COMO_ENTENDER_EL_MODELO.md').write_text(beginner,encoding='utf-8')
if (OUTPUT/'verification.json').exists():
    verification=json.loads((OUTPUT/'verification.json').read_text(encoding='utf-8'))
    reasons=verification.get('skip_reasons',[])
    verification['skipped_missing_local_data']=sum(any(token in reason.lower() for token in
        ['local inputs','local archives','local executed feature','raw data']) for reason in reasons)
    verification['skipped_historical_exclusion']=sum('DataCamp' in reason for reason in reasons)
    verification['skip_counts_classified_at_utc']=utc_now()
    (OUTPUT/'verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
registry={'role':'audit index, not a duplicate of frozen audits','updated_at_utc':utc_now(),
 'retrospective':True,'post2022_evidence':'semiconfirmatory due to prior DataCamp exposure; evaluation awaiting explicit approval',
 'models_selected_commit':protocol['frozen_reference']['models_selected_commit'],
 'authoritative_documents':{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':digest(p)} for p in
  [ROOT/'reports/models_selected/data_audit.json',ROOT/'reports/models_selected/freeze_manifest.json',
   OUTPUT/'protocol.json',OUTPUT/'protocol_seal.json',OUTPUT/'pre2023_product_discrepancy.json']},
 'final_evaluation_audit':{'path':'reports/final_evaluation/data_audit.json','status':'not yet generated; awaiting evaluation'},
 'official_worldcup_results_loaded_at_utc':None}
(ROOT/'data_audit.json').write_text(json.dumps(registry,indent=2,ensure_ascii=False),encoding='utf-8')

# Remove empty trailing headings only in the mutable historical preparation report.
path=ROOT/'reports/data_preparation/RESULTADOS.md'
lines=path.read_text(encoding='utf-8').splitlines()
while lines and not lines[-1].strip():lines.pop()
if lines and lines[-1].startswith('#'):
    lines.pop()
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
frozen_checks()
print('Documentación vigente preparada; congelado intacto y sin métricas posteriores a 2022.')
