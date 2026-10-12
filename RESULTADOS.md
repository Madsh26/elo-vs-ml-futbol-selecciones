# Resultados del estudio

La logística con Elo y forma confirma su aporte frente a Solo Elo en la evaluación semiconfirmatoria 2023–corte: log loss 0.847844 frente a 0.856713, diferencia -0.008869, IC trimestral [-0.014749; -0.003367], Brier mejora y cuatro subperiodos favorables. XGBoost no demuestra una mejora robusta.

En los 72 partidos de grupos, logística obtiene 0.897303 frente a 0.902773 de Elo; el intervalo de la diferencia incluye cero. Es una descripción de muestra pequeña, no una prueba de superioridad.

Logística y Poisson son productos distintos, sin reconciliación. La discrepancia media es 2.4748 puntos porcentuales en 2023–corte y 2.1903 en los grupos.

[Informe completo](reports/final_evaluation/RESULTADOS.md) · [Herramienta interactiva](reports/final_evaluation/football_report.html) · [Datos y diccionario](docs/DATOS_Y_DICCIONARIO.md) · [Protocolo aprobado](reports/final_evaluation/PROTOCOLO_APROBADO.md).

El estudio es retrospectivo y el periodo posterior a 2022 es semiconfirmatorio por exposición previa a DataCamp, excluido de comparaciones. Mantengo intacta la evidencia de selección en reports/models_selected/. La cronología también documenta el solapamiento operativo de 10.312 segundos entre carga oficial y cierre del remuestreo semiconfirmatorio; no modifica pronósticos, modelos o criterios.
