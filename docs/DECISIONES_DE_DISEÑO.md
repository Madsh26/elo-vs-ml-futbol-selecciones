# Decisiones de diseño

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
