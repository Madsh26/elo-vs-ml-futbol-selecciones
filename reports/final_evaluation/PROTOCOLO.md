# Protocolo de evaluación pendiente de aprobación

Construyo un estudio retrospectivo. Este protocolo se escribió en 2026-10-12T19:35:12.994232+00:00 y se selló en 2026-10-12T19:35:13.000277+00:00, con SHA256 `900b96918ab690af5cd3aa004c35372bec68b39fa3efc1cc30ba05469863dedf`. La autoridad de su registro será el commit de la etiqueta phase4-protocol y este sello, nunca el tiempo de modificación del archivo.

**No calculo métricas con resultados desde 2023 hasta recibir aprobación explícita.** No ejecuto la reproducción del pipeline DataCamp: queda fuera de todas las líneas base y comparaciones. Su exposición previa a 846 partidos convierte 2023–corte en evidencia semiconfirmatoria, no virgen.

## Población, referencia y criterio

Admito todos los registros válidos desde 2023-01-01 hasta antes de 2026-06-10, sin seleccionar por marcador. Uso 90 minutos verificados donde haya evidencia y el final registrado como aproximación donde falte. Marco tandas y prórrogas probadas; una tanda no se transforma automáticamente en empate.

La comparación principal es logística congelada con Elo y forma frente a Solo Elo congelado con sede fija, en no amistosos. Calculo la diferencia pareada de log loss. Confirmo la selección únicamente si el IC superior del 95% es <0, Brier no empeora y la diferencia mejora en al menos tres de estos cuatro periodos: 2023, 2024, 2025 y 2026-01-01 hasta antes de 2026-06-10. No ajusto ni selecciono otro modelo con esta prueba.

## Representatividad

Reporto total, amistosos, no amistosos y Mundiales —con N=0 cuando no existan—. Además:

- Ambos equipos con Elo previo **estrictamente >1700**, sin sumar la ventaja de sede. Fijo el umbral antes de observar esta evaluación.
- Partidos entre dos de las 48 selecciones del fixture de 2026.
- Partidos de al menos una de esas 48 selecciones contra cualquier rival.

Estos estratos se solapan y son secundarios. No cambio el umbral ni la lista de selecciones a partir de los resultados. El umbral absoluto depende de la escala Elo congelada y no define por sí mismo calidad universal.

## Métricas e incertidumbre

Reporto log loss, Brier multiclase sumado, RPS —orden derrota/empate/victoria, suma acumulada dividida por dos—, acierto, tasas de empate reales y previstas, y NLL conjunta de marcador solo en los modelos de goles. Los clasificadores 1X2 no tienen una NLL de marcador inventada.

Uso tablas de fiabilidad con diez intervalos fijos y recuentos, más pendiente e intercepto de calibración por clase. El ECE de diez intervalos es complementario. Ajustar la recta diagnóstica no recalibra las predicciones. Un estrato sin clases suficientes o sin ajuste fiable se informa como no estimable.

Obtengo IC del 95% con **2.000 réplicas de trimestres completos**, semilla 20261012, remuestreo pareado y medias ponderadas por número de partidos. No aplico corrección por comparaciones múltiples: las comparaciones secundarias y los estratos son descriptivos. Informo deriva por cada subperiodo porque los coeficientes siguen entrenados solo hasta 2022.

## Sensibilidades y productos

Evalúo por separado sin tandas/prórrogas marcadas, solo no amistosos y duración estrictamente verificada cuando exista muestra. No reentreno ni cambio la historia de forma del modelo congelado para estas sensibilidades.

Muestro separadamente el 1X2 de la logística, el 1X2 de Poisson y la matriz de marcadores Poisson. No aplico reconciliación. Reporto la diferencia absoluta media por probabilidad, en puntos porcentuales, diferencias por clase y variación total media.

## Orden de ejecución tras aprobar

1. Verifico hashes y registro aprobación real.
2. Actualizo solo Elo y forma con resultados anteriores al corte. Esta entrada es necesaria **antes** de generar las 72 predicciones.
3. Genero todos los pronósticos con el estado fijo al corte, sin actualizar con partidos del Mundial. Compruebo simetría neutral a 1e-9 y probabilidades que suman 1.
4. Sello predicciones y matrices con SHA256 y fecha UTC; creo el commit y la etiqueta phase4-predictions-frozen.
5. Calculo las métricas semiconfirmatorias del protocolo.
6. Cargo resultados oficiales del Mundial después del congelado y evalúo descriptivamente los grupos. Uso bootstrap pareado por fecha, con sensibilidad por partido, y reporto la incertidumbre real de N=72; no fijo un error estándar supuesto ni declaro superioridad por una diferencia pequeña.
7. Evalúo eliminatorias aparte y a 90 minutos solo si existen datos verificables. Creo un commit separado de resultados y evaluación.

Ningún archivo de reports/models_selected/ ni sus cinco archivos de código con hash se modifica. El JSON es el registro completo y autoritativo de estas reglas.
