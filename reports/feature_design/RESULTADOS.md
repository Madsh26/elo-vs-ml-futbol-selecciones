# Diagnóstico histórico de selección

Este archivo conserva la evidencia anterior a la regla de conjuntos independientes del resultado. Sus métricas no son evidencia vigente de mejora. La narrativa del diseño y sus resultados vigentes están en [RESULTADOS.md](../../RESULTADOS.md) y reports/selection_review/.

# Calibración del estado histórico

Construyo este estudio retrospectivo con corte deportivo exclusivo 2026-06-10. Seleccioné Elo sin evaluar el periodo reservado desde 2023. Comparé 13 configuraciones con una logística de una sola variable: diferencia de Elo. Las predicciones se reconcilian con el orden inverso para respetar simetría.

| Configuración | Log loss | Brier | Partidos |
| --- | --- | --- | --- |
| 0 | 0.902016 | 0.537450 | 3134 |
| 1 | 0.903247 | 0.538332 | 3134 |
| 2 | 0.901945 | 0.537374 | 3134 |
| 3 | 0.904417 | 0.538914 | 3134 |
| 4 | 0.902069 | 0.537508 | 3134 |
| 5 | 0.902096 | 0.537594 | 3134 |
| 6 | 0.902555 | 0.537742 | 3134 |
| 7 | 0.901794 | 0.537333 | 3134 |
| 8 | 0.902293 | 0.537610 | 3134 |
| 9 | 0.902727 | 0.537769 | 3134 |
| 10 | 0.902016 | 0.537450 | 3134 |
| 11 | 0.902016 | 0.537450 | 3134 |
| 12 | 0.903840 | 0.538624 | 3134 |

La configuración seleccionada es 7. Sus intervalos del 95 % son [0.8597140934640295, 0.9441387195094818] para log loss y [0.5107536756265428, 0.5662226745942446] para Brier. Remuestreo trimestres completos con 400 réplicas; no simulo torneos. La rejilla y las reglas se guardaron antes de calcular estas métricas. Seleccionar el mínimo de varias configuraciones introduce optimismo: todavía necesito la prueba reservada para juzgar la mejora.

| Inicio del bloque | Partidos | Log loss | Brier |
| --- | --- | --- | --- |
| 2016-01-01 | 843 | 0.912257 | 0.543742 |
| 2018-01-01 | 886 | 0.875261 | 0.520713 |
| 2020-01-01 | 976 | 0.853350 | 0.509307 |
| 2022-01-01 | 429 | 1.046246 | 0.622825 |

## Inicialización e inactividad

Una puntuación inicial común de 1400, 1500 o 1600 solo desplaza la escala: no distingue la fuerza inicial de las selecciones y no cambia las diferencias. Uso 1500 como convención. La historia completa sirve como calentamiento. La regresión por inactividad reduce la diferencia respecto a ese centro tras el plazo configurado. La rejilla es acotada y no una búsqueda exhaustiva.

## Parámetros seleccionados

| Competición | Peso K |
| --- | --- |
| Amistosos | 12 |
| Nations League | 20 |
| Continentales y eliminatorias | 28 |
| Mundial | 40 |
| Otras competiciones | 16 |

Uso una ventaja de sede de 60 puntos Elo y un multiplicador de goles de 1 + 0.5 × log(1 + diferencia absoluta de goles). La puntuación inicial común es 1500. La tasa de regresión por inactividad seleccionada es 0: no aplico esa regresión. La diferencia de log loss entre configuraciones es pequeña; la elección no demuestra una mejora robusta.

## Ranking secundario

El archivo termina en el segundo semestre de 2024. Asumo disponibilidad desde 2025-01-01, posterior al semestre; esa fecha no es una publicación observada. Exijo antigüedad máxima de 90 días y fecha estrictamente anterior al partido. No hay ranking vigente para 2026.

Elo: log loss 0.901794; Elo con ranking: 0.902269. Cambio pareado: 0.000475, intervalo [-0.0007974916212332998, 0.0018842951664766105]. Mejoró en 1 de cuatro bloques. Aplicando el criterio escrito, descarto el ranking del conjunto principal de variables.

## Alcance

Esta operación selecciona parámetros del estado Elo y estudia ranking secundario. No selecciona XGBoost ni una política de duración de amistosos. No evalúa partidos oficiales de 2026 ni congela un pronóstico. No atribuyo estos resultados a una prueba independiente del diseño.

## Variables y cobertura

Uso los parámetros Elo seleccionados para calcular estado y variables disponibles antes de cada partido. Construyo las variables históricas solo hasta 2022. Dejo Elo, forma y descanso del fixture pendientes hasta abrir el periodo reservado en Fase 4; no presento el estado de 2022 como vigente en 2026. El ranking de ambas selecciones está faltante en los 72 partidos de 2026.

La altitud se identifica en 34.9% del historial y 80.6% de las sedes del fixture, con ciudad y país sin ambigüedad; conservo la procedencia de elevación o DEM. El descanso significa días desde el último partido internacional observado. No tengo datos para reconstruir viajes reales o altitud del lugar de entrenamiento.

Las alineaciones internacionales fechadas empiezan en 2024-01-12; no hay ninguna antes de 2023. Identifico un conjunto de jugadores observados en los últimos 730 días para 17 de las 48 selecciones. Consulto las valoraciones anteriores al corte y publico cobertura del conjunto observado, no de una convocatoria oficial, en dated_market_coverage.csv. No incorporo mercado al modelo principal: no puedo validar su aporte en los bloques de selección sin abrir el periodo reservado. El adaptador as-of queda implementado para una fuente con más historia.

La ventaja de sede se representa con signo respecto a ambos equipos; elimino host_away del conjunto de características de este diseño. La referencia independiente conserva su contrato original. Contrasto estos grupos con una logística mediante ablaciones temporales. Su evaluación con XGBoost y modelos de goles corresponde a la Fase 3.

## Ranking y puntos conjuntamente

Además del puesto, contrasté los puntos FIFA, normalizando la diferencia por la suma de puntos para evitar mezclar escalas históricas. Este contraste tiene su propio protocolo fechado antes de ejecutarlo y utiliza los parámetros Elo ya seleccionados. Los faltantes tienen indicadores explícitos.

Log loss: 0.902555; Brier: 0.537798. Cambio de log loss respecto a Elo: 0.000761, intervalo [-0.000490938143671981, 0.0021381899157004304]. Mejoró en 1 de cuatro bloques. Descarto también el grupo conjunto de puesto y puntos del modelo principal. No uso resultados desde 2023 para esta decisión.

## Ablación de variables y cobertura

Comparé cada grupo con la misma logística sobre Elo, en los mismos partidos y bloques anteriores a 2023. Mantengo fijos los parámetros seleccionados y C=1. Cada contraste usa el criterio escrito antes de ejecutarlo.

| Grupo | Log loss | Brier | Cambio de log loss | IC inferior | IC superior | Bloques con mejora | Admitido |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Goles y forma reciente | 0.888251 | 0.527859 | -0.013543 | -0.022724 | -0.006394 | 3 | Sí |
| Días desde el último partido | 0.901819 | 0.537345 | 0.000024 | -0.000142 | 0.000163 | 2 | No |
| Competición y sede | 0.809187 | 0.478374 | -0.092608 | -0.116368 | -0.073262 | 4 | Sí |
| Altitud de sede | 0.902256 | 0.537212 | 0.000462 | -0.002158 | 0.002974 | 2 | No |
| Ponderación por cobertura | 0.902351 | 0.537437 | 0.000557 | -0.000881 | 0.001795 | 2 | No |
| Grupos admitidos conjuntamente | 0.803438 | 0.474785 | -0.098356 | -0.126915 | -0.076227 | 4 | Sí |

La ponderación es una sensibilidad descriptiva con estratos administrativos actuales; no puedo certificar afiliación histórica por fecha y no la habilito como política de producción. La ponderación utiliza solo cobertura del bloque de entrenamiento y conserva el estrato sin cruce. No abre resultados del bloque siguiente para calcular pesos. La selección de variables comparte los bloques de validación: los intervalos son descriptivos y la comparación independiente sigue pendiente. No atribuyo este resultado a XGBoost.

## Sesgo observable de amistosos

| Modelo | Conjunto observado | Partidos | Log loss | Brier |
| --- | --- | --- | --- | --- |
| Solo Elo | Amistosos | 197 | 1.033826 | 0.671668 |
| Solo Elo | No amistosos | 2937 | 0.892938 | 0.528322 |
| Elo, forma y contexto | Amistosos | 197 | 0.003750 | 0.000033 |
| Elo, forma y contexto | No amistosos | 2937 | 0.857078 | 0.506629 |

Los 197 amistosos verificables de validación son todos marcadores finales 0–0 invariantes. El indicador de competición aprende en parte esta selección: su excelente resultado en esos amistosos no permite afirmar capacidad de pronóstico sobre amistosos generales. En los partidos no amistosos, el intervalo pareado del cambio de log loss de la combinación es [-0.053810303611971734, -0.019681305199110134]. «No amistosos» incluye las categorías de la fuente, no certifica reconocimiento oficial de cada torneo. La mejora queda limitada a esta validación y requiere la evaluación reservada.
