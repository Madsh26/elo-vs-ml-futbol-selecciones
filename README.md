# ¿Le gana el machine learning a Elo? Evaluación retrospectiva de 8 modelos en fútbol de selecciones y el Mundial 2026

**3.624 partidos · protocolo sellado con hashes · 72 partidos del Mundial**

**Pregunta:** ¿mejoran el aprendizaje automático y los modelos de goles a un Elo simple al predecir partidos de selecciones?

**Resultado:** en no amistosos, la logística con Elo y forma reduce el log loss en **0.0089** (≈1% relativo; IC [-0.0147; -0.0034]) y el acierto es prácticamente igual (61.53% frente a 61.56%). XGBoost y los modelos de goles no demuestran una mejora robusta en esta evaluación semiconfirmatoria. La ventaja tampoco queda demostrada entre selecciones fuertes ni en los grupos del Mundial. [Fuente: métricas ejecutadas](reports/final_evaluation/semiconfirmatory_metrics.csv).

![Comparación probabilística](assets/model_comparison.png)

Estudio retrospectivo, construido con el Mundial ya jugado. La evidencia 2023–corte es semiconfirmatoria por exposición previa al periodo. [Explorar los partidos](reports/final_evaluation/football_report.html) · [Resultados](reports/final_evaluation/RESULTADOS.md) · [Explicación sencilla](docs/COMO_ENTENDER_EL_MODELO.md).

## Datos

Uso **49,469 partidos** (1872-11-30–2026-06-09) para el estado Elo y la forma; **21,781** para el ajuste, **6,376** para selección temporal y **3,624** para evaluación semiconfirmatoria. El informe presenta **72 partidos de grupos** y **48 selecciones**. Estas cantidades se generan leyendo `reports/final_evaluation/data_inventory.json`.

| Fuente | Contenido | Uso en el estudio | Licencia documentada | Enlace de origen | Incluida en Git |
|---|---|---|---|---|---|
| martj42 snapshot | Resultados, goles, tandas y nombres históricos | estado Elo; ajuste; validación 2026 tras sellado | CC0-1.0 | no verificada | Sí |
| Fjelstul | Catálogo y periodos de Mundiales | validación de duración; reconstrucción histórica a 90 minutos | CC-BY-SA-4.0 | [Origen](https://github.com/jfjelstul/worldcup) | Sí |
| Ranking FIFA semestral contenedor | Posición y puntos por año/semestre | ablación; excluida | no verificada | no verificada | No |
| Transfermarkt DuckDB | Jugadores, valoraciones y partidos | games: validación 2026; mercado y national_teams: excluidos como variables | CC0 declarada para el dataset; vínculo del DuckDB exacto no verificado | [Origen](https://github.com/dcaribou/transfermarkt-datasets) | No |
| GeoNames cities15000 | Ciudades y altitud | ablación de altitud estática; excluida del modelo elegido | no verificada | no verificada | No |
| StatsBomb | Eventos y metadatos de partidos | validación opcional; no usada para ajustar ni elegir modelos | StatsBomb Public Data User Agreement; no redistribución | [Origen](https://github.com/statsbomb/open-data) | No |
| Openfootball | Resultados de Mundial, separado de Fjelstul | validación 2026 tras sellado | CC0-1.0 | no verificada | Sí |
| Partidos resueltos | Calendario, equipos, grupos y sedes | metadatos de pronóstico; no entrenamiento | no verificada | no verificada | Sí (términos de competencia pendientes) |

Conservo el snapshot exacto por SHA256: el contenido actual de una fuente que se actualiza, como martj42, puede ser distinto. Las fechas de obtención no están verificadas. El [manifiesto](data/MANIFEST.csv), la [guía de fuentes](data/README.md) y el [diccionario de variables](docs/DATOS_Y_DICCIONARIO.md) detallan archivos, cantidades, cobertura, hashes y condiciones originales.

### Datos que no uso y por qué

- Valor de mercado: la cobertura histórica de las plantillas no permite evaluarlo en los bloques de selección. El valor y club actuales no son variables históricas válidas.
- Ranking FIFA 2026: no hay histórico vigente disponible; no lo extrapolo. La foto repetida está excluida. El ranking semestral con rezago fue una ablación y no forma parte del modelo elegido.
- Altitud GeoNames: evaluada como variable secundaria, no admitida en el diseño final.
- StatsBomb: validación opcional, no entrenamiento ni evidencia adicional ejecutada.
- `national_teams` de Transfermarkt: foto sin fecha histórica; no es ranking por partido.
- Entrega DataCamp: histórico de la competencia, excluido como modelo y línea base.

La logística utiliza las seis variables documentadas en el diccionario, calculadas únicamente con el pasado. Los datos completos posteriores al corte se conservan como fuente; sus resultados no entran en el ajuste. Las licencias de datos son independientes de MIT para el código propio.

## Método y lectura de resultados

La referencia Solo Elo incluye sede fija. Comparo frecuencias, logística con forma, ordinal, XGBoost 1X2, Poisson, Dixon-Coles y XGBoost Poisson. No reajusto modelos desde 2022: actualizo solo el estado Elo y forma. **Logística estima 1X2; Poisson estima marcadores y su propio 1X2. No son el mismo producto.**

En no amistosos, log loss es **0.8478** para logística y **0.8567** para Elo. La diferencia tiene IC trimestral **[-0.0147; -0.0034]**. Remuestreo 2.000 veces bloques trimestrales completos; el bootstrap mensual es sensibilidad. Reporto Brier, RPS, acierto, fiabilidad por clase, NLL de marcador y resultados por población.

Entre equipos con ambos Elo >1700 (674 partidos) y entre las 48 selecciones del Mundial (406), los intervalos incluyen cero. La mejora de la muestra amplia no garantiza una ventaja en el tipo de encuentro más exigente.

Para inferencia exijo ≥200 partidos y ≥30 eventos por clase. Los 72 grupos y las eliminatorias son descriptivos. Las eliminatorias usan participantes conocidos retrospectivamente y no representan simulación ni pronósticos sellados antes del torneo.

## Limitaciones y lectura crítica

- **Efecto pequeño y posible deriva.** La diferencia de log loss frente a Elo pasa por 2023: -0.0151, 2024: -0.0074, 2025: -0.0021. Mantengo coeficientes sin reajuste; la ventaja disminuye en esos tres años. Es una señal exploratoria de posible deriva, no una causa demostrada. [CSV por periodo](reports/final_evaluation/semiconfirmatory_subperiods.csv).
- **Calibración del empate.** La pendiente diagnóstica es 1.40 en no amistosos; el ideal es 1. Entre los diez mayores errores de los grupos, 3 son 0–0. El mayor es España–Cabo Verde, donde el favorito tenía 87.8%. No ajusto el modelo con este diagnóstico. [Calibración](reports/final_evaluation/semiconfirmatory_calibration.csv) · [Errores](reports/final_evaluation/worldcup_largest_errors.csv).
- **Elo solo conoce resultados**, no plantillas, lesiones ni valor de mercado. En Colombia–Portugal, el estado con corte exclusivo 2026-06-10 es Elo 2060 frente a 2023; la logística sellada el 2026-10-12 asigna 40.7/29.0/30.3% (Colombia/empate/Portugal). [Estado previo sellado](reports/final_evaluation/features_72_frozen.csv) · [Predicción congelada](reports/final_evaluation/group_forecasts_logistic.csv). Como contraste de plausibilidad exploratorio, [Australia Football](https://www.australiafootball.com/news/2026-06-26-colombia-vs-portugal-wc2026-pre/) publicó el 2026-06-26 una cuota 1.9 para Portugal, equivalente a 52.6% implícito bruto, sin descontar el margen. Esa información es posterior al corte y no es un benchmark evaluado: no la mezclo con los resultados del protocolo ni la presento como consenso verificado de todo el mercado. [Registro de fuentes y fechas](docs/market_plausibility_sources.json).
- **Hipótesis no probada:** el escaso anclaje entre confederaciones podría hacer que Elo sobrevalore algunas selecciones de CONMEBOL. No atribuyo causalidad ni generalizo desde un partido.
- **Sin referencia externa de mercado en la evaluación.** Queda como trabajo futuro comparar cuotas, plantillas y valoraciones con fecha, respetando el mismo corte de información.

## Reproducibilidad y documentación técnica

```powershell
python tools/verify_final_evaluation.py
```

La verificación comprueba modelos, protocolo y predicciones frente a sus hashes y commits; el CI informa pruebas y omisiones por datos locales. El historial y la presentación de los resultados finales se reconstruyen con los ZIP incluidos y `resolved_fixtures.csv`, utilizando las predicciones y métricas congeladas. Las ablaciones y la corroboración con Transfermarkt requieren las fuentes excluidas indicadas en `data/README.md`. Uso dos hilos por defecto y no simulo cuadros de torneo.

- [Protocolo aprobado y umbral](reports/final_evaluation/PROTOCOLO_APROBADO.md).
- [Decisiones y límites](docs/DECISIONES_DE_DISEÑO.md), incluido el periodo semiconfirmatorio y la incidencia de secuencia registrada.
- [Datos, diccionario y cobertura](docs/DATOS_Y_DICCIONARIO.md).
- [Índice de auditorías](data_audit.json); cada protocolo y sello identifica el archivo exacto cubierto por SHA256.

models-selected conserva la selección anterior a 2023; phase4-protocol y phase4-protocol-approved son protocolos distintos; phase4-predictions-frozen identifica las predicciones anteriores a cargar resultados oficiales. Los modelos y métricas históricos de DataCamp están excluidos de comparaciones. El trabajo se construyó con el Mundial ya jugado y no se presenta como pronóstico publicado antes del torneo.

Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.

## Publicación en GitHub

Nombre sugerido: `elo-vs-ml-futbol-selecciones`. Topics: `sports-analytics`, `elo-rating`, `xgboost`, `probabilistic-forecasting`, `reproducible-research`.
