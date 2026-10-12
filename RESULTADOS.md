# Resultados del estudio

Construyo un estudio retrospectivo de probabilidades de fútbol. El corte deportivo final es exclusivo, 2026-06-10, pero esta selección y sus diagnósticos admiten resultados únicamente hasta 2022. No abro el periodo reservado desde 2023, no entreno XGBoost y no presento este trabajo como un pronóstico publicado antes del Mundial.

En los 4,473 no amistosos de validación, Solo Elo con ventaja fija de sede obtiene log loss **0.8616** y Brier **0.5056**. Ningún grupo de variables con ventanas estrictas cumple el criterio de mejora frente al control Elo + sede. La forma con duración supuesta en todo el historial permanece como sensibilidad favorable, no como información de goles certificada. La selección de Elo cambia ventaja fija de sede y regresión por inactividad; los detalles e incertidumbre están a continuación.

## Principio de evaluación

Defino los conjuntos sin depender del resultado. El 0–0 no recibe una excepción de cobertura. Registro el protocolo y sus criterios antes de ejecutar la revisión: `docs/PROTOCOLO_CONJUNTOS.md` y `reports/selection_review/selection_protocol.json`.

Para 1X2 admito todos los partidos válidos. Reconstruyo 90 minutos cuando hay evidencia; en el resto uso el marcador final registrado como aproximación marcada, que puede incluir prórroga o duración no estándar. Las tandas permanecen en el conjunto y nunca convierten automáticamente la etiqueta en empate. No afirmo que todas estas etiquetas aproximadas sean resultados certificados a 90 minutos.

Para goles estrictos uso un catálogo independiente de partidos: Fjelstul. La ficha sin prórroga permite utilizar cualquier marcador a 90 minutos; los partidos con prórroga requieren reconstrucción por periodo e integridad reconciliada. El listado martj42 de goleadores no define cobertura del conjunto estricto: un partido sin filas de goles puede ser un 0–0 o un partido sin cobertura. Comparo el catálogo con la inclusión de todos los amistosos de duración supuesta y con una suposición explícita en todo el historial.

## Diagnóstico de selección

El historial completo de esta revisión contiene 45,845 partidos anteriores a 2023. El conjunto 1X2 contiene esos mismos 45,845 registros; el conjunto estricto de goles contiene 951. No leo los marcadores del periodo reservado para completar este diagnóstico.

| Conjunto | Partidos | 0–0 registrado % | Empates registrados % | 0–0 etiqueta % | Empates etiqueta % | Diferencia 0–0 (puntos porcentuales) | Diferencia empates (puntos porcentuales) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Historial completo | 45845 | 7.999 | 22.703 | 7.999 | 22.703 | 0.000 | 0.000 |
| Resultado 1X2: todos | 45845 | 7.999 | 22.703 | 8.112 | 22.977 | 0.000 | 0.000 |
| Resultado 1X2: no amistosos | 28564 | 7.681 | 21.268 | 7.863 | 21.709 | -0.318 | -1.435 |
| Resultado 1X2: amistosos | 17281 | 8.524 | 25.074 | 8.524 | 25.074 | 0.525 | 2.371 |
| Goles: Catálogo Fjelstul con duración verificada | 951 | 8.202 | 22.187 | 9.569 | 25.552 | 0.203 | -0.515 |
| Goles: Catálogo verificado y todos los amistosos de duración supuesta | 18232 | 8.507 | 24.923 | 8.578 | 25.099 | 0.508 | 2.221 |
| Goles: Todos los partidos con duración supuesta donde falta verificación | 45845 | 7.999 | 22.703 | 8.112 | 22.977 | 0.000 | 0.000 |
| Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 45845 | 7.999 | 22.703 | 7.999 | 22.703 | 0.000 | 0.000 |
| Diagnóstico archivado: excepción de 0–0 | 17529 | 20.920 | 32.740 | 21.216 | 33.459 | 12.921 | 10.037 |

| Conjunto | Goles registrados por partido | Goles de la etiqueta por partido |
| --- | --- | --- |
| Historial completo | 2.9523 | 2.9523 |
| Resultado 1X2: todos | 2.9523 | 2.9473 |
| Resultado 1X2: no amistosos | 2.9914 | 2.9833 |
| Resultado 1X2: amistosos | 2.8876 | 2.8876 |
| Goles: Catálogo Fjelstul con duración verificada | 2.8254 | 2.7508 |
| Goles: Catálogo verificado y todos los amistosos de duración supuesta | 2.8844 | 2.8805 |
| Goles: Todos los partidos con duración supuesta donde falta verificación | 2.9523 | 2.9473 |
| Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 2.9523 | 2.9523 |
| Diagnóstico archivado: excepción de 0–0 | 2.4395 | 2.4264 |

La caída de goles medios en el diagnóstico archivado acompaña a la sobrerrepresentación de ceros; no la interpreto como menor capacidad ofensiva de las selecciones. Las diferencias del catálogo de Mundiales se interpretan dentro de su dominio y su política de reconstrucción.

La inclusión de todos los registros iguala exactamente las proporciones **registradas** del historial. El estrato no amistoso se compara también con todos los no amistosos; el amistoso, con todos los amistosos. Las tasas del catálogo de Mundiales pueden diferir por el dominio de competiciones; no las fuerzo a igualar las del historial mundial. La reconstrucción de una etiqueta de prórroga puede cambiar la tasa de empate sin cambiar qué partidos entran. La sensibilidad «todos los marcadores registrados» muestra igualdad de composición y de etiquetas por definición; no certifica duración a 90 minutos.

Las tasas y diferencias de **cada conjunto en cada bloque** están en `selection_bias_diagnostics.csv`; las referencias por dominio están en `domain_references.csv`. El diagnóstico archivado conserva la evidencia del sesgo, pero no se utiliza para seleccionar parámetros o variables.

| Inicio del bloque | Conjunto | Partidos | 0–0 registrado % | Empates registrados % | 0–0 etiqueta % | Empates etiqueta % | Diferencia 0–0 (p.p.) | Diferencia empates (p.p.) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016-01-01 | Historial completo | 1844 | 8.948 | 24.295 | 8.948 | 24.295 | 0.000 | 0.000 |
| 2016-01-01 | Resultado 1X2: todos | 1844 | 8.948 | 24.295 | 9.056 | 24.512 | 0.000 | 0.000 |
| 2016-01-01 | Resultado 1X2: no amistosos | 1272 | 8.491 | 22.956 | 8.648 | 23.270 | -0.457 | -1.339 |
| 2016-01-01 | Resultado 1X2: amistosos | 572 | 9.965 | 27.273 | 9.965 | 27.273 | 1.017 | 2.978 |
| 2016-01-01 | Goles: Catálogo Fjelstul con duración verificada | 0 | No disponible | No disponible | No disponible | No disponible | No disponible | No disponible |
| 2016-01-01 | Goles: Catálogo verificado y todos los amistosos de duración supuesta | 572 | 9.965 | 27.273 | 9.965 | 27.273 | 1.017 | 2.978 |
| 2016-01-01 | Goles: Todos los partidos con duración supuesta donde falta verificación | 1844 | 8.948 | 24.295 | 9.056 | 24.512 | 0.000 | 0.000 |
| 2016-01-01 | Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 1844 | 8.948 | 24.295 | 8.948 | 24.295 | 0.000 | 0.000 |
| 2016-01-01 | Diagnóstico archivado: excepción de 0–0 | 843 | 19.573 | 32.622 | 19.810 | 33.096 | 10.625 | 8.327 |
| 2018-01-01 | Historial completo | 2091 | 8.943 | 22.860 | 8.943 | 22.860 | 0.000 | 0.000 |
| 2018-01-01 | Resultado 1X2: todos | 2091 | 8.943 | 22.860 | 9.039 | 23.147 | 0.000 | 0.000 |
| 2018-01-01 | Resultado 1X2: no amistosos | 1422 | 7.876 | 20.323 | 8.017 | 20.745 | -1.067 | -2.536 |
| 2018-01-01 | Resultado 1X2: amistosos | 669 | 11.211 | 28.251 | 11.211 | 28.251 | 2.268 | 5.391 |
| 2018-01-01 | Goles: Catálogo Fjelstul con duración verificada | 64 | 1.562 | 20.312 | 1.562 | 21.875 | -7.381 | -2.547 |
| 2018-01-01 | Goles: Catálogo verificado y todos los amistosos de duración supuesta | 733 | 10.368 | 27.558 | 10.368 | 27.694 | 1.425 | 4.698 |
| 2018-01-01 | Goles: Todos los partidos con duración supuesta donde falta verificación | 2091 | 8.943 | 22.860 | 9.039 | 23.147 | 0.000 | 0.000 |
| 2018-01-01 | Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 2091 | 8.943 | 22.860 | 8.943 | 22.860 | 0.000 | 0.000 |
| 2018-01-01 | Diagnóstico archivado: excepción de 0–0 | 886 | 21.106 | 31.377 | 21.332 | 32.054 | 12.163 | 8.517 |
| 2020-01-01 | Historial completo | 1471 | 8.634 | 23.521 | 8.634 | 23.521 | 0.000 | 0.000 |
| 2020-01-01 | Resultado 1X2: todos | 1471 | 8.634 | 23.521 | 8.770 | 23.997 | 0.000 | 0.000 |
| 2020-01-01 | Resultado 1X2: no amistosos | 1152 | 8.160 | 23.438 | 8.333 | 24.045 | -0.474 | -0.084 |
| 2020-01-01 | Resultado 1X2: amistosos | 319 | 10.345 | 23.824 | 10.345 | 23.824 | 1.711 | 0.303 |
| 2020-01-01 | Goles: Catálogo Fjelstul con duración verificada | 0 | No disponible | No disponible | No disponible | No disponible | No disponible | No disponible |
| 2020-01-01 | Goles: Catálogo verificado y todos los amistosos de duración supuesta | 319 | 10.345 | 23.824 | 10.345 | 23.824 | 1.711 | 0.303 |
| 2020-01-01 | Goles: Todos los partidos con duración supuesta donde falta verificación | 1471 | 8.634 | 23.521 | 8.770 | 23.997 | 0.000 | 0.000 |
| 2020-01-01 | Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 1471 | 8.634 | 23.521 | 8.634 | 23.521 | 0.000 | 0.000 |
| 2020-01-01 | Diagnóstico archivado: excepción de 0–0 | 976 | 13.012 | 27.869 | 13.217 | 28.586 | 4.379 | 4.347 |
| 2022-01-01 | Historial completo | 970 | 7.938 | 22.680 | 7.938 | 22.680 | 0.000 | 0.000 |
| 2022-01-01 | Resultado 1X2: todos | 970 | 7.938 | 22.680 | 8.144 | 22.887 | 0.000 | 0.000 |
| 2022-01-01 | Resultado 1X2: no amistosos | 627 | 7.177 | 22.488 | 7.496 | 22.807 | -0.761 | -0.192 |
| 2022-01-01 | Resultado 1X2: amistosos | 343 | 9.329 | 23.032 | 9.329 | 23.032 | 1.391 | 0.352 |
| 2022-01-01 | Goles: Catálogo Fjelstul con duración verificada | 64 | 10.938 | 23.438 | 12.500 | 23.438 | 2.999 | 0.757 |
| 2022-01-01 | Goles: Catálogo verificado y todos los amistosos de duración supuesta | 407 | 9.582 | 23.096 | 9.828 | 23.096 | 1.644 | 0.415 |
| 2022-01-01 | Goles: Todos los partidos con duración supuesta donde falta verificación | 970 | 7.938 | 22.680 | 8.144 | 22.887 | 0.000 | 0.000 |
| 2022-01-01 | Goles: Todos los marcadores registrados, sensibilidad sin reconstrucción | 970 | 7.938 | 22.680 | 7.938 | 22.680 | 0.000 | 0.000 |
| 2022-01-01 | Diagnóstico archivado: excepción de 0–0 | 429 | 17.949 | 31.702 | 18.415 | 32.168 | 10.011 | 9.021 |

## Cuánto explicaba el artefacto

    | Estrato | Partidos | Participación | Log loss Elo | Log loss combinación sesgada | Mejora media | Contribución a la mejora agregada |
| --- | --- | --- | --- | --- | --- | --- |
| Amistosos | 197 | 0.062859 | 1.033826 | 0.003750 | 1.030076 | 0.064749 |
| No amistosos | 2937 | 0.937141 | 0.892938 | 0.857078 | 0.035861 | 0.033606 |

Esta descomposición utiliza los mismos partidos de aquella validación. La aportación de los amistosos seleccionados solo por 0–0 no demuestra capacidad predictiva y retiro esa comparación como evidencia vigente de mejora. Las selecciones y ablaciones siguientes utilizan conjuntos independientes del marcador.

## Parámetros de Elo

Selecciono por log loss de no amistosos en cuatro bloques anteriores a 2023. Ajusto la logística con todos los 1X2 disponibles antes de cada bloque, incluidos amistosos de duración supuesta. El estado Elo se actualiza después de calcular todas las variables de una fecha. La tabla presenta los parámetros, no números arbitrarios de configuración.

| Configuración | K amistosos | K Nations League | K continental/eliminatorias | K Mundial | K otros | Multiplicador γ | Ventaja sede | Regresión anual | Inactividad mínima (días) | Inicial | Log loss no amistosos | Brier no amistosos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pesos de referencia | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.100000 | 730 | 1500 | 0.864272 | 0.507289 |
| Pesos menores | 8 | 16 | 24 | 32 | 16 | 0.500000 | 60 | 0.100000 | 730 | 1500 | 0.865730 | 0.508189 |
| Pesos mayores | 16 | 24 | 32 | 48 | 16 | 0.500000 | 60 | 0.100000 | 730 | 1500 | 0.864003 | 0.507150 |
| Sin multiplicador de goles | 12 | 20 | 28 | 40 | 16 | 0.000000 | 60 | 0.100000 | 730 | 1500 | 0.867539 | 0.509467 |
| Multiplicador de goles fuerte | 12 | 20 | 28 | 40 | 16 | 1.000000 | 60 | 0.100000 | 730 | 1500 | 0.864195 | 0.507188 |
| Sede sin ventaja fija | 12 | 20 | 28 | 40 | 16 | 0.500000 | 0 | 0.100000 | 730 | 1500 | 0.887637 | 0.521974 |
| Sede con ventaja fija mayor | 12 | 20 | 28 | 40 | 16 | 0.500000 | 100 | 0.100000 | 730 | 1500 | 0.861633 | 0.505563 |
| Sin regresión por inactividad | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.000000 | 730 | 1500 | 0.862894 | 0.506382 |
| Regresión por inactividad mayor | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.250000 | 730 | 1500 | 0.865772 | 0.508298 |
| Regresión tras un año | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.100000 | 365 | 1500 | 0.866393 | 0.508597 |
| Inicialización común 1400 | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.100000 | 730 | 1400 | 0.864272 | 0.507289 |
| Inicialización común 1600 | 12 | 20 | 28 | 40 | 16 | 0.500000 | 60 | 0.100000 | 730 | 1600 | 0.864272 | 0.507289 |
| Sin margen, sede ni regresión | 12 | 20 | 28 | 40 | 16 | 0.000000 | 0 | 0.000000 | 730 | 1500 | 0.890990 | 0.524197 |

La configuración seleccionada es **Sede con ventaja fija mayor**. Comparo sus parámetros con la selección diagnosticada:

| Parámetro | Selección con cohorte sesgada | Selección con conjuntos independientes |
| --- | --- | --- |
| Ventaja fija de sede (puntos) | 60 | 100.000 |
| Tasa anual de regresión por inactividad | 0 | 0.100 |

Una inicialización común de 1400, 1500 o 1600 solo desplaza la escala; conservo 1500 como convención. Los pesos de partidos no FIFA usan el peso de amistosos y siguen identificados; «otros» no implica reconocimiento oficial.

El multiplicador de diferencia de goles es 1 + γ × log(1 + diferencia absoluta). La ventaja de sede configurada es 100 puntos y aparece tanto en las actualizaciones del estado como en la diferencia efectiva del baseline Solo Elo. Elo + sede comparte esa ventaja y permite un coeficiente adicional aprendido en el entrenamiento. Así las ablaciones no reciben una sede que falte a su referencia.

El coeficiente adicional de sede no cumple el criterio frente a Solo Elo con ventaja fija; conservo la referencia más sencilla como baseline principal 1X2. Elo + sede permanece como control común para las ablaciones.

## Evaluación temporal y ablaciones

| Modelo | Estrato | Partidos | Log loss | IC 95 % | Brier | IC 95 % Brier |
| --- | --- | --- | --- | --- | --- | --- |
| Solo Elo con ventaja de sede fija | Todos | 6376 | 0.889439 | [0.8666, 0.9189] | 0.523424 | [0.5088, 0.5425] |
| Solo Elo con ventaja de sede fija | No amistosos | 4473 | 0.861633 | [0.8309, 0.8972] | 0.505563 | [0.4863, 0.5282] |
| Solo Elo con ventaja de sede fija | Amistosos | 1903 | 0.954796 | [0.9246, 0.9831] | 0.565405 | [0.5464, 0.5836] |
| Elo + sede | Todos | 6376 | 0.889964 | [0.8672, 0.9191] | 0.523779 | [0.5091, 0.5426] |
| Elo + sede | No amistosos | 4473 | 0.862337 | [0.8317, 0.8976] | 0.505990 | [0.4867, 0.5285] |
| Elo + sede | Amistosos | 1903 | 0.954901 | [0.9245, 0.9829] | 0.565592 | [0.5464, 0.5841] |
| Goles y forma reciente: catálogo verificado | Todos | 6376 | 0.889490 | [0.8670, 0.9183] | 0.523840 | [0.5090, 0.5426] |
| Goles y forma reciente: catálogo verificado | No amistosos | 4473 | 0.861935 | [0.8312, 0.8961] | 0.505952 | [0.4862, 0.5284] |
| Goles y forma reciente: catálogo verificado | Amistosos | 1903 | 0.954259 | [0.9235, 0.9840] | 0.565885 | [0.5457, 0.5852] |
| Descanso observado | Todos | 6376 | 0.890085 | [0.8673, 0.9195] | 0.523757 | [0.5092, 0.5427] |
| Descanso observado | No amistosos | 4473 | 0.862373 | [0.8320, 0.8976] | 0.505974 | [0.4870, 0.5284] |
| Descanso observado | Amistosos | 1903 | 0.955221 | [0.9232, 0.9845] | 0.565556 | [0.5461, 0.5842] |
| Contexto de competición | Todos | 6376 | 0.890069 | [0.8663, 0.9195] | 0.523609 | [0.5081, 0.5429] |
| Contexto de competición | No amistosos | 4473 | 0.863404 | [0.8315, 0.8995] | 0.506539 | [0.4865, 0.5300] |
| Contexto de competición | Amistosos | 1903 | 0.952747 | [0.9224, 0.9810] | 0.563733 | [0.5450, 0.5818] |
| Altitud de sede | Todos | 6376 | 0.890285 | [0.8675, 0.9198] | 0.523975 | [0.5092, 0.5430] |
| Altitud de sede | No amistosos | 4473 | 0.862602 | [0.8315, 0.8983] | 0.506196 | [0.4866, 0.5289] |
| Altitud de sede | Amistosos | 1903 | 0.955356 | [0.9240, 0.9833] | 0.565765 | [0.5465, 0.5840] |
| Puesto FIFA | Todos | 6376 | 0.889984 | [0.8673, 0.9190] | 0.523768 | [0.5092, 0.5424] |
| Puesto FIFA | No amistosos | 4473 | 0.862410 | [0.8321, 0.8981] | 0.505962 | [0.4867, 0.5285] |
| Puesto FIFA | Amistosos | 1903 | 0.954798 | [0.9247, 0.9824] | 0.565620 | [0.5464, 0.5839] |
| Puesto y puntos FIFA | Todos | 6376 | 0.890344 | [0.8678, 0.9192] | 0.523949 | [0.5095, 0.5427] |
| Puesto y puntos FIFA | No amistosos | 4473 | 0.862808 | [0.8325, 0.8979] | 0.506159 | [0.4868, 0.5285] |
| Puesto y puntos FIFA | Amistosos | 1903 | 0.955066 | [0.9252, 0.9823] | 0.565764 | [0.5470, 0.5837] |
| Forma con todos los amistosos de duración supuesta | Todos | 6376 | 0.889663 | [0.8666, 0.9186] | 0.523836 | [0.5086, 0.5428] |
| Forma con todos los amistosos de duración supuesta | No amistosos | 4473 | 0.861950 | [0.8304, 0.8970] | 0.505765 | [0.4854, 0.5277] |
| Forma con todos los amistosos de duración supuesta | Amistosos | 1903 | 0.954800 | [0.9240, 0.9839] | 0.566312 | [0.5462, 0.5852] |
| Forma con duración supuesta en todo el historial | Todos | 6376 | 0.882455 | [0.8605, 0.9105] | 0.518919 | [0.5050, 0.5372] |
| Forma con duración supuesta en todo el historial | No amistosos | 4473 | 0.853031 | [0.8228, 0.8841] | 0.499895 | [0.4808, 0.5200] |
| Forma con duración supuesta en todo el historial | Amistosos | 1903 | 0.951617 | [0.9201, 0.9788] | 0.563635 | [0.5439, 0.5815] |
| Pesos de cobertura: sensibilidad administrativa | Todos | 6376 | 0.889964 | [0.8672, 0.9191] | 0.523779 | [0.5091, 0.5426] |
| Pesos de cobertura: sensibilidad administrativa | No amistosos | 4473 | 0.862337 | [0.8317, 0.8976] | 0.505990 | [0.4867, 0.5285] |
| Pesos de cobertura: sensibilidad administrativa | Amistosos | 1903 | 0.954901 | [0.9245, 0.9829] | 0.565592 | [0.5464, 0.5841] |
| Elo + sede con etiqueta final registrada | Todos | 6376 | 0.888722 | [0.8657, 0.9183] | 0.522762 | [0.5082, 0.5419] |
| Elo + sede con etiqueta final registrada | No amistosos | 4473 | 0.860393 | [0.8297, 0.8955] | 0.504408 | [0.4844, 0.5269] |
| Elo + sede con etiqueta final registrada | Amistosos | 1903 | 0.955308 | [0.9250, 0.9832] | 0.565902 | [0.5467, 0.5845] |

Uso Brier multiclase sin dividir. Los intervalos remuestrean trimestres completos con 400 réplicas y semilla fija. No simulo torneos. Comparo cada grupo contra **Elo + sede**; el criterio de admisión se aplica exclusivamente a no amistosos: intervalo pareado de log loss con límite superior menor que cero, Brier sin empeorar y mejora en al menos tres de cuatro bloques.

| Grupo frente a Elo + sede | Cambio log loss | IC pareado | Cambio Brier | Bloques con mejora |
| --- | --- | --- | --- | --- |
| Solo Elo con ventaja de sede fija | -0.000704 | [-0.00149, 0.00006] | -0.000427 | 2.000000 |
| Elo + sede | 0.000000 | [0.00000, 0.00000] | 0.000000 | 0.000000 |
| Goles y forma reciente: catálogo verificado | -0.000401 | [-0.00384, 0.00236] | -0.000038 | 2.000000 |
| Descanso observado | 0.000037 | [-0.00052, 0.00064] | -0.000016 | 2.000000 |
| Contexto de competición | 0.001067 | [-0.00040, 0.00282] | 0.000549 | 1.000000 |
| Altitud de sede | 0.000265 | [-0.00048, 0.00098] | 0.000206 | 2.000000 |
| Puesto FIFA | 0.000074 | [-0.00087, 0.00099] | -0.000028 | 2.000000 |
| Puesto y puntos FIFA | 0.000471 | [-0.00038, 0.00131] | 0.000169 | 0.000000 |
| Forma con todos los amistosos de duración supuesta | -0.000386 | [-0.00469, 0.00364] | -0.000225 | 2.000000 |
| Forma con duración supuesta en todo el historial | -0.009305 | [-0.01391, -0.00591] | -0.006095 | 3.000000 |
| Pesos de cobertura: sensibilidad administrativa | 0.000000 | [0.00000, 0.00000] | 0.000000 | 0.000000 |

Los grupos que pasan individualmente son: ninguno. La combinación de los grupos que pasan no cumple o no corresponde aplicar el criterio. Las ventanas de goles de duración supuesta son sensibilidades y no se adoptan automáticamente por su rendimiento. La selección comparte los bloques de validación y requiere todavía la prueba reservada.

La sensibilidad de forma con duración supuesta en todo el historial obtiene log loss 0.853031 en no amistosos, frente a Elo + sede 0.862337. Pasa el criterio estadístico, pero no la admito como información de goles certificada a 90 minutos: requiere aceptar explícitamente esa aproximación. Mantengo el catálogo verificado como política principal de goles.

Los datos por partido, los resultados de cada bloque y los intervalos de los tres estratos se conservan en `walk_forward_predictions.csv`, `walk_forward_blocks.csv` y `feature_ablation.csv`. La sensibilidad de etiqueta registrada utiliza los mismos partidos con otra definición de resultado y se informa de forma absoluta, sin presentarla como mejora pareada frente a otra etiqueta.

## Límites de información

31,905 etiquetas 1X2 usan duración no verificada. Admito 616 partidos con tanda y marco 159 con goles de prórroga probados, sin excluirlos por ese resultado. Los cruces de catálogo ausentes y los conflictos de integridad están listados por partido.

El ranking semestral tiene disponibilidad conservadora posterior al semestre y antigüedad máxima de 90 días; no extrapolo a 2026. Mercado queda fuera: no tengo pertenencia jugador–selección fechada antes de 2023. La altitud es estática; descanso significa días desde el último internacional observado, no recuperación física medida. La ponderación por confederaciones actuales es una sensibilidad administrativa, no una afiliación histórica certificada ni una política de producción.

Registro fecha de revisión, hashes, exclusiones, políticas y decisiones en `data_audit.json`. No sello predicciones ni cargo resultados oficiales de 2026. La Fase 3 queda pendiente de aprobación.
