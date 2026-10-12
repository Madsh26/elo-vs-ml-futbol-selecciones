# Probabilidades de fútbol internacional

Evaluación retrospectiva de Elo, aprendizaje automático y modelos de goles.

Construyo un estudio de victoria, empate, derrota y marcadores a 90 minutos. El Mundial 2026 ya estaba jugado al construirlo; no lo presento como un pronóstico publicado previamente. El corte deportivo es exclusivo, **2026-06-10**.

## Estado de la evidencia

Seleccioné los modelos con resultados anteriores a 2023: **logística con Elo y forma** para 1X2 y **Poisson** para marcadores. Son modelos distintos: el 1X2 de Poisson procede de su propia matriz de marcadores y no coincide con el 1X2 de la logística. No mezclo sus probabilidades ni las reconcilio artificialmente.

El periodo 2023–corte es **semiconfirmatorio, no virgen**: la entrega histórica para DataCamp ya puntuó 846 partidos de 2023-01-08 a 2026-06-04. Sus modelos y métricas están excluidos de todas las líneas base y comparaciones del estudio actual. Que esos resultados no hayan intervenido en esta selección no elimina la exposición previa.

La Fase 4 está en la puerta de aprobación. Ya escribí y sellé su protocolo; todavía no calculo métricas desde 2023 ni genero las predicciones finales de los 72 encuentros. Los resultados oficiales del Mundial se cargarán después de congelar las predicciones y su commit.

## Diseño

Los conjuntos se definen sin depender del marcador. Admito todos los registros válidos, reconstruyendo 90 minutos cuando hay evidencia y usando el marcador final como aproximación declarada cuando falta. Una tanda no demuestra empate a 90 minutos. Las marcas de tanda y prórroga permiten análisis de sensibilidad; el catálogo independiente de Mundiales permite comprobar la duración.

Elo utiliza todas las competiciones, pesos por competición, margen de goles y sede real. Los parámetros congelados son sede 100, gamma 1, K de referencia y tasa de regresión 0; con tasa cero, el plazo de inactividad de 730 días no tiene efecto. Las variables de una fecha se calculan antes de actualizar sus resultados. La forma reciente usa únicamente el pasado.

Entrené y comparé frecuencias, Solo Elo, logística con forma, ordinal, XGBoost 1X2, Poisson, Dixon-Coles y XGBoost Poisson. XGBoost permanece como comparador: no demostró una mejora robusta en los bloques de selección. Descanso, competición, altitud y ranking FIFA no cumplieron el criterio de admisión; mercado no tiene pertenencia histórica fechada suficiente. No extrapolo ranking a 2026 ni uso valores actuales de jugadores.

## Documentación y reproducción

- [Resultados y estado actual](RESULTADOS.md): entrada al informe, sin duplicar el congelado.
- [Protocolo de evaluación](reports/final_evaluation/PROTOCOLO.md): población, métricas, incertidumbre y puerta de aprobación.
- [Decisiones de diseño](docs/DECISIONES_DE_DISEÑO.md).
- [Cómo entiendo los modelos](docs/COMO_ENTENDER_EL_MODELO.md): explicación sin conocimientos previos.
- [Índice de auditorías](data_audit.json): enlaces y hashes de los documentos de autoridad.

```powershell
python tools/verify_final_evaluation.py
```

Este comando verifica el congelado y ejecuta pruebas que no evalúan resultados desde 2023. Solo escribe la verificación en reports/final_evaluation/. El CI informa pruebas ejecutadas y omitidas por falta de datos o por exclusión del histórico. Para verificar los commits y etiquetas necesito el historial de Git y la etiqueta models-selected, no solo una copia de los archivos.

Mantengo intactos reports/models_selected/ y sus cinco archivos de código protegidos. No ejecuto los antiguos scripts que regeneran esos informes. La reproducción de selección desde cero corresponde a una copia de trabajo independiente, con las fuentes locales y sus hashes.

Uso archivos locales, sin descargas ni scraping. Los datos grandes permanecen fuera de Git. Conservo metadatos de fixture del archivo histórico como fuente suministrada; no utilizo sus modelos ni sus resultados de evaluación. Cada fuente conserva sus condiciones y el código nuevo tiene licencia MIT.
