# Resultados y estado del estudio

Este es un estudio retrospectivo, construido con el Mundial 2026 ya jugado. El corte deportivo exclusivo es 2026-06-10. Distingo tres niveles de evidencia: selección anterior a 2023, evaluación semiconfirmatoria 2023–corte y descripción posterior de los 72 partidos. Los dos últimos niveles siguen pendientes de aprobación y ejecución.

## Evidencia de selección anterior a 2023

En los 4.473 no amistosos de los cuatro bloques elegí logística con Elo y forma. Elo es la referencia, no el ganador de todos los candidatos. Poisson es el producto descriptivo de marcadores; ningún modelo de goles cumplió todo el criterio frente a Elo.

| Modelo | Log loss | Brier |
| --- | --- | --- |
| Frecuencias | 1.071228 | 0.649566 |
| Solo Elo con sede fija | 0.858306 | 0.503416 |
| Logística con Elo y forma | 0.851631 | 0.498981 |
| Regresión ordinal | 0.857636 | 0.502972 |
| XGBoost 1X2 | 0.855941 | 0.501241 |
| Poisson independiente | 0.854577 | 0.501040 |
| Dixon-Coles | 0.853436 | 0.500466 |
| XGBoost Poisson | 0.857185 | 0.501711 |

El resultado completo y sus intervalos están en [el informe congelado](reports/models_selected/RESULTADOS.md). Lo conservo intacto como evidencia de selección. Sus expresiones de periodo «cerrado» o «reservado» describen la separación usada en esa selección, no la virginidad de 2023–corte: el proyecto DataCamp ya había puntuado 846 partidos de ese periodo. Ese trabajo es histórico y superado, no un comparador.

## Dos productos distintos

La logística calcula victoria/empate/derrota directamente. Poisson estima goles y genera una matriz de marcadores, de la cual derivo su propio 1X2. Sus probabilidades no coinciden y no aplico una reconciliación.

En los 6376 partidos anteriores a 2023, la diferencia absoluta media entre sus tres probabilidades es **2.5240 puntos porcentuales**. Por clase: victoria 2.7296, empate 1.9608, derrota 2.8817. Esta es evidencia de selección, no una evaluación desde 2023. El cálculo está en [pre2023_product_discrepancy.json](reports/final_evaluation/pre2023_product_discrepancy.json).

## Comprobación del sesgo archivado

Uso las etiquetas originales del CSV de descomposición; no etiquetas faltantes del generador histórico. Esta tabla documenta el artefacto, no una mejora vigente.

| Estrato | Partidos | Participación | Log loss Elo | Log loss combinación sesgada | Mejora media | Contribución agregada |
| --- | --- | --- | --- | --- | --- | --- |
| Amistosos | 197 | 0.062859 | 1.033826 | 0.003750 | 1.030076 | 0.064749 |
| No amistosos | 2937 | 0.937141 | 0.892938 | 0.857078 | 0.035861 | 0.033606 |

## Evaluación semiconfirmatoria pendiente

El protocolo [PROTOCOLO.md](reports/final_evaluation/PROTOCOLO.md) queda sellado antes de ejecutar métricas y requiere aprobación explícita. Compararé principalmente logística contra Solo Elo en no amistosos; reportaré además partidos con ambos Elo previos >1700 y partidos de las 48 selecciones entre sí o contra cualquier rival.

No reajusto modelos desde 2022 ni cambio umbrales a partir de esta evaluación. La sede tiene ventaja fija 100 y la **tasa de regresión por inactividad es 0**: el plazo 730 días es inerte. La adopción anterior solo se confirma o no se confirma; no selecciono un sustituto con estos resultados.

Después de la aprobación actualizaré solo el estado Elo y forma hasta el corte para generar y congelar los 72 pronósticos. Esta actualización es necesaria antes de sellar las predicciones y no modifica los modelos. No usaré resultados del Mundial. Los commits de protocolo, predicciones congeladas y evaluación serán distintos; usaré sus fechas y los sellos de hash, no las fechas de modificación de archivos.

El informe definitivo de Fase 4 se publicará en reports/final_evaluation/RESULTADOS.md cuando se ejecute. No existe todavía una cifra de rendimiento para ese periodo o el Mundial en esta fase.
