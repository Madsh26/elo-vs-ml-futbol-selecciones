# International Football Probabilities

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
