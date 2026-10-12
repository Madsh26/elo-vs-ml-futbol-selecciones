# Datos y definición del resultado

Construí el estudio con archivos locales y un corte exclusivo del 2026-06-10. El trabajo se realiza con el torneo ya jugado; no representa un pronóstico publicado antes del Mundial. En esta preparación no entrené modelos ni cargué resultados oficiales posteriores al corte.

## Qué representa cada resultado

Conservo 49,469 partidos en el historial. Para predecir goles a 90 minutos dispongo de 19,342 marcadores con evidencia. Los 30,127 casos restantes conservan su participación en el historial, pero no aportan etiquetas de goles ni goles a las ventanas recientes. No admito supuestos de duración en el conjunto principal. La alternativa de sensibilidad admite 16,592 amistosos adicionales suponiendo duración estándar.

Uso eventos completos que coinciden con los goles de ambos equipos y que tienen minutos válidos. En martj42 el descuento se codifica como minuto 90; Fjelstul distingue los periodos de prórroga. Conservo las filas de eventos aparentemente repetidas y compruebo sus cantidades contra el marcador. Una tanda no determina automáticamente un empate en el partido.

Para Elo utilizo el marcador a 90 minutos cuando puedo reconstruirlo. Si no puedo, uso el marcador final registrado, que puede incluir prórroga. No uso al ganador de la tanda. Marco esta diferencia para medir su efecto.

## Cobertura por competición

| Tipo de competición | Partidos del historial | Marcadores admisibles |
| --- | --- | --- |
| Campeonatos continentales | 3251 | 3215 |
| Amistosos | 18194 | 1558 |
| Ligas de Naciones | 1080 | 679 |
| Torneos no FIFA | 245 | 15 |
| Otras competiciones | 9795 | 995 |
| Eliminatorias | 15940 | 11916 |
| Mundiales | 964 | 964 |

El grupo «other_tournament» conserva competiciones cuya categoría requiere una clasificación más específica; no afirmo que todas sean competiciones oficiales FIFA. Las competiciones identificadas como no FIFA permanecen etiquetadas.

## Cobertura desde 2023 hasta el corte

| Tipo de competición | Partidos del historial | Marcadores admisibles |
| --- | --- | --- |
| Campeonatos continentales | 313 | 312 |
| Amistosos | 913 | 85 |
| Ligas de Naciones | 439 | 204 |
| Torneos no FIFA | 17 | 0 |
| Otras competiciones | 439 | 39 |
| Eliminatorias | 1503 | 1173 |

Estos son tamaños de conjuntos disponibles, no métricas de predicción.

## Sensibilidad de la política del historial

Mantengo los mismos parámetros Elo para comparar únicamente qué partidos y marcadores incorpora el historial. La elección y calibración temporal de esos parámetros es una operación posterior y separada.

| Política del historial | Cambio medio de Elo | Cambio máximo de Elo |
| --- | --- | --- |
| Historial completo con prioridad a 90 minutos | 0.00 | 0.00 |
| Historial completo con marcador final registrado | 2.25 | 10.70 |
| Solo marcadores a 90 minutos admisibles | 72.93 | 188.15 |
| Marcadores verificables y amistosos de duración supuesta | 32.40 | 85.24 |
| Elo con amistosos y Mundiales | 114.49 | 190.88 |

| Política del historial | Selección | Elo | Puesto en las entidades de la fuente | Partidos |
| --- | --- | --- | --- | --- |
| Historial completo con prioridad a 90 minutos | Colombia | 1871.30 | 5 | 638 |
| Historial completo con prioridad a 90 minutos | Portugal | 1860.71 | 6 | 694 |
| Historial completo con marcador final registrado | Colombia | 1866.07 | 5 | 638 |
| Historial completo con marcador final registrado | Portugal | 1864.72 | 6 | 694 |
| Solo marcadores a 90 minutos admisibles | Colombia | 1683.15 | 21 | 397 |
| Solo marcadores a 90 minutos admisibles | Portugal | 1786.55 | 5 | 418 |
| Marcadores verificables y amistosos de duración supuesta | Colombia | 1836.61 | 5 | 607 |
| Marcadores verificables y amistosos de duración supuesta | Portugal | 1832.72 | 6 | 681 |
| Elo con amistosos y Mundiales | Colombia | 1782.33 | 4 | 263 |
| Elo con amistosos y Mundiales | Portugal | 1698.36 | 12 | 320 |

Los puestos se calculan sobre las entidades presentes en cada escenario, no son puestos del ranking FIFA. Un cambio de Elo no demuestra mejor capacidad predictiva. La evaluación de modelos debe comprobarlo en partidos que no intervienen en su ajuste.

## Fuentes disponibles y límites

Inspeccioné las tablas de Transfermarkt y documento su cobertura a continuación. El ranking por semestre termina en 2024 y no se extrapola a 2026.

Mantengo Fjelstul y Openfootball como fuentes distintas. No leo el README ni los marcadores de 2026 de Openfootball para decidir el diseño. StatsBomb queda reservado para validación de marcadores y periodos. GeoNames se reserva para altitud estática.

No sello un modelo en esta preparación. En la auditoría dejo vacías las fechas de congelado y carga de resultados oficiales; se registrarán al ejecutar esas operaciones.

## Duración observable de amistosos

Entre los 0 amistosos con eventos completos, 0 tienen algún gol posterior al minuto 90 (proporción no estimable: no hay amistosos con eventos completos); 0 aparecen en tandas. Esta muestra seleccionada no demuestra la duración de los amistosos sin eventos. El descuento está codificado como minuto 90.

## Representación del entrenamiento de goles

Cuento participaciones de selecciones: cada partido aporta dos. Las tablas por año, competición y confederación están en `coverage_bias.csv`. Uso la confederación actual únicamente para describir cobertura; conservo las entidades históricas sin cruce como categoría explícita.

| Confederación | Participaciones históricas | Participaciones con goles verificables | Representación relativa |
| --- | --- | --- | --- |
| AFC | 15023 | 4577 | 0.78 |
| CAF | 8145 | 3022 | 0.95 |
| CONCACAF | 7530 | 3074 | 1.04 |
| CONMEBOL | 7655 | 4241 | 1.42 |
| OFC | 684 | 236 | 0.88 |
| UEFA | 30795 | 15958 | 1.33 |
| Unmapped historical entity | 29106 | 7576 | 0.67 |

La selección de partidos con eventos puede cambiar qué selecciones y competiciones aprende el modelo. En la comparación temporal contrastaré entrenamiento ordinario con pesos por confederación calculados solo en el bloque de entrenamiento, acotados entre 0,5 y 2. El grupo sin cruce seguirá identificado; no inventaré afiliaciones históricas.

## Valoraciones y pertenencia a selecciones

Inspeccioné el DuckDB en modo de solo lectura. Excluí 94 valoraciones del corte o posteriores. `transfermarkt_coverage.csv` informa el porcentaje de jugadores de la base con valoración anterior al corte para las 48 selecciones. El denominador es la población de jugadores registrada por nacionalidad actual; no es una plantilla oficial de 23 jugadores.

No uso valor actual, club actual, convocatorias actuales ni el ranking de `national_teams`. Las nacionalidades disponibles tampoco tienen fechas de vigencia. Por eso el agregado por nacionalidad queda como diagnóstico y adaptador experimental, sin atribuirle pertenencia histórica verificada ni usarlo en el modelo principal. Para incorporar valor de una plantilla necesito una relación fechada entre jugador y selección.
