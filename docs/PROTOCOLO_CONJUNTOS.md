# Protocolo de conjuntos y selección temporal

Registro esta regla antes de ejecutar la revisión: **los conjuntos de evaluación se definen sin depender del resultado**. Exijo la misma cobertura o la misma suposición de duración para todos los marcadores posibles. No uso el 0–0 como excepción de admisión. Distingo la pertenencia al conjunto, la reconstrucción de su etiqueta y las comprobaciones de integridad de la fuente.

El estudio es retrospectivo. No abro resultados desde 2023: todas las operaciones de esta revisión leen únicamente filas con fecha estrictamente anterior a 2023-01-01, antes de interpretar los marcadores. El corte deportivo final del estudio sigue siendo 2026-06-10. No entreno XGBoost ni evalúo el Mundial 2026 en esta operación.

## Resultado 1X2

Admito todo partido con registro válido, independientemente del marcador. Separo amistosos y no amistosos como estratos explícitos; «no amistoso» no certifica reconocimiento oficial FIFA. Ninguno se excluye por empate, goles, tanda o prórroga.

La etiqueta principal utiliza el resultado a 90 minutos cuando puedo reconstruirlo con periodos verificados de Fjelstul o con eventos completos reconciliados de martj42. En los demás casos utiliza el marcador final registrado como aproximación declarada: puede incluir prórroga o una duración no estándar. Una tanda no obliga a un empate y su ganador no modifica la etiqueta. Registro tandas, goles probados de prórroga y falta de verificación. El resultado registrado sin reconstrucción constituye una sensibilidad adicional sobre exactamente los mismos partidos.

Admito todos los amistosos con la misma política: duración estándar supuesta cuando falta verificación, sin excepción para el 0–0. Evalúo ese estrato por separado; no confundo sus etiquetas aproximadas con evidencia universal de duración a 90 minutos.

## Goles a 90 minutos

El conjunto estricto se define por el catálogo de partidos masculinos de Fjelstul, con identidad y fecha, independientemente de cuántos goles haya. Si la ficha confirma ausencia de prórroga, uso el marcador registrado de ese partido a 90 minutos para cualquier marcador, sin exigir filas de goles solo a los partidos con goles. Si hubo prórroga, reconstruyo mediante su corpus de eventos por periodo y aplico la misma reconciliación de integridad a ambos equipos. Las inconsistencias entre fuentes quedan marcadas y no reciben una etiqueta inventada.

El archivo martj42 de goleadores es un listado de goles, no un catálogo independiente de partidos con cobertura completa: la ausencia de filas no distingue 0–0 de falta de cobertura. Por eso su presencia no define pertenencia al conjunto estricto de goles. Sus eventos sí pueden ayudar a reconstruir una etiqueta del conjunto 1X2, cuya pertenencia ya está fijada sin usar el resultado.

Comparo el conjunto estricto con dos sensibilidades: (a) ese catálogo más **todos** los amistosos, con duración supuesta y faltantes de verificación declarados; (b) **todo** el historial, con la misma suposición para cada partido sin duración verificada. No selecciono una política de goles por observar una tasa de empates que parezca conveniente. Sus ventanas se calculan causalmente bajo cada política; repito las ablaciones de forma con cada una.

## Calibración y referencias

Mantengo la rejilla acotada de parámetros Elo ya publicada, incluyendo los desplazamientos de inicialización como comprobación de invariancia. Uso los bloques 2016–2017, 2018–2019, 2020–2021 y 2022, con ajuste logístico desde 2000 hasta el inicio de cada bloque. El estado Elo usa todo el historial anterior a cada partido y nunca actualiza con resultados de la misma fecha antes de calcular sus variables.

Selecciono parámetros por log loss acumulada de **no amistosos** en esos bloques. Desempato por Brier y por el orden declarado de la rejilla; una puntuación inicial común conserva 1500 como convención. Ajusto la logística con todos los partidos 1X2 previos al bloque, incluidos amistosos de duración supuesta. Informo no amistosos, amistosos y total por separado.

«Solo Elo» utiliza (diferencia de Elo + ventaja de sede configurada × signo de sede) / 400. «Elo + sede» utiliza esa misma diferencia efectiva y un coeficiente de sede adicional aprendido exclusivamente en el entrenamiento. Por tanto, ninguna ablación recibe ventaja de sede que falte a su referencia. Comparo todos los grupos contra **Elo + sede**, con regularización C=1 fija y reconciliación simétrica.

Repito los grupos de forma reciente, descanso, contexto de competición (sin duplicar la sede), altitud, puesto FIFA, puesto y puntos FIFA y ponderación de cobertura. Mercado sigue excluido por no disponer de pertenencia fechada antes de 2023. La ponderación por confederaciones actuales es solo una sensibilidad administrativa: no certifica afiliación histórica y no se habilita para producción.

Un grupo pasa el criterio si el límite superior del intervalo pareado del cambio de log loss de **no amistosos** es menor que cero, no empeora Brier de ese estrato y mejora log loss en al menos tres de los cuatro bloques. Compruebo también el conjunto combinado de grupos que pasen. Informo métricas e intervalos absolutos y pareados para los tres estratos. Uso 400 remuestreos de trimestres completos y semilla 20261012; no simulo torneos. La selección comparte bloques de validación y sigue necesitando evaluación independiente.

## Comprobación estándar de sesgo

Antes de interpretar mejoras, calculo participación de 0–0 y empates en el historial y en cada conjunto, para el periodo anterior a 2023 y para cada bloque. Informo tanto el marcador registrado como la etiqueta utilizada: cambiar una etiqueta reconstruida no equivale a seleccionar un partido. Comparo cada conjunto con el historial completo y con su mismo dominio de competiciones. El conjunto de todos los registros iguala por definición las proporciones **registradas** del historial; no fuerzo las tasas de un catálogo de Mundiales a parecerse a amistosos o eliminatorias.

Guardo fecha real, hash de este protocolo, fuentes, excepciones, sensibilidades, selección y pruebas en data_audit.json. Los resultados sesgados quedan como diagnóstico histórico, no como evidencia vigente de mejora. Espero aprobación antes de la Fase 3.
