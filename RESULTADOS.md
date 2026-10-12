# Resultados del estudio

Construyo este estudio retrospectivo con el torneo ya jugado. No lo presento como un pronóstico publicado antes del Mundial. El corte deportivo final es exclusivo, 2026-06-10; todos los resultados usados aquí son anteriores a 2023-01-01. Mantengo 2023–corte cerrado y la evaluación del Mundial pendiente.

## Diseño y aproximación de duración

Los conjuntos de evaluación se definen sin depender del resultado. Admito los 45,845 registros válidos tanto para 1X2 como para goles: uso 90 minutos reconstruidos cuando hay evidencia y el marcador final como aproximación cuando falta. La regla es igual para 0–0 y para cualquier otro marcador. Marco 616 tandas y 159 partidos con goles de prórroga probados; su unión es 763 (1.66%). Esta marca identifica riesgo conocido, no certifica la duración de los demás partidos. Cuando verifico la prórroga, uso el marcador reconstruido. No convierto una tanda automáticamente en empate.

El catálogo estricto tiene 951 Mundiales, con cero partidos en los bloques 2016 y 2020. Lo utilizo para validar la aproximación; no para entrenar un modelo general de goles. Para los modelos ajustados uso resultados desde 2000; el estado Elo y las variables de forma incorporan el historial anterior a cada partido. Las variables de todos los partidos del mismo día se calculan antes de actualizar sus resultados.

No dispongo de amistosos con duración verificada de forma independiente antes de 2023. Por eso la proporción de goles posteriores al minuto 90 en ese subconjunto no puede estimarse: no la informo como 0%. Es una limitación pendiente de los archivos de eventos, no una razón para seleccionar solo empates.

## Selección conjunta de Elo

Registro los criterios en reports/models_selected/protocol.json antes de ejecutar. Comparo 32 combinaciones en cuatro bloques temporales. Aplicando un error estándar pareado y el orden de simplicidad previamente escrito, elijo sede de 100 puntos, regresión de 0 y gamma de 1.0; los pesos K figuran en la tabla. La fila elegida y el mínimo están registrados en selected_elo.json. Inicializo en 1500 y mantengo un plazo de inactividad de 730 días. La regresión de 0.1 de la configuración de referencia procedía de su definición, no de una selección aislada por datos.

| Sede | Inactividad | K amistoso | K Nations | K continental | K Mundial | Gamma | Log loss | Exceso al mínimo | Error estándar pareado | Dentro de 1 EE | Elegida |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 60 | 0.000000 | 12 | 20 | 28 | 40 | 0.500000 | 0.862894 | 0.004588 | 0.001256 | False | False |
| 60 | 0.000000 | 12 | 20 | 28 | 40 | 1.000000 | 0.862797 | 0.004491 | 0.001327 | False | False |
| 60 | 0.000000 | 16 | 24 | 32 | 48 | 0.500000 | 0.862565 | 0.004259 | 0.001136 | False | False |
| 60 | 0.000000 | 16 | 24 | 32 | 48 | 1.000000 | 0.863274 | 0.004968 | 0.001428 | False | False |
| 60 | 0.100000 | 12 | 20 | 28 | 40 | 0.500000 | 0.864272 | 0.005965 | 0.001262 | False | False |
| 60 | 0.100000 | 12 | 20 | 28 | 40 | 1.000000 | 0.864195 | 0.005889 | 0.001252 | False | False |
| 60 | 0.100000 | 16 | 24 | 32 | 48 | 0.500000 | 0.864003 | 0.005697 | 0.001120 | False | False |
| 60 | 0.100000 | 16 | 24 | 32 | 48 | 1.000000 | 0.864717 | 0.006411 | 0.001332 | False | False |
| 100 | 0.000000 | 12 | 20 | 28 | 40 | 0.500000 | 0.860040 | 0.001733 | 0.000807 | False | False |
| 100 | 0.000000 | 12 | 20 | 28 | 40 | 1.000000 | 0.858306 | 0.000000 | 0.000000 | True | True |
| 100 | 0.000000 | 16 | 24 | 32 | 48 | 0.500000 | 0.859203 | 0.000896 | 0.000564 | False | False |
| 100 | 0.000000 | 16 | 24 | 32 | 48 | 1.000000 | 0.858350 | 0.000043 | 0.000413 | True | False |
| 100 | 0.100000 | 12 | 20 | 28 | 40 | 0.500000 | 0.861633 | 0.003327 | 0.000999 | False | False |
| 100 | 0.100000 | 12 | 20 | 28 | 40 | 1.000000 | 0.859843 | 0.001537 | 0.000414 | False | False |
| 100 | 0.100000 | 16 | 24 | 32 | 48 | 0.500000 | 0.860818 | 0.002512 | 0.000793 | False | False |
| 100 | 0.100000 | 16 | 24 | 32 | 48 | 1.000000 | 0.859918 | 0.001611 | 0.000519 | False | False |
| 120 | 0.000000 | 12 | 20 | 28 | 40 | 0.500000 | 0.861730 | 0.003424 | 0.001183 | False | False |
| 120 | 0.000000 | 12 | 20 | 28 | 40 | 1.000000 | 0.858767 | 0.000461 | 0.000570 | True | False |
| 120 | 0.000000 | 16 | 24 | 32 | 48 | 0.500000 | 0.860541 | 0.002234 | 0.001034 | False | False |
| 120 | 0.000000 | 16 | 24 | 32 | 48 | 1.000000 | 0.858487 | 0.000181 | 0.000675 | True | False |
| 120 | 0.100000 | 12 | 20 | 28 | 40 | 0.500000 | 0.863457 | 0.005151 | 0.001340 | False | False |
| 120 | 0.100000 | 12 | 20 | 28 | 40 | 1.000000 | 0.860423 | 0.002117 | 0.000763 | False | False |
| 120 | 0.100000 | 16 | 24 | 32 | 48 | 0.500000 | 0.862289 | 0.003983 | 0.001202 | False | False |
| 120 | 0.100000 | 16 | 24 | 32 | 48 | 1.000000 | 0.860166 | 0.001859 | 0.000808 | False | False |
| 150 | 0.000000 | 12 | 20 | 28 | 40 | 0.500000 | 0.866785 | 0.008479 | 0.001860 | False | False |
| 150 | 0.000000 | 12 | 20 | 28 | 40 | 1.000000 | 0.861899 | 0.003592 | 0.001325 | False | False |
| 150 | 0.000000 | 16 | 24 | 32 | 48 | 0.500000 | 0.865056 | 0.006750 | 0.001771 | False | False |
| 150 | 0.000000 | 16 | 24 | 32 | 48 | 1.000000 | 0.861090 | 0.002784 | 0.001357 | False | False |
| 150 | 0.100000 | 12 | 20 | 28 | 40 | 0.500000 | 0.868717 | 0.010411 | 0.001961 | False | False |
| 150 | 0.100000 | 12 | 20 | 28 | 40 | 1.000000 | 0.863746 | 0.005440 | 0.001436 | False | False |
| 150 | 0.100000 | 16 | 24 | 32 | 48 | 0.500000 | 0.867006 | 0.008700 | 0.001879 | False | False |
| 150 | 0.100000 | 16 | 24 | 32 | 48 | 1.000000 | 0.862953 | 0.004646 | 0.001453 | False | False |

La sensibilidad a las configuraciones que cambian una sola coordenada está en elo_neighbors.csv, con intervalos pareados por trimestres. Elegir el mínimo de esta búsqueda no demuestra una mejora fuera de estos bloques.

## Forma y variables complementarias

Admito la forma con duración supuesta en todo el historial por la decisión explícita del diseño. Repito su comprobación con el Elo elegido y omitiendo tandas/prórrogas marcadas de la historia de forma, del entrenamiento y de la evaluación; conservo esos partidos para actualizar Elo.

| Modelo | Estrato | Partidos | Log loss | Diferencia frente a Elo | IC de diferencia | Diferencia Brier | Bloques con mejora |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Forma con duración supuesta | Total | 6376 | 0.880402 | -0.005418 | [-0.007985; -0.003508] | -0.003521 | 4 |
| Forma con duración supuesta | No amistosos | 4473 | 0.851631 | -0.006675 | [-0.009682; -0.004275] | -0.004435 | 3 |
| Forma con duración supuesta | Amistosos | 1903 | 0.948026 | -0.002463 | [-0.007883; 0.002764] | -0.001374 | 3 |
| Forma sin partidos marcados | Total | 6227 | 0.868353 | -0.005566 | [-0.008313; -0.003566] | -0.003597 | 3 |
| Forma sin partidos marcados | No amistosos | 4329 | 0.833635 | -0.006592 | [-0.009868; -0.004110] | -0.004326 | 3 |
| Forma sin partidos marcados | Amistosos | 1898 | 0.947538 | -0.003228 | [-0.009332; 0.001822] | -0.001934 | 3 |

El criterio se cumple en el historial principal: **True**; al excluir marcados: **True**. Reporto las ablaciones secundarias en secondary_ablations.csv. No incorporo silenciosamente una variable adicional. El ranking semestral solo se usa con disponibilidad posterior al semestre y antigüedad máxima de 90 días; no tengo ranking vigente de 2026. Mercado queda fuera por falta de pertenencia jugador–selección fechada antes de 2023. Altitud, descanso y competición se conservan como diagnósticos de ablación.

## Modelos y selección

La referencia principal es Solo Elo con sede fija. Todos los candidatos comparten partidos y bloques. La logística usa Elo y las diferencias de goles, forma y fuerza de oponentes admitidas. La regresión ordinal utiliza dos umbrales simétricos sobre la diferencia efectiva de Elo. XGBoost usa una configuración pequeña fijada antes de ejecutar, sin ajustar parámetros con resultados del bloque evaluado.

Poisson, Dixon-Coles y XGBoost Poisson comparten una regresión orientada para las dos selecciones; su distribución de marcadores genera también el 1X2. Dixon-Coles incorpora covariables Elo/forma y una corrección conjunta de marcadores bajos; no es una estimación independiente de ataque/defensa para cada selección. Limito tasas a [exp(-6), 12] y la corrección a celdas positivas por partido; reporto activaciones en los archivos de predicción. No calibro el 1X2 de un modelo de goles por separado de sus marcadores. Reporto calibración nativa con ECE y tablas de fiabilidad, sin atribuirle una calibración posterior que no se ejecutó.

Un candidato se admite si, en no amistosos, su diferencia pareada de log loss tiene IC superior menor que cero, Brier no empeora y mejora en al menos tres bloques. Entre candidatos admisibles dentro de un error estándar del mejor, elijo el de menor complejidad según el orden registrado. El modelo seleccionado para 1X2 es **Logística con Elo y forma**. El modelo de marcadores es **Poisson independiente**, con selección por NLL de marcador; cumple el criterio frente a Elo: **False**. Esta selección se debe confirmar en el periodo reservado.

| Modelo | Partidos | Log loss | IC log loss | Brier | Diferencia frente a Elo | IC de diferencia | Bloques con mejora | NLL marcador |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Frecuencias históricas | 4473 | 1.071228 | [1.064107; 1.079794] | 0.649566 | 0.212922 | [0.183664; 0.236435] | 0 | No aplica |
| Solo Elo con sede fija | 4473 | 0.858306 | [0.828912; 0.892527] | 0.503416 | 0.000000 | [0.000000; 0.000000] | 0 | No aplica |
| Logística con Elo y forma | 4473 | 0.851631 | [0.822729; 0.884634] | 0.498981 | -0.006675 | [-0.009682; -0.004275] | 3 | No aplica |
| Regresión ordinal con Elo | 4473 | 0.857636 | [0.827767; 0.891269] | 0.502972 | -0.000670 | [-0.002019; 0.000677] | 3 | No aplica |
| XGBoost 1X2 | 4473 | 0.855941 | [0.827431; 0.887727] | 0.501241 | -0.002365 | [-0.005775; 0.000857] | 2 | No aplica |
| Poisson independiente | 4473 | 0.854577 | [0.824813; 0.886292] | 0.501040 | -0.003730 | [-0.009013; 0.000659] | 2 | 2.863784 |
| Dixon-Coles con covariables | 4473 | 0.853436 | [0.824030; 0.885058] | 0.500466 | -0.004870 | [-0.010129; -0.000660] | 2 | 2.863988 |
| XGBoost Poisson | 4473 | 0.857185 | [0.829791; 0.887647] | 0.501711 | -0.001121 | [-0.005824; 0.002459] | 3 | 2.875824 |

## Estratos y calibración

Brier es la suma multiclase, sin dividir. ECE utiliza diez intervalos de anchura fija por clase. Los intervalos absolutos y pareados de log loss, Brier y NLL de marcador se remuestrean por trimestres completos, con 400 réplicas y semilla fija; no tratan partidos como observaciones independientes. Pueden ser optimistas porque estos mismos bloques se usan para seleccionar; necesito el periodo reservado para confirmar. Fiabilidad por intervalo y resultados por bloque están en reliability.csv y walk_forward_blocks.csv.

| Modelo | Estrato | Partidos | Log loss | Brier | Acierto | ECE victoria | ECE empate | ECE derrota | Empates reales | Empates previstos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Frecuencias históricas | Total | 6376 | 1.07647 | 0.65275 | 0.47867 | 0.09685 | 0.00062 | 0.09747 | 0.23698 | 0.23636 |
| Frecuencias históricas | No amistosos | 4473 | 1.07123 | 0.64957 | 0.47440 | 0.09258 | 0.01034 | 0.08225 | 0.22602 | 0.23636 |
| Frecuencias históricas | Amistosos | 1903 | 1.08881 | 0.66023 | 0.48870 | 0.10689 | 0.02636 | 0.13325 | 0.26274 | 0.23638 |
| Frecuencias históricas | Mundiales | 128 | 1.07149 | 0.64972 | 0.40625 | 0.02459 | 0.01011 | 0.01447 | 0.22656 | 0.23668 |
| Solo Elo con sede fija | Total | 6376 | 0.88582 | 0.52102 | 0.59379 | 0.01582 | 0.01819 | 0.01976 | 0.23698 | 0.23187 |
| Solo Elo con sede fija | No amistosos | 4473 | 0.85831 | 0.50342 | 0.60943 | 0.01523 | 0.01569 | 0.01769 | 0.22602 | 0.22925 |
| Solo Elo con sede fija | Amistosos | 1903 | 0.95049 | 0.56239 | 0.55702 | 0.04646 | 0.02515 | 0.03611 | 0.26274 | 0.23801 |
| Solo Elo con sede fija | Mundiales | 128 | 1.02331 | 0.59961 | 0.54688 | 0.10051 | 0.03135 | 0.10834 | 0.22656 | 0.25791 |
| Logística con Elo y forma | Total | 6376 | 0.88040 | 0.51749 | 0.59959 | 0.01628 | 0.01980 | 0.02296 | 0.23698 | 0.23183 |
| Logística con Elo y forma | No amistosos | 4473 | 0.85163 | 0.49898 | 0.61659 | 0.02103 | 0.01679 | 0.02173 | 0.22602 | 0.22884 |
| Logística con Elo y forma | Amistosos | 1903 | 0.94803 | 0.56101 | 0.55964 | 0.04372 | 0.02686 | 0.04223 | 0.26274 | 0.23884 |
| Logística con Elo y forma | Mundiales | 128 | 1.01454 | 0.59321 | 0.54688 | 0.10301 | 0.03365 | 0.05136 | 0.22656 | 0.26022 |
| Regresión ordinal con Elo | Total | 6376 | 0.88486 | 0.52065 | 0.59379 | 0.01836 | 0.00757 | 0.01823 | 0.23698 | 0.23069 |
| Regresión ordinal con Elo | No amistosos | 4473 | 0.85764 | 0.50297 | 0.60943 | 0.01734 | 0.01290 | 0.02049 | 0.22602 | 0.22732 |
| Regresión ordinal con Elo | Amistosos | 1903 | 0.94886 | 0.56219 | 0.55702 | 0.04144 | 0.02414 | 0.02919 | 0.26274 | 0.23861 |
| Regresión ordinal con Elo | Mundiales | 128 | 1.01720 | 0.59988 | 0.54688 | 0.08128 | 0.03803 | 0.09474 | 0.22656 | 0.26460 |
| XGBoost 1X2 | Total | 6376 | 0.88294 | 0.51900 | 0.59379 | 0.01558 | 0.01764 | 0.02547 | 0.23698 | 0.22998 |
| XGBoost 1X2 | No amistosos | 4473 | 0.85594 | 0.50124 | 0.61011 | 0.02223 | 0.01731 | 0.02401 | 0.22602 | 0.22650 |
| XGBoost 1X2 | Amistosos | 1903 | 0.94641 | 0.56075 | 0.55544 | 0.02575 | 0.02457 | 0.03734 | 0.26274 | 0.23818 |
| XGBoost 1X2 | Mundiales | 128 | 1.01149 | 0.59732 | 0.55469 | 0.08579 | 0.03907 | 0.07627 | 0.22656 | 0.26563 |
| Poisson independiente | Total | 6376 | 0.88430 | 0.52033 | 0.59661 | 0.01789 | 0.02408 | 0.03851 | 0.23698 | 0.21290 |
| Poisson independiente | No amistosos | 4473 | 0.85458 | 0.50104 | 0.61279 | 0.01907 | 0.01957 | 0.03618 | 0.22602 | 0.20929 |
| Poisson independiente | Amistosos | 1903 | 0.95415 | 0.56568 | 0.55859 | 0.04042 | 0.04136 | 0.05284 | 0.26274 | 0.22139 |
| Poisson independiente | Mundiales | 128 | 1.00666 | 0.59232 | 0.53125 | 0.10366 | 0.01781 | 0.07548 | 0.22656 | 0.24437 |
| Dixon-Coles con covariables | Total | 6376 | 0.88291 | 0.51954 | 0.59661 | 0.02296 | 0.01495 | 0.03300 | 0.23698 | 0.22454 |
| Dixon-Coles con covariables | No amistosos | 4473 | 0.85344 | 0.50047 | 0.61301 | 0.02388 | 0.01190 | 0.03064 | 0.22602 | 0.22074 |
| Dixon-Coles con covariables | Amistosos | 1903 | 0.95219 | 0.56439 | 0.55807 | 0.04560 | 0.02928 | 0.04664 | 0.26274 | 0.23346 |
| Dixon-Coles con covariables | Mundiales | 128 | 1.00923 | 0.59297 | 0.53125 | 0.09707 | 0.03132 | 0.05269 | 0.22656 | 0.25788 |
| XGBoost Poisson | Total | 6376 | 0.88466 | 0.51981 | 0.59457 | 0.02009 | 0.02878 | 0.03270 | 0.23698 | 0.21607 |
| XGBoost Poisson | No amistosos | 4473 | 0.85719 | 0.50171 | 0.61033 | 0.02918 | 0.02869 | 0.03070 | 0.22602 | 0.21285 |
| XGBoost Poisson | Amistosos | 1903 | 0.94925 | 0.56236 | 0.55754 | 0.03071 | 0.03977 | 0.04446 | 0.26274 | 0.22363 |
| XGBoost Poisson | Mundiales | 128 | 1.00565 | 0.59347 | 0.54688 | 0.09259 | 0.01752 | 0.07851 | 0.22656 | 0.24408 |

## Sensibilidades de goles y cobertura

goal_sensitivity.csv contiene: exclusión de los partidos marcados, entrenamiento solo con no amistosos y validación sobre Mundiales estrictos. Las comparaciones de cada sensibilidad usan las mismas claves para su referencia. La comprobación estricta tiene únicamente los Mundiales de 2018 y 2022 en estos bloques: no extrapolo su cobertura a amistosos o a todas las confederaciones. Las ausencias de Mundiales en los otros bloques figuran como N=0, no como rendimiento cero.

| Modelo | Política | Partidos | Log loss | Brier | NLL marcador | IC NLL marcador |
| --- | --- | --- | --- | --- | --- | --- |
| Poisson independiente | Sin partidos marcados | 4329 | 0.835936 | 0.487474 | 2.874075 | [2.825439; 2.938994] |
| Poisson independiente | Entrenamiento no amistoso | 4473 | 0.855445 | 0.501585 | 2.866614 | [2.819574; 2.928334] |
| Poisson independiente | Validación Mundial estricta | 128 | 1.006664 | 0.592320 | 2.899396 | [2.580693; 3.028708] |
| Dixon-Coles con covariables | Sin partidos marcados | 4329 | 0.836059 | 0.487587 | 2.874960 | [2.826144; 2.940538] |
| Dixon-Coles con covariables | Entrenamiento no amistoso | 4473 | 0.854475 | 0.501056 | 2.866984 | [2.820731; 2.928574] |
| Dixon-Coles con covariables | Validación Mundial estricta | 128 | 1.009233 | 0.592969 | 2.902573 | [2.570389; 3.028364] |
| XGBoost Poisson | Sin partidos marcados | 4329 | 0.838277 | 0.488021 | 2.884789 | [2.836865; 2.946765] |
| XGBoost Poisson | Entrenamiento no amistoso | 4473 | 0.857045 | 0.501920 | 2.873558 | [2.829910; 2.930903] |
| XGBoost Poisson | Validación Mundial estricta | 128 | 1.005646 | 0.593467 | 2.897402 | [2.566117; 3.005506] |

Conservo las proporciones de 0–0, empates y goles por conjunto y bloque en reports/selection_review/selection_bias_diagnostics.csv. La admisión completa conserva la composición del historial; las diferencias restantes se explican por reconstrucción de etiquetas o por el dominio Mundial. Registro la participación por confederación, competición y año de cada sensibilidad en goal_population_coverage.csv, comparada con el historial desde 2000. Las confederaciones son metadatos actuales usados solo como diagnóstico, no una validación de afiliación histórica. El entrenamiento principal de goles ya no selecciona por cobertura de eventos: comparte exactamente la población del 1X2. No uso ponderaciones actuales de confederación como variables históricas.

## Cuánto explicaba el artefacto

El diagnóstico previo permitía 0–0 sin eventos y excluía otros marcadores en la misma situación. De su mejora agregada de 0.098356, 0.064749 procedía de 197 amistosos, todos 0–0. Conservo esta descomposición para auditar el sesgo, no como resultado vigente.

| Estrato | Partidos | Participación | Log loss Elo | Log loss combinación sesgada | Mejora media | Contribución agregada |
| --- | --- | --- | --- | --- | --- | --- |
| nan | 197 | 0.062859 | 1.033826 | 0.003750 | 1.030076 | 0.064749 |
| nan | 2937 | 0.937141 | 0.892938 | 0.857078 | 0.035861 | 0.033606 |

## Congelado y límites

Congelo modelos entrenados solo hasta 2022, parámetros y protocolo en 2026-10-12T17:07:05.615286+00:00; guardo SHA256 en freeze_manifest.json y data_audit.json. La etiqueta models-selected identifica este estado. No cargo resultados desde 2023 ni resultados oficiales del Mundial en esta fase; no existe todavía una comparación honesta en los 72 partidos. La referencia original guardada continúa intacta y su evaluación se aplaza.

Esta selección y sus intervalos no sustituyen una prueba independiente. La duración supuesta sigue siendo una limitación de medición; excluir los casos conocidos no descarta prórrogas desconocidas. Tampoco tengo composición histórica suficiente para incorporar valor de mercado ni ranking vigente de 2026. No simulo cuadros de torneo ni invento métricas del periodo reservado.
