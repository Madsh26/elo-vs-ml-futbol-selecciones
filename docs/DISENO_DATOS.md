# Definición del historial y del marcador

Uso dos conjuntos relacionados. El historial conserva los partidos válidos de las fuentes locales, incluidas eliminatorias, campeonatos continentales y Nations League. El conjunto de entrenamiento de goles contiene únicamente los partidos cuyo marcador a 90 minutos puedo reconstruir. Los supuestos de duración de amistosos quedan en una alternativa de sensibilidad, fuera del conjunto principal.

Un partido sin marcador verificable a 90 minutos no desaparece del historial. Puede actualizar Elo y la forma basada en resultados, pero no aporta goles a las ventanas de ataque y defensa. Cada ventana registra qué proporción de sus partidos tiene información de goles comparable. Para muestras pequeñas, el promedio de goles incluye un prior fijo equivalente a tres partidos con 1,3 goles por equipo; no lo interpreto como datos observados.

## Evidencia de duración

1. Filtro las fechas antes de interpretar y conservar valores de goles. El límite es exclusivo: no entra ningún partido del 10 de junio de 2026 o posterior.
2. En Fjelstul compruebo que la cantidad de goles atribuida a cada equipo coincide con el marcador final. Descuento únicamente los eventos identificados como prórroga por su periodo.
3. En martj42 compruebo equipo anotador, cantidades de goles, minutos presentes y rango de minutos. El descuento se codifica como minuto 90; los eventos mayores de 90 corresponden a prórroga en la semántica contrastada de esta fuente.
4. Conservo eventos aparentemente idénticos. Dos goles pueden compartir equipo, minuto y jugador; eliminarlos sin contrastar el marcador altera la evidencia.
5. Un marcador final 0–0 permite conocer el 0–0 a 90 minutos aunque el encuentro haya continuado sin goles.
6. No convierto una tanda automáticamente en empate. Una tanda puede resolver una eliminatoria a dos partidos. Si falta evidencia de goles a 90 minutos, el partido conserva una marca de exclusión del entrenamiento de goles.
7. Un amistoso sin tanda conocida y sin eventos disponibles queda excluido del entrenamiento principal de goles. En una alternativa de sensibilidad declaro la suposición de duración estándar. No uso esa alternativa para resolver conflictos entre fuentes o minutos faltantes.
8. Si las fuentes discrepan o los eventos no coinciden con el marcador, excluyo la etiqueta de goles y conservo el motivo.

StatsBomb se reserva para comprobar marcadores y semántica de periodos, no para construir características predictivas. Su minuto numérico puede superar 90 durante el descuento; no aplico allí la regla de minutos de martj42.

## Resultado utilizado por Elo

La política principal utiliza el marcador a 90 minutos cuando está disponible. En los casos no verificables utiliza el marcador final registrado, posiblemente con prórroga, sin incorporar el ganador de la tanda. Esta limitación queda identificada en cada fila.

Comparo cinco políticas manteniendo los mismos parámetros de Elo:

- Historial completo con marcador a 90 minutos cuando está disponible y marcador registrado en los demás casos.
- Historial completo utilizando siempre el marcador final registrado.
- Solo partidos con etiqueta de goles a 90 minutos admisible.
- Esos partidos más los amistosos de duración estándar supuesta, como alternativa explícita.
- `baseline_elo_amistosos`: restringe el historial a amistosos y Mundiales, utilizando el mismo archivo de resultados y corte que las demás políticas. No uso sus goles no verificables como etiquetas del conjunto principal.

La sensibilidad mide cambios en el estado Elo y en la cobertura. No demuestra mejoras de predicción. Los parámetros se mantienen fijos para aislar estas decisiones sobre datos; su calibración temporal corresponde a una operación posterior.

El modelo guardado de la referencia de amistosos se conserva por separado. No atribuyo a esa referencia entrenada las métricas de una política recalculada con otro archivo de resultados.

## Identidad y fechas

Mantengo los alias de una misma selección y las correspondencias históricas con sus intervalos de vigencia. Czechoslovakia y Czech Republic son entidades distintas. Fjelstul y Openfootball son fuentes distintas aunque sus archivos ZIP compartan nombre.

Para los partidos de una misma fecha calculo todas las características antes de actualizar el historial con cualquiera de sus resultados. Las consultas del fixture utilizan el historial conocido en el corte; no simulo resultados intermedios para actualizarlo.

## Fuentes pendientes

No hay tablas de mercado disponibles: guardo la cobertura de Transfermarkt como faltante, no como cero. La estructura admite enriquecimientos opcionales posteriores; no utilizo clubes ni valores actuales de jugadores como sustitutos de información histórica.

El archivo de ranking con una fotografía repetida en fechas distintas está excluido. El ranking de año/semestre presente en los archivos llega a 2024. Solo puede estudiarse como variable secundaria con disponibilidad conservadora después del semestre y un máximo de 90 días de antigüedad. No extrapolo un ranking vigente para 2026 ni afirmo que haya sido incorporado al modelo en esta preparación.

GeoNames se considera una fuente de altitud estática. Su fecha de edición no se usa como información de rendimiento deportivo. La elección del lugar representativo del país de origen debe ser explícita, no una supuesta altitud de toda la selección.

## Estudio retrospectivo y sellado

Construyo el estudio con el Mundial ya jugado. No lo presento como un pronóstico publicado antes de su comienzo. Las fechas de corte, preparación, congelado y carga de resultados oficiales representan operaciones distintas.

La preparación no congela un modelo ni carga resultados oficiales posteriores al corte. El congelado deberá registrar modelo, configuración y predicciones, con sus hashes, antes de iniciar la evaluación de 2026. Los marcadores vistos en documentación de Openfootball no intervienen en decisiones de modelado.
