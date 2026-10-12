# International Football Probabilities

Construyo un estudio retrospectivo de probabilidades de fútbol para mi portafolio: victoria, empate, derrota y distribución de marcadores a 90 minutos. El torneo ya estaba jugado al construir el estudio; no lo presento como un pronóstico publicado previamente.

El corte deportivo final es exclusivo, **2026-06-10**. Selecciono y congelo modelos usando únicamente resultados anteriores a **2023-01-01**. Mantengo 2023–corte y los resultados oficiales del Mundial reservados para la evaluación posterior.

## Diseño

Los conjuntos de evaluación se definen sin depender del resultado. Admito todos los registros válidos para 1X2 y goles, reconstruyendo 90 minutos donde hay evidencia y usando el final registrado como aproximación declarada donde falta. No convierto una tanda automáticamente en empate. El catálogo estricto de Mundiales sirve como validación de esta aproximación, con sensibilidades sin partidos marcados y solo no amistosos.

Elo utiliza todas las competiciones, actualización por fecha, pesos por competición, margen de goles y ventaja real de sede. Comparo 32 configuraciones conjuntas y elijo por log loss de no amistosos con una regla pareada de un error estándar. La forma reciente procede solo de partidos anteriores. La logística con forma debe cumplir el criterio frente a Elo en esta búsqueda; no doy por válida una combinación de contexto por una evaluación sesgada.

Comparo frecuencias, Solo Elo con sede fija, logística con forma, regresión ordinal, XGBoost 1X2, Poisson, Dixon-Coles con covariables y XGBoost Poisson. Los modelos de goles producen el marcador y el 1X2 desde la misma distribución. Pruebo simetría al intercambiar equipos con tolerancia 1e-9.

Elijo **Logística con Elo y forma** para 1X2 y **Poisson independiente** para marcadores. Esta es una selección anterior a 2023 que necesita confirmación independiente. [RESULTADOS.md](RESULTADOS.md) explica métricas, intervalos, sensibilidades y límites.

## Validación y reproducción

Uso bloques 2016–2017, 2018–2019, 2020–2021 y 2022, con entrenamiento anterior a cada bloque desde 2000. Reporto total, amistosos, no amistosos y Mundiales, log loss, Brier multiclase sin dividir, acierto, ECE por clase, empates previstos/reales y NLL de marcador. Remuestreo trimestres completos para los intervalos pareados. Un modelo complejo debe superar la referencia bajo el criterio escrito previamente; el periodo reservado sigue sin abrir.

```powershell
python select_models.py
python tools/verify_models_selected.py
```

No descargo datos ni simulo torneos. Uso dos hilos por defecto. Si el congelado ya existe, select_models.py verifica sus hashes sin sustituirlo. Para reproducir la selección desde cero necesito una copia de trabajo sin el directorio de congelado, las fuentes locales con los SHA256 registrados y la preparación previa. Los CSV grandes están excluidos de Git; si falta el historial preparado, lo reconstruyo con el corte anterior a 2023 y compruebo su hash. El protocolo queda guardado antes de ejecutar métricas. Los comandos históricos fix_selection_bias.py corresponden a la etiqueta selection-bias-fixed y no generan el informe vigente.

## Fuentes y límites

Uso archivos locales de martj42, Fjelstul, ranking FIFA semestral, GeoNames, Transfermarkt, StatsBomb, Openfootball y fixtures suministrados. Mantengo las fuentes separadas y en data/raw/. El ranking repetido es una fotografía excluida; el ranking semestral solo es una ablación con rezago conservador y caducidad de 90 días. No extrapolo ranking a 2026. Valor de mercado queda fuera por falta de pertenencia a selecciones fechada antes de 2023; no uso valor/club/nacionalidad actuales como históricos. StatsBomb queda para validación opcional. Openfootball y resultados de 2026 permanecen reservados.

## Trazabilidad

[data_audit.json](data_audit.json), [protocolo previo](reports/models_selected/protocol.json), [congelado](reports/models_selected/freeze_manifest.json) y [decisiones de diseño](docs/DECISIONES_DE_DISEÑO.md) registran fechas, hashes y reglas. Las etiquetas data-prepared, selection-bias-fixed y models-selected identifican preparación, definición de conjuntos y modelos congelados. Conservo los informes históricos como diagnóstico; la narrativa vigente está en RESULTADOS.md y reports/models_selected/.

Cada fuente conserva sus condiciones originales. El código nuevo tiene licencia MIT.
