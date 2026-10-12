# Cómo entiendo los modelos

Mi modelo elegido no es Solo Elo: es una regresión logística que utiliza Elo y forma reciente. Elo es una medida de fuerza y la referencia contra la que compruebo si algo más complejo merece utilizarse.

Elo se parece a una clasificación que aprende después de cada partido. Ganar contra un rival fuerte aporta más que ganar contra uno débil. Perder contra un favorito suele restar menos que perder contra un rival débil. Mi cálculo también distingue competiciones, margen de goles y sede. No es el ranking FIFA.

La logística aprende a convertir la diferencia de fuerza y la forma reciente en tres probabilidades. Si imagino un marcador de fuerza como un termómetro, Elo es la lectura; la logística es la regla aprendida para traducirla a victoria, empate y derrota. El baseline Solo Elo también ajusta una logística, pero solo con la diferencia efectiva de Elo y sede.

Sí entrené otras alternativas: ordinal, XGBoost, Poisson y Dixon-Coles, además de frecuencias y las dos logísticas. XGBoost puede aprender relaciones más complejas, pero eso no garantiza que sus probabilidades sean mejores fuera del entrenamiento. Con esta configuración y estos datos no mostró una mejora robusta; eso no demuestra que XGBoost sea inferior en cualquier problema.

Elo resume mucha información: resultados anteriores y fuerza de los rivales. Una variable adicional puede repetir lo que ya resume o añadir ruido. Las métricas no identifican por sí solas la causa de cada diferencia; lo que sí muestran es qué mejora se sostuvo en mis bloques y con qué incertidumbre.

No elimino variables por intuición. Probé descanso, competición, altitud y ranking mediante ablación: añadí cada grupo y medí si aportaba. No cumplieron el criterio. El valor de mercado tiene otro problema: no tengo pertenencia histórica fechada suficiente a las selecciones, y usar el club o valor actual introduciría información del futuro.

Poisson responde a otra pregunta: cuántos goles puede marcar cada equipo. A partir de esas tasas genero probabilidades de 0–0, 1–0, 1–1 y otros marcadores; al sumarlas obtengo su propio 1X2. La logística y Poisson no tienen por qué coincidir. Muestro ambos como productos distintos y no hago que parezcan un único modelo.

Nombré el trabajo **Probabilidades de fútbol internacional**, con el subtítulo **Evaluación retrospectiva de Elo, aprendizaje automático y modelos de goles**. Para el repositorio mantengo international-football-probabilities. El nombre describe lo que estudio sin prometer un ganador o una precisión que todavía no he demostrado.
