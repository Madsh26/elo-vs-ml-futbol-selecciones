# Resultados del pipeline local

Modelo de marcadores elegido en validación 2022: **xgboost_poisson**.

432 filas de probabilidades: 72 encuentros y seis modelos. Cuatro modelos exportan distribuciones de marcadores; dos clasificadores se comparan por separado. Las perspectivas por equipo corresponden a los cuatro modelos de marcadores.

## Protocolo

Entrenamiento 2010-2017; parada anticipada 2018-2019; dependencia del híbrido 2020-2021; selección de marcadores/calibración 2022; prueba 2023 hasta el corte. Variables actualizadas solo con partidos de fechas anteriores. Tras archivar el backtest, modelos de despliegue ajustados con todo el historial elegible y calibración mediante predicciones fuera de tiempo.

El backtest es secuencial, no una evaluación con todas las variables congeladas antes de un torneo. Los modelos finales de despliegue no tienen nuevas métricas de prueba independientes.

## Datos

Corte exclusivo: 2026-06-10. Último resultado local con goles: 2026-06-04. Registros de 2026 programados: 72; con resultados: 0.

Política de duración: Friendlies assumed 90 minutes; men World Cup regulation scores reconstructed from local goal events; other competitions excluded.

Se usa información local de participantes del calendario sin certificar su disponibilidad en la fecha histórica. No es una predicción publicada antes del Mundial.

## Evaluación temporal

```text
                  model  log_loss  brier_multiclass_unscaled  score_nll
               logistic  0.917102                   0.546287        NaN
                poisson  0.955928                   0.570524   2.951600
            dixon_coles  0.954656                   0.570523   2.948881
            xgboost_1x2  0.927646                   0.550600        NaN
xgboost_1x2_temperature  0.923276                   0.549691        NaN
        xgboost_poisson  0.924403                   0.549558   2.868777
    xgboost_dixon_coles  0.923475                   0.549261   2.867254
```

Las tasas de goles no son un modelo de xG basado en tiros. La importancia de variables no demuestra causalidad. La temperatura del clasificador no altera las matrices de marcadores de otros modelos.

Ejecución: 33.6 segundos, 2 hilos para XGBoost, cero simulaciones de torneos. Este tiempo corresponde a esta máquina y ejecución.
