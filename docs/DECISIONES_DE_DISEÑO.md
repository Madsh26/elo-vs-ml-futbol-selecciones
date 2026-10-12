# Decisiones de diseño

Construyo un estudio retrospectivo con el torneo ya jugado. El corte deportivo exclusivo es 2026-06-10. Registro por separado las fechas reales de preparación, selección, congelado y carga de resultados. No presento el trabajo como un pronóstico publicado previamente.

## Historial y objetivos

Conservo todas las competiciones del historial, identificando torneos no FIFA y categorías sin clasificación específica. Para goles a 90 minutos exijo evidencia reconciliada con el marcador. Una tanda no demuestra empate a 90 minutos. Mantengo eventos aparentemente idénticos y verifico sus cantidades. Los partidos de una fecha comparten el estado anterior a esa fecha.

En Elo uso el marcador a 90 minutos verificado o el final registrado cuando no puedo verificarlo, sin ganador de tanda. Comparo políticas con correlación de puestos entre las 48 selecciones, cambios del top 20 de referencia y diferencias tras centrar las puntuaciones. El top 20 se define dentro de las 48.

## Criterios fijados antes de evaluar modelos

Reservo 2023–2026-06-09 para la Fase 4. Selecciono parámetros Elo con bloques 2016–2017, 2018–2019, 2020–2021 y 2022. En cada bloque ajusto la logística con marcadores verificables desde 2000 hasta el inicio del bloque. Calculo Elo con todo el historial anterior a cada partido. Promedio pérdidas por partido fuera de muestra.

Publico la rejilla acotada en `elo_protocol.json` antes de producir métricas. Uso log loss como criterio principal y Brier multiclase sin dividir como criterio secundario. Calculo intervalos remuestreando trimestres completos, con semilla fija y 400 réplicas. La selección del mínimo introduce optimismo; los intervalos de validación no sustituyen la prueba reservada.

En Fase 3 comparo duración estricta y duración supuesta de amistosos con idénticos bloques y partidos verificables de evaluación. Solo adopto la alternativa si reduce log loss con límite superior del intervalo del cambio menor que cero, no empeora Brier y mejora en al menos tres de los cuatro bloques. Ante incertidumbre conservo duración estricta. No decido esta política en Fase 2.

Para cobertura contrasto entrenamiento ordinario y ponderación por confederación, usando la razón entre participación histórica y participación en etiquetas verificables, calculada únicamente en el bloque de entrenamiento. Acoto pesos entre 0,5 y 2 y normalizo a media uno. Aplico el mismo criterio temporal para adoptarlos. La confederación actual describe estratos administrativos y no reconstruye cambios históricos de afiliación.

El ranking semestral queda disponible el día siguiente al fin del semestre, estrictamente antes del partido, y caduca tras 90 días desde esa disponibilidad conservadora. Lo considero secundario y aplico el mismo criterio de mejora. No extrapolo a 2026.

## Mercado y geografía

Consulto valoraciones fechadas estrictamente antes del partido y del corte. Nunca uso valor actual, club actual ni el ranking de `national_teams`: esa tabla carece de fechas históricas. La nacionalidad de `players` tampoco tiene vigencia fechada. Su agregado es un diagnóstico, no una plantilla histórica verificada; queda fuera del modelo principal hasta disponer de pertenencia jugador–selección fechada. La cobertura de jugadores registrados no representa una convocatoria oficial.

GeoNames aporta altitud estática. Si no identifico una ciudad y su país sin ambigüedad, dejo el dato faltante. No infiero altitud de origen ni viajes reales a partir de nacionalidades.

## Trazabilidad

Guardo fuentes en `data/raw/` con nombres sin espacios ni tildes y verifico sus SHA256. Mantengo Fjelstul y Openfootball separados. Los resultados oficiales de 2026 se admiten solo después de congelar parámetros y predicciones y registrar sus hashes. Conservo la referencia guardada de Elo con amistosos y Mundiales como baseline independiente. Identifico la preparación con la etiqueta Git `data-prepared` y registro la calibración en un commit separado.
