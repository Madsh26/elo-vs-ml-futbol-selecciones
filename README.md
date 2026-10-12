# International Football Probabilities

Estudio probabilístico de los partidos de grupos del Mundial 2026 con datos locales. Mi objetivo es estimar victoria, empate, derrota y marcadores a 90 minutos, y comprobar qué modelos aportan evidencia frente a referencias sencillas.

Construyo el estudio con el torneo ya jugado. El corte de información deportiva es exclusivo: **2026-06-10**. No presento el trabajo como un pronóstico publicado antes del Mundial ni uso sus resultados para elegir modelos o variables.

## Preparación de datos

```powershell
python prepare_data.py
python calibrate_features.py
python -B -m unittest discover -s tests -v
python tools/verify_project.py
python tools/finalize_feature_audit.py
```

La preparación no descarga archivos ni entrena modelos. Separa el historial que permite calcular Elo del conjunto que permite aprender goles comparables a 90 minutos. Los resultados de esta operación están en [RESULTADOS.md](reports/data_preparation/RESULTADOS.md) y sus decisiones, hashes y fechas en [data_audit.json](reports/data_preparation/data_audit.json).

La preparación y la calibración temporal de Elo están implementadas. Los resultados ejecutados se describen en [RESULTADOS.md](RESULTADOS.md). Selecciono parámetros con cuatro bloques anteriores a 2023. La comparación de XGBoost, las políticas de duración y ponderación, la evaluación reservada y la comparación oficial de 2026 corresponden a operaciones posteriores.

La extensión del estado Elo con los resultados de 2023–corte queda pendiente hasta abrir la evaluación reservada. En el fixture de esta fase identifico metadatos y altitud; no publico puntuaciones o forma de 2022 como si estuvieran vigentes en 2026.

En validación, la logística con Elo, forma reciente y contexto de competición/sede cumple el criterio de selección. Descarto ranking, puntos FIFA, descanso, altitud y ponderación por cobertura como variables del conjunto principal de esta logística. No atribuyo esta selección a XGBoost: su comparación corresponde a la fase de modelos.

La cobertura de amistosos verificables solo incluye marcadores 0–0 invariantes. Por eso informo resultados globales y de partidos no amistosos por separado; no interpreto el excelente resultado observado en esos amistosos como rendimiento generalizable.

## Fuentes locales

| Fuente | Uso |
| --- | --- |
| `data/raw/international_results_current.zip` | Resultados, goles y tandas anteriores al corte; nombres históricos |
| `data/raw/fjelstul_worldcup.zip` | Fjelstul: verificación de partidos y periodos de gol |
| `reports/probabilistic/resolved_fixtures.csv` | Metadatos del fixture de 72 partidos ya resuelto; no contiene resultados oficiales |
| `data/raw/fifa_rank_semesters.zip` | Ranking por año y semestre, pendiente de una ablación con rezago conservador |
| `data/raw/statsbomb_open_data.zip` | StatsBomb, reservado para validación |
| `data/raw/geonames_cities15000.zip` | Altitud estática, reservada para contexto de sede |
| `data/raw/openfootball_worldcup.zip` | Openfootball, separado de Fjelstul; resultados reservados para evaluación después del sellado |

El archivo `fifa_rank_repeated_snapshot_excluded.csv` está excluido: repite la misma fotografía en fechas distintas. No dispongo de un ranking vigente para 2026. El archivo por semestre que inspeccioné llega a 2024; solo puede estudiarse con disponibilidad posterior al fin del semestre y un máximo de 90 días de antigüedad.

Inspecciono las tablas de Transfermarkt en data/raw/transfermarkt.duckdb. Las valoraciones se filtran por fecha. La nacionalidad actual no demuestra pertenencia histórica a una selección; por eso publico cobertura de la base como diagnóstico y excluyo estos agregados del modelo principal. No uso valor actual, club actual ni el ranking actual de national_teams.

## Qué partidos conservo

Conservo todas las competiciones presentes en los resultados válidos para el historial, incluidas eliminatorias, campeonatos continentales y Nations League. Identifico por separado amistosos, competiciones principales, otros torneos y torneos no FIFA; no afirmo que cualquier encuentro distinto de un amistoso tenga reconocimiento oficial FIFA.

Para entrenar goles utilizo eventos completos que coinciden con los goles de ambos equipos y cuyos minutos puedo interpretar. Fjelstul identifica periodos de prórroga. En martj42 el descuento de la segunda mitad se codifica como minuto 90. No traslado esa regla a StatsBomb: allí el periodo permite distinguir descuento y prórroga.

Una tanda no implica que el partido terminara empatado a 90 minutos: puede resolver una eliminatoria con marcador agregado. Tampoco elimino eventos aparentemente idénticos sin contrastarlos con la cantidad de goles del partido.

Si no puedo reconstruir un marcador a 90 minutos, lo excluyo únicamente como etiqueta de goles. Para Elo utilizo el marcador final registrado, que puede incluir prórroga, sin usar al ganador de la tanda. Las ventanas de ataque y defensa omiten esos goles no comparables y registran su cobertura.

Un amistoso sin evidencia de duración queda fuera del conjunto principal de goles. En una alternativa de sensibilidad declaro duración estándar para amistosos sin tanda conocida y sin eventos disponibles. Los partidos con evidencia contradictoria o minutos faltantes no reciben esa excepción.

La [definición del historial](docs/DISENO_DATOS.md) explica cada decisión y la interpretación de las cinco políticas de sensibilidad.

## Ausencia de información futura

- Filtro las fechas antes de interpretar y conservar goles, minutos y otros valores de resultado.
- Los datos del 10 de junio de 2026 y posteriores no entran al historial ni al entrenamiento.
- Para todos los partidos de una fecha calculo las características antes de actualizar el historial con cualquiera de sus resultados.
- Los alias históricos tienen vigencia explícita. Mantengo Czechoslovakia y Czech Republic como entidades distintas.
- Una sede geográfica no se renombra como si fuera una federación histórica.
- Las fechas de corte, preparación, congelado y carga de resultados oficiales son campos distintos. Las dos últimas permanecen vacías hasta ejecutar esas operaciones.

## Sensibilidad

Comparo el historial completo, el uso de marcadores finales registrados, la restricción a marcadores a 90 minutos admisibles y la inclusión alternativa de amistosos de duración supuesta. Mantengo fijos los parámetros Elo para aislar el efecto de estas políticas.

La referencia **Elo con amistosos y Mundiales** se identifica internamente como `baseline_elo_amistosos`. Su modelo guardado se conserva sin reentrenar. Los cambios en cobertura o Elo no demuestran mejores probabilidades: la evaluación fuera de muestra debe comprobarlo.

## Salidas de la preparación

```text
reports/data_preparation/
    historical_results.csv
    goal_training_90.csv
    goal_exclusions.csv
    historical_features.csv
    goal_training_features.csv
    fixture_features.csv
    competition_coverage.csv
    team_coverage.csv
    name_registry.csv
    elo_policy_sensitivity.csv
    sensitivity_summary.csv
    data_audit.json
    RESULTADOS.md
```

Los datos fuente no se incluyen automáticamente en el repositorio. Para reproducir la preparación se requieren los archivos locales y sus hashes. La ejecución usa como máximo dos hilos en las librerías numéricas por defecto; no realiza simulaciones de torneos.

## Código y comprobaciones

`ingestion.py` define el resultado y las exclusiones. `preparation.py` construye el estado por fecha y las tablas de sensibilidad. La interfaz `load_study_local` devuelve separados el historial completo, los objetivos de goles y las tablas opcionales de enriquecimiento.

Las pruebas comprueban el corte exclusivo, nombres e identidades históricas, conservación de eventos iguales, reconstrucción de prórrogas, tandas que no implican empate y ventanas que no utilizan goles inciertos ni resultados de la misma fecha. Las comprobaciones de los modelos guardados se mantienen como pruebas de la referencia independiente.

Las decisiones están descritas en [el registro de diseño](docs/DECISIONES_DE_DISEÑO.md). La etiqueta Git data-prepared identifica la preparación de fuentes y objetivos.

## Atribución

Uso los archivos locales de international football results de martj42, The Fjelstul World Cup Database, StatsBomb open-data, transfermarkt-datasets de dcaribou, el ranking semestral suministrado, GeoNames, Openfootball y los fixtures de DataCamp. Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.

