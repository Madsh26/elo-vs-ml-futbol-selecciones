# Definición del historial y del resultado

Construyo un estudio retrospectivo y separo pertenencia a un conjunto, reconstrucción de la etiqueta e integridad de las fuentes. El corte deportivo final es 2026-06-10; la selección actual solo admite resultados anteriores a 2023.

## Pertenencia independiente del resultado

No uso marcador, empate, goles o ganador para definir cobertura. El conjunto 1X2 contiene todo registro válido del dominio declarado. Una tanda permanece en el historial: no transforma automáticamente un marcador en empate. Cuando puedo reconstruir 90 minutos, uso ese resultado; cuando no puedo, conservo el final registrado como aproximación y marco la incertidumbre.

El catálogo de Fjelstul identifica partidos independientemente de la presencia de goles. La ficha sin prórroga certifica el resultado a 90 minutos para cualquier marcador. La reconstrucción con prórroga utiliza periodos del corpus y reconciliación de cantidades. Distingo conflictos de integridad de ausencia de cruce de identidad/fecha; ambas listas permanecen visibles.

No considero que la ausencia de filas en goalscorers demuestre cobertura de un 0–0. Martj42 lista goles y codifica descuento como 90; sus eventos completos pueden ayudar a reconstruir una etiqueta 1X2, pero no definen admisión al conjunto estricto de goles. StatsBomb distingue descuento y prórroga por periodo y queda reservado para validación.

## Sensibilidades

El conjunto estricto de goles usa el catálogo independiente. Las alternativas agregan todos los amistosos o todos los registros con duración supuesta, sin excepciones por marcador, tanda o ausencia de goles. Cada ventana de ataque y defensa utiliza solo partidos previos admitidos bajo su política y conserva cobertura. Un promedio con pocos partidos tiene un prior fijo equivalente a tres encuentros de 1,3 goles; no lo presento como goles observados.

Los indicadores de verificación del partido actual no son predictores: se utilizan para auditoría de etiquetas. Las variables de forma provienen de resultados previos. Las suposiciones de duración se informan por separado y no se convierten en prueba de duración física del partido.

## Diagnóstico estándar

Comparo 0–0 y empates registrados y de la etiqueta, por conjunto y bloque. El conjunto completo 1X2 tiene las mismas proporciones registradas que el historial por construcción. Una diferencia en la etiqueta reconstruida puede deberse a prórroga y no a selección. Comparo además dominios equivalentes: amistosos con amistosos, no amistosos con no amistosos y catálogo de Mundiales con Mundiales. No igualo tasas de dominios distintos artificialmente.

## Identidad y tiempo

Aplico el filtro de fecha antes de interpretar goles. Los alias históricos respetan intervalos; Czechoslovakia y Czech Republic permanecen distintas. Las sedes se normalizan como territorios, no como sucesiones de federaciones. Los partidos del mismo día comparten el estado anterior a ese día.

Mercado no tiene pertenencia fechada antes de 2023 y queda excluido. El ranking semestral se considera disponible el día siguiente al fin del semestre y caduca a 90 días; no hay extrapolación a 2026. La altitud de sede es estática; las ciudades ambiguas y viajes no verificables permanecen faltantes.

## Registro y sellado

El protocolo de conjuntos se fija antes de ejecutar las métricas. Guardo decisiones, fechas y hashes en data_audit.json. La selección actual no carga resultados reservados ni entrena XGBoost. El congelado del modelo y predicciones y la carga de resultados oficiales siguen pendientes. No presento el estudio como una publicación anterior al torneo.
