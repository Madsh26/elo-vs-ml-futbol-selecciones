# Decisiones de diseño

Construyo un estudio retrospectivo con el torneo ya jugado. Distingo el corte deportivo exclusivo 2026-06-10 de las fechas reales de construcción, selección, congelado y carga de resultados. No lo presento como pronóstico publicado antes del Mundial.

## Conjuntos sin selección por marcador

Los conjuntos de evaluación se definen sin depender del resultado. Esta es una comprobación estándar: reviso 0–0 y empates por población, dominio y bloque. Una tanda no prueba empate a 90 minutos; las filas idénticas de goleadores no se eliminan automáticamente. Mantengo entidades históricas distintas, incluido Czechoslovakia respecto a Czech Republic.

Admito todo el historial válido para goles y 1X2 bajo duración supuesta donde falta evidencia. Reconstruyo 90 minutos cuando se puede verificar. Marco tandas y prórrogas probadas. El catálogo independiente Fjelstul de Mundiales valida la aproximación; no es el entrenamiento principal. Repito con exclusión de marcados y con entrenamiento solo no amistoso. La exclusión también retira esos partidos de la historia de forma, pero Elo conserva todo el historial. No uso la tasa de empates para decidir admisiones.

## Selección temporal y simplicidad

El periodo desde 2023 es semiconfirmatorio: el pipeline histórico DataCamp ya puntuó 846 partidos de 2023-01-08 a 2026-06-04. No uso sus modelos ni métricas como comparadores. La selección vigente solo utilizó resultados anteriores a 2023; esta separación no convierte el periodo posterior en virgen. Calculo variables antes de actualizar todos los resultados de una fecha. Elo tiene inicialización 1500, tasa de regresión por inactividad 0 —el plazo de 730 días es inerte con esa tasa— y una búsqueda conjunta de 32 combinaciones de sede, regresión, pesos K y margen de goles. La regresión 0.1 de la referencia era un parámetro fijado, no una elección de datos de la búsqueda aislada.

El protocolo escrito previamente está en reports/models_selected/protocol.json. Selecciono por log loss de no amistosos en los cuatro bloques. Dentro de un error estándar pareado del mínimo prefiero, por orden, ausencia de regresión, pesos de referencia, gamma menor y ventaja de sede menor. Para modelos y variables exijo IC superior de diferencia de log loss <0, Brier sin empeorar y mejora en tres bloques; entre candidatos admitidos cercanos uso el orden de complejidad escrito. Los intervalos usan trimestres completos, 400 réplicas, semilla fija. Estos bloques de selección necesitan confirmación independiente.

## Variables y modelos

La forma con duración supuesta está admitida explícitamente y se verifica al excluir marcados. No incorporo automáticamente grupos secundarios; guardo ablaciones de sede adicional, descanso, competición, altitud y ranking. El ranking está disponible después del semestre y caduca a 90 días, sin extrapolación a 2026. Mercado queda fuera: no tengo pertenencia fechada a selecciones anterior a 2023. No uso tablas actuales players/national_teams como históricos. GeoNames aporta solo altitud estática identificable; no invento viajes ni altitud de entrenamiento. No pondero por afiliaciones históricas supuestas a partir de confederaciones actuales.

Todos los clasificadores reconcilian ambos órdenes. Los modelos de goles comparten una regresión orientada de tasas y generan victoria/empate/derrota desde su distribución conjunta. Dixon-Coles usa covariables y corrección de marcadores bajos; no efectos libres por selección. Tasas y corrección tienen límites explícitos de validez. No calibro por separado el 1X2 del marcador: reporto ECE nativo por clase y fiabilidad. XGBoost tiene configuración pequeña fija, sin parada temprana usando el bloque evaluado.

## Congelado

Congelo los modelos con entrenamiento anterior a 2023 en 2026-10-12T17:07:05.615286+00:00, con hashes en freeze_manifest.json. La etiqueta models-selected precede a abrir 2023–corte. El congelado de predicciones de los 72 partidos y la carga de resultados oficiales corresponden a fases posteriores; sus fechas no se inventan. El modelo guardado de DataCamp permanece histórico y superado, excluido de todas las comparaciones. Mantengo archivos fuente en data/raw/ y reportes históricos como diagnósticos separados.


## Evaluación semiconfirmatoria y puerta de aprobación

El protocolo nuevo vive en reports/final_evaluation/protocol.json, con sello y commit phase4-protocol. No abro métricas desde 2023 antes de aprobación explícita. Después actualizaré solo el estado causal para congelar 72 predicciones; los modelos no se reajustan. Los commits de protocolo, predicciones y evaluación son separados. Logística y Poisson son productos distintos, sin reconciliación; reporto su discrepancia media.

Los documentos de models_selected se conservan literalmente como registros congelados. Su lenguaje de periodo reservado se interpreta con la salvedad semiconfirmatoria de este registro vigente. README y RESULTADOS son entradas, y data_audit es un índice; no duplico el informe o auditoría congelados.


## Resultado de evaluación semiconfirmatoria

La selección se confirma bajo el protocolo aprobado: logística mejora log loss y Brier frente a Solo Elo en no amistosos, con cuatro subperiodos favorables. No cambio modelos ni criterios. XGBoost sigue siendo comparador porque su intervalo incluye cero. El estrato de equipos fuertes mantiene >1700 y el mínimo inferencial es 200 partidos/30 eventos por clase. Reporto clústeres reales, remuestreo mensual como sensibilidad y exposición previa de DataCamp.

Las 72 predicciones se sellaron y se comprometieron antes de la carga oficial. En grupos, el intervalo frente a Elo incluye cero; no declaro superioridad. Las eliminatorias se condicionan a participantes conocidos retrospectivamente y al estado anterior al corte. La logística y Poisson mantienen productos separados.

Registro el solapamiento de 10.312 segundos entre inicio de carga oficial y cierre del bootstrap semiconfirmatorio, sin cambios de modelos o entradas del cálculo. Conservo los tiempos reales y no afirmo una ejecución estrictamente secuencial de ese cierre. Los resultados y la incidencia están en reports/final_evaluation/RESULTADOS.md.
