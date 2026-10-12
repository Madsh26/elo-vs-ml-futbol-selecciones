# Protocolo aprobado y condiciones previas

El protocolo completo y autoritativo es **reports/final_evaluation/protocol_approved.json**. Su SHA256 cubre exactamente los bytes de ese archivo JSON, no el directorio, el modelo ni este documento. Conservo protocol.json, su sello y la etiqueta phase4-protocol sin modificaciones.

Registro la aprobación explícita y estas condiciones en 2026-10-12T20:04:26.027163+00:00. Creo un commit y etiqueta nuevos: phase4-protocol-approved. Antes de calcular cualquier métrica desde 2023 generaré y congelaré los 72 pronósticos, con su propio commit phase4-predictions-frozen.

## Umbral comprobado sin datos desde 2023

Mantengo ambos Elo previos estrictamente >1700, sin ventaja de sede. El estrato completo cumple los mínimos en los cuatro bloques; el cruce no amistoso de 2022 queda descriptivo con N=184.

| Inicio | Fin exclusivo | Población | Todos | Ambos >1700 | Victorias A | Empates | Victorias B | Estimable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016-01-01 | 2018-01-01 | total | 1844 | 377 | 165 | 114 | 98 | True |
| 2016-01-01 | 2018-01-01 | non_friendlies | 1272 | 256 | 113 | 80 | 63 | True |
| 2016-01-01 | 2018-01-01 | friendlies | 572 | 121 | 52 | 34 | 35 | False |
| 2018-01-01 | 2020-01-01 | total | 2091 | 416 | 175 | 119 | 122 | True |
| 2018-01-01 | 2020-01-01 | non_friendlies | 1422 | 223 | 87 | 65 | 71 | True |
| 2018-01-01 | 2020-01-01 | friendlies | 669 | 193 | 88 | 54 | 51 | False |
| 2020-01-01 | 2022-01-01 | total | 1471 | 347 | 157 | 103 | 87 | True |
| 2020-01-01 | 2022-01-01 | non_friendlies | 1152 | 287 | 127 | 85 | 75 | True |
| 2020-01-01 | 2022-01-01 | friendlies | 319 | 60 | 30 | 18 | 12 | False |
| 2022-01-01 | 2023-01-01 | total | 970 | 260 | 120 | 62 | 78 | True |
| 2022-01-01 | 2023-01-01 | non_friendlies | 627 | 184 | 84 | 41 | 59 | False |
| 2022-01-01 | 2023-01-01 | friendlies | 343 | 76 | 36 | 21 | 19 | False |

Al 2022-12-31, 39 de 48 selecciones superan 1700. Guardo sus 48 valores en worldcup_48_elo_2022_12_31.csv, calculados con resultados anteriores a 2023; la fecha del último resultado es 2022-12-30.

## Mínimos e incertidumbre

Un estrato o subperiodo es estimable para inferencia solo con **al menos 200 partidos y 30 eventos de cada clase**. Cuando no alcanza el mínimo, muestro recuentos y métricas descriptivas, sin superioridad ni regresiones de calibración. Los 72 partidos del Mundial serán descriptivos por diseño.

El periodo semiconfirmatorio permite **14 trimestres y 42 meses de calendario**, con el último incompleto. Reportaré el número de clústeres efectivamente observados para cada población. El criterio primario mantiene 2.000 réplicas trimestrales pareadas; añado 2.000 réplicas mensuales como sensibilidad, con semilla 20261012. No sustituyo el criterio trimestral por el resultado mensual.

Se mantienen las demás reglas del [protocolo previo](PROTOCOLO.md): comparación principal de logística contra Solo Elo, cuatro subperiodos, duración supuesta marcada, separación Logística/Poisson, modelos sin reajuste, exclusión de DataCamp y congelado anterior a resultados oficiales. 2023–corte sigue siendo semiconfirmatorio por exposición previa.
