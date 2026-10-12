"""Present the active design as one retrospective study, without stale claims."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'README.md').write_text('''# International Football Probabilities

Estudio retrospectivo de probabilidades de fútbol para mi portafolio. Mi objetivo es estimar victoria, empate, derrota y marcadores a 90 minutos y comprobar si los modelos aportan evidencia frente a referencias sencillas.

El corte deportivo final es exclusivo: **2026-06-10**. La selección actual de parámetros y variables utiliza solo resultados anteriores a **2023-01-01**. Mantengo 2023–corte reservado y no presento el trabajo como un pronóstico publicado antes del Mundial. La fase de modelos, incluido XGBoost, queda pendiente de aprobación.

## Definición de los conjuntos

**Los conjuntos de evaluación se definen sin depender del resultado.** No admito un 0–0 por una excepción de cobertura. Uso dos conjuntos con objetivos distintos:

- **Resultado 1X2:** todos los registros válidos, sin excluir empates, marcadores con goles, tandas o prórrogas. Reconstruyo 90 minutos cuando hay evidencia; cuando no la hay, uso el marcador final como aproximación marcada. Una tanda no determina un empate a 90 minutos. Separo amistosos y no amistosos en todos los informes.
- **Goles estrictos a 90 minutos:** el catálogo independiente de partidos masculinos de Fjelstul. La ficha sin prórroga permite utilizar cualquier marcador; los casos con prórroga se reconstruyen por periodo. No uso la presencia de filas de goleadores como criterio de admisión: ese listado no certifica cobertura de partidos sin goles.

Las sensibilidades incorporan todos los amistosos o todo el historial con una suposición de duración declarada y común a todos los marcadores. No confundo esas etiquetas con duración certificada ni adopto una política para que su tasa de empates parezca conveniente.

## Validación

Uso cuatro bloques: 2016–2017, 2018–2019, 2020–2021 y 2022. Cada entrenamiento termina antes de su bloque de evaluación. Todas las variables de una fecha se calculan antes de actualizar con sus resultados. Selecciono Elo por log loss de no amistosos; informo también amistosos y total, con Brier multiclase sin dividir e intervalos por remuestreo de trimestres completos.

Solo Elo incluye la ventaja fija de sede en su diferencia efectiva. Elo + sede comparte esa ventaja y permite un coeficiente adicional aprendido. Comparo cada grupo de variables contra Elo + sede. La admisión requiere un intervalo pareado favorable, Brier sin empeorar y mejora en al menos tres bloques. Los resultados están en [RESULTADOS.md](RESULTADOS.md); las tasas por conjunto y bloque, en [selection_bias_diagnostics.csv](reports/selection_review/selection_bias_diagnostics.csv).

El diagnóstico de sesgo es una comprobación estándar: comparo ceros y empates del historial con cada conjunto y su dominio de competiciones. Conservo la descomposición de la mejora sesgada como evidencia de por qué no debe interpretarse como rendimiento vigente.

## Reproducción local

```powershell
python fix_selection_bias.py
python tools/verify_selection_review.py
python tools/complete_selection_review.py
```

La ejecución no descarga archivos ni simula torneos. Utiliza como máximo dos hilos numéricos por defecto. El protocolo se guarda antes de calcular métricas. Las fuentes grandes y los historiales procesados no se incluyen automáticamente en el repositorio; necesito los archivos locales con los hashes de la auditoría para reproducirlos.

Las pruebas cubren admisión independiente del marcador, ausencia de excepción para ceros sin cobertura, catálogo de duración para cualquier marcador, reconstrucción de periodos, corte temporal, consultas as-of, simetría, probabilidades normalizadas y claves idénticas de evaluación. La reproducción de la referencia guardada que necesita resultados del periodo reservado se aplaza hasta la Fase 4 y aparece como prueba omitida explícitamente.

## Fuentes

| Archivo local | Uso |
| --- | --- |
| data/raw/international_results_current.zip | Historial, goles, tandas y nombres históricos; filtro de fecha antes de interpretar marcadores |
| data/raw/fjelstul_worldcup.zip | Catálogo de partidos y verificación de duración y periodos |
| data/raw/fifa_rank_semesters.zip | Ablación secundaria con disponibilidad posterior al semestre y caducidad de 90 días |
| data/raw/fifa_rank_repeated_snapshot_excluded.csv | Fotografía repetida excluida; no es un histórico |
| data/raw/geonames_cities15000.zip | Altitud estática de ciudad y país sin ambigüedad |
| data/raw/transfermarkt.duckdb | Diagnóstico previo de cobertura; mercado fuera del modelo por falta de pertenencia fechada antes de 2023 |
| data/raw/statsbomb_open_data.zip | Validación opcional; no se incorpora al entrenamiento en esta revisión |
| data/raw/openfootball_worldcup.zip | Resultados de 2026 reservados hasta el congelado; no se cargan en esta revisión |

No tengo ranking FIFA vigente de 2026 y no lo extrapolo. No uso valor actual, club actual, nacionalidad actual como pertenencia histórica ni ranking de national_teams. No invento viajes o altitud del lugar de entrenamiento a partir de una nacionalidad. Mantengo entidades históricas distintas y documentadas las excepciones de cruce del catálogo.

## Trazabilidad

[data_audit.json](data_audit.json) registra fechas reales, cortes, hashes, incertidumbre de duración, criterios, parámetros, decisiones y pruebas. [PROTOCOLO_CONJUNTOS.md](docs/PROTOCOLO_CONJUNTOS.md) fija las reglas antes de la ejecución. [DECISIONES_DE_DISEÑO.md](docs/DECISIONES_DE_DISEÑO.md) describe el diseño.

La etiqueta data-prepared identifica la preparación inicial y selection-bias-fixed identifica la revisión de selección. Mantengo los archivos de informes previos como diagnósticos históricos; la narrativa vigente está en RESULTADOS.md y reports/selection_review/. La referencia guardada se conserva para una comparación posterior, sin reentrenarla ni usar sus resultados reservados en esta selección.

Uso archivos locales de martj42, The Fjelstul World Cup Database, StatsBomb, dcaribou, el ranking semestral suministrado, GeoNames, Openfootball y los fixtures de DataCamp. Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.
''',encoding='utf-8')
(ROOT/'docs/DISENO_DATOS.md').write_text('''# Definición del historial y del resultado

Construyo un estudio retrospectivo y separo pertenencia a un conjunto, reconstrucción de la etiqueta e integridad de las fuentes. El corte deportivo final es 2026-06-10; la selección actual solo admite resultados anteriores a 2023.

## Pertenencia independiente del resultado

No uso marcador, empate, goles o ganador para definir cobertura. El conjunto 1X2 contiene todo registro válido del dominio declarado. Una tanda permanece en el historial: no transforma automáticamente un marcador en empate. Cuando puedo reconstruir 90 minutos, uso ese resultado; cuando no puedo, conservo el final registrado como aproximación y marco la incertidumbre.

El catálogo de Fjelstul identifica partidos independientemente de la presencia de goles. La ficha sin prórroga certifica el resultado a 90 minutos para cualquier marcador. La reconstrucción con prórroga utiliza periodos del corpus y reconciliación de cantidades. Distingo conflictos de integridad de ausencia de cruce de identidad/fecha; ambas listas permanecen visibles.

No considero que la ausencia de filas en goalscorers demuestre cobertura de un 0–0. Martj42 lista goles y codifica descuento como 90; sus eventos completos pueden ayudar a reconstruir una etiqueta 1X2, pero no definen admisión al conjunto estricto de goles. StatsBomb distingue descuento y prórroga por periodo y queda reservado para validación.

## Sensibilidades

El conjunto estricto de goles usa el catálogo independiente. Las alternativas agregan todos los amistosos o todos los registros con duración supuesta, sin excepciones por marcador, tanda o ausencia de goles. Cada ventana de ataque y defensa utiliza solo partidos previos admitidos bajo su política y conserva cobertura. Un promedio con pocos partidos tiene un prior fijo equivalente a tres encuentros de 1,3 goles; no lo presento como goles observados.

Los indicadores de verificación del partido actual no son predictores: se utilizan para auditoría de etiquetas. Las variables de forma provienen de resultados previos. Las suposiciones de duración se informan por separado y no se convierten en prueba de duración física del partido.

## Diagnóstico estándar

Comparo 0–0 y empates registrados y de la etiqueta, por conjunto y bloque. El conjunto completo 1X2 tiene las mismas proporciones registradas que el historial por construcción. Una diferencia en la etiqueta reconstruida puede deberse a prórroga y no a selección. Comparo además dominios equivalentes: amistosos con amistosos, no amistosos con no amistosos y catálogo de Mundiales con Mundiales. No igualo tasas de dominios distintos artificialmente.

## Identidad y tiempo

Aplico el filtro de fecha antes de interpretar goles. Los alias históricos respetan intervalos; Czechoslovakia y Czech Republic permanecen distintas. Las sedes se normalizan como territorios, no como sucesiones de federaciones. Los partidos del mismo día comparten el estado anterior a ese día.

Mercado no tiene pertenencia fechada antes de 2023 y queda excluido. El ranking semestral se considera disponible el día siguiente al fin del semestre y caduca a 90 días; no hay extrapolación a 2026. La altitud de sede es estática; las ciudades ambiguas y viajes no verificables permanecen faltantes.

## Registro y sellado

El protocolo de conjuntos se fija antes de ejecutar las métricas. Guardo decisiones, fechas y hashes en data_audit.json. La selección actual no carga resultados reservados ni entrena XGBoost. El congelado del modelo y predicciones y la carga de resultados oficiales siguen pendientes. No presento el estudio como una publicación anterior al torneo.
''',encoding='utf-8')
(ROOT/'docs/DECISIONES_DE_DISEÑO.md').write_text('''# Decisiones de diseño

Construyo un estudio retrospectivo con el torneo ya jugado. El corte deportivo final es exclusivo, 2026-06-10. Las fechas reales de preparación, selección, revisión, congelado y carga de resultados son operaciones distintas; no presento el trabajo como un pronóstico publicado previamente.

## Principio de evaluación

**Los conjuntos de evaluación se definen sin depender del resultado.** Exijo la misma cobertura o la misma suposición de duración a todos los marcadores. Un 0–0 no recibe una excepción que excluiría un partido con goles en la misma situación. La comprobación estándar compara proporciones de 0–0 y empates por conjunto, dominio y bloque antes de atribuir mejoras a variables o modelos.

El protocolo previo a ejecución está en PROTOCOLO_CONJUNTOS.md; su fecha y SHA256 están registrados en selection_protocol.json. La descomposición del sesgo queda conservada como diagnóstico, no como evidencia vigente de rendimiento.

## Dos objetivos y dos conjuntos

Admito todos los registros válidos para 1X2, incluidos amistosos, tandas y prórrogas. Reconstruyo 90 minutos con evidencia o uso el final como aproximación declarada. Una tanda nunca determina automáticamente empate. Reporto amistosos y no amistosos por separado y el total.

Para goles estrictos uso un catálogo independiente de partidos, Fjelstul. Una ficha sin prórroga admite cualquier marcador; con prórroga reconstruyo por periodo y reconcilio integridad. La presencia de goles en martj42 no define cobertura del conjunto estricto. Las sensibilidades añaden todos los amistosos o todo el historial bajo una suposición común de duración.

## Selección temporal

No abro resultados desde 2023. Uso bloques 2016–2017, 2018–2019, 2020–2021 y 2022, ajustando una logística con los 1X2 desde 2000 hasta cada inicio de bloque. Selecciono parámetros Elo por log loss de no amistosos; el estado usa todo el historial previo y se actualiza después de calcular todas las variables de una fecha.

Solo Elo incluye la ventaja configurada de sede en su diferencia efectiva. Elo + sede comparte esa ventaja y permite un coeficiente adicional aprendido. Comparo todos los grupos contra Elo + sede. Un grupo pasa si el intervalo pareado de log loss de no amistosos tiene límite superior menor que cero, Brier no empeora y mejora en tres o más de cuatro bloques. Las sensibilidades de duración no se adoptan automáticamente.

Uso 400 remuestreos de trimestres completos con semilla fija, log loss y Brier sin dividir. Informo intervalos y tasas de empate en los tres estratos. La selección comparte bloques y requiere evaluación independiente. No interpreto el mínimo de una rejilla como mejora demostrada en el Mundial.

## Variables complementarias

El ranking semestral está disponible conservadoramente después de acabar el semestre y caduca a 90 días. Lo contrasto mediante ablación, sin extrapolar a 2026. Mercado queda excluido por ausencia de pertenencia jugador–selección fechada antes de 2023; no uso los campos actuales de players o national_teams como históricos.

GeoNames aporta altitud estática de una sede identificada sin ambigüedad. No infiero altitud de entrenamiento o viajes reales de una nacionalidad. Los pesos por confederaciones actuales son una sensibilidad administrativa y no certifican afiliación histórica. En 1X2, admitir todo el historial elimina la diferencia de cobertura entre entrenamiento y su referencia de registros.

## Trazabilidad

Guardo fuentes en data/raw/ con nombres sin espacios ni tildes y verifico SHA256. Mantengo Fjelstul y Openfootball separados. Los resultados oficiales de 2026 solo se admiten después del congelado y sus hashes. La referencia guardada permanece intacta. La etiqueta selection-bias-fixed identifica esta revisión; la Fase 3 requiere aprobación.
''',encoding='utf-8')
for relative in ['reports/data_preparation/RESULTADOS.md','reports/feature_design/RESULTADOS.md']:
    path=ROOT/relative
    # Preserve factual old material as an explicitly retired diagnostic.
    text=path.read_text(encoding='utf-8')
    text=text.replace('En esta preparación no entrené modelos ni cargué resultados oficiales posteriores al corte.',
                      'La preparación descrita aquí constituye un registro histórico de auditoría.')
    title='# Diagnóstico histórico de selección\n\nEste archivo conserva la evidencia anterior a la regla de conjuntos independientes del resultado. Sus métricas no son evidencia vigente de mejora. La narrativa del diseño y sus resultados vigentes están en [RESULTADOS.md](../../RESULTADOS.md) y reports/selection_review/.\n\n'
    if not text.startswith('# Diagnóstico histórico de selección'):path.write_text(title+text,encoding='utf-8')
print('Documentación del diseño vigente actualizada; evidencia histórica conservada.')
