# Decisiones de diseño

Construyo un estudio retrospectivo con el torneo ya jugado. Distingo el corte deportivo exclusivo 2026-06-10 de las fechas reales de construcción, selección, congelado y carga de resultados. No lo presento como pronóstico publicado antes del Mundial.

## Conjuntos sin selección por marcador

Los conjuntos de evaluación se definen sin depender del resultado. Esta es una comprobación estándar: reviso 0–0 y empates por población, dominio y bloque. Una tanda no prueba empate a 90 minutos; las filas idénticas de goleadores no se eliminan automáticamente. Mantengo entidades históricas distintas, incluido Czechoslovakia respecto a Czech Republic.

Admito todo el historial válido para goles y 1X2 bajo duración supuesta donde falta evidencia. Reconstruyo 90 minutos cuando se puede verificar. Marco tandas y prórrogas probadas. El catálogo independiente Fjelstul de Mundiales valida la aproximación; no es el entrenamiento principal. Repito con exclusión de marcados y con entrenamiento solo no amistoso. La exclusión también retira esos partidos de la historia de forma, pero Elo conserva todo el historial. No uso la tasa de empates para decidir admisiones.

## Selección temporal y simplicidad

Resultados desde 2023 están reservados. Calculo variables antes de actualizar todos los resultados de una fecha. Elo tiene inicialización 1500, plazo de inactividad 730 días y una búsqueda conjunta de 32 combinaciones de sede, regresión, pesos K y margen de goles. La regresión 0.1 de la referencia era un parámetro fijado, no una elección de datos de la búsqueda aislada.

El protocolo escrito previamente está en reports/models_selected/protocol.json. Selecciono por log loss de no amistosos en los cuatro bloques. Dentro de un error estándar pareado del mínimo prefiero, por orden, ausencia de regresión, pesos de referencia, gamma menor y ventaja de sede menor. Para modelos y variables exijo IC superior de diferencia de log loss <0, Brier sin empeorar y mejora en tres bloques; entre candidatos admitidos cercanos uso el orden de complejidad escrito. Los intervalos usan trimestres completos, 400 réplicas, semilla fija. Estos bloques de selección necesitan confirmación independiente.

## Variables y modelos

La forma con duración supuesta está admitida explícitamente y se verifica al excluir marcados. No incorporo automáticamente grupos secundarios; guardo ablaciones de sede adicional, descanso, competición, altitud y ranking. El ranking está disponible después del semestre y caduca a 90 días, sin extrapolación a 2026. Mercado queda fuera: no tengo pertenencia fechada a selecciones anterior a 2023. No uso tablas actuales players/national_teams como históricos. GeoNames aporta solo altitud estática identificable; no invento viajes ni altitud de entrenamiento. No pondero por afiliaciones históricas supuestas a partir de confederaciones actuales.

Todos los clasificadores reconcilian ambos órdenes. Los modelos de goles comparten una regresión orientada de tasas y generan victoria/empate/derrota desde su distribución conjunta. Dixon-Coles usa covariables y corrección de marcadores bajos; no efectos libres por selección. Tasas y corrección tienen límites explícitos de validez. No calibro por separado el 1X2 del marcador: reporto ECE nativo por clase y fiabilidad. XGBoost tiene configuración pequeña fija, sin parada temprana usando el bloque evaluado.

## Congelado

Congelo los modelos con entrenamiento anterior a 2023 en 2026-10-12T17:07:05.615286+00:00, con hashes en freeze_manifest.json. La etiqueta models-selected precede a abrir 2023–corte. El congelado de predicciones de los 72 partidos y la carga de resultados oficiales corresponden a fases posteriores; sus fechas no se inventan. El modelo guardado original permanece intacto. Mantengo archivos fuente en data/raw/ y reportes históricos como diagnósticos separados.
