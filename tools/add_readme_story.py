"""Add the author's verified project narrative without changing evaluation evidence."""
import csv
import json
from pathlib import Path
import sys
from verify_final_evaluation import frozen_checks, git

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'reports/final_evaluation'
URL='https://madsh26.github.io/elo-vs-ml-futbol-selecciones/'


def rows(name):
    with (FOLDER/name).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    frozen_checks()
    current=(ROOT/'README.md').read_bytes().decode('utf-8')
    approved=git('show','docs-data-sources:README.md').decode('utf-8')
    section=lambda text:text[text.index('## Datos'):text.index('## Método y lectura de resultados')]
    assert section(current)==section(approved)
    metrics=rows('semiconfirmatory_metrics.csv')
    primary=next(r for r in metrics if r['model']=='logistic' and r['stratum']=='non_friendlies')
    elo=next(r for r in metrics if r['model']=='elo' and r['stratum']=='non_friendlies')
    groups=rows('worldcup_group_metrics.csv')
    gl=next(r for r in groups if r['model']=='logistic')
    ge=next(r for r in groups if r['model']=='elo')
    years=[r for r in rows('semiconfirmatory_subperiods.csv') if r['model']=='logistic' and r['stratum']=='non_friendlies' and r['start'][:4] in ['2023','2024','2025']]
    errors=rows('worldcup_largest_errors.csv')
    spain=next(r for r in errors if r['home_team']=='Spain' and r['away_team']=='Cabo Verde')
    col=next(r for r in rows('group_forecasts_logistic.csv') if r['home_team']=='Colombia' and r['away_team']=='Portugal')
    inventory=json.loads((FOLDER/'data_inventory.json').read_text(encoding='utf-8'))
    market=json.loads((ROOT/'docs/market_plausibility_sources.json').read_text(encoding='utf-8'))['verified_match_market']
    gain=-float(primary['difference_log_loss'])
    total=f"{inventory['semiconfirmatory_matches']:,}".replace(',','.')
    story=f'''## Por qué hice este proyecto

Empecé este trabajo a partir de una entrega para una competencia de DataCamp. La meta era simple: sumar puntos prediciendo el Mundial 2026. Me interesaba aplicar XGBoost a un problema deportivo concreto y convertirlo después en un proyecto para mi portafolio. Al revisar la entrega, vi que una puntuación por sí sola no respondía lo que más me importaba: si el modelo aprendía algo útil o si la complejidad solo hacía más difícil entenderlo. Replanteé el estudio con otra pregunta: **¿le gana el machine learning a un Elo simple?**

Los datos útiles para el ajuste eran, sobre todo, resultados de partidos. No tenía una cobertura histórica suficiente de plantillas, lesiones o cuotas con fecha para compararlos en las mismas condiciones. Eso definió el propósito: medir cuánto aporta el machine learning cuando comparte con Elo una información limitada, sin presentarlo como un modelo capaz de competir con las casas de apuestas.

Fijé el protocolo y los hashes antes de la evaluación formal de 2023–2026 y sellé las predicciones antes del contraste oficial del Mundial. Esa separación tiene un límite: la entrega histórica de DataCamp ya había puntuado parte de ese periodo. Por eso lo llamo **semiconfirmatorio**, no una prueba completamente nueva. Todo el estudio se construyó con el torneo ya jugado; no afirmo haber publicado estas predicciones antes del Mundial.

### Qué es Elo

Elo es una calificación que sube o baja después de cada partido: ganarle a un rival fuerte suma más que ganarle a uno débil. Resume resultados pasados y dificultad de los rivales en un número. En este estudio, transformo la diferencia entre dos equipos en probabilidades de victoria, empate y derrota mediante una logística, teniendo en cuenta la sede. Su sencillez lo convierte en una buena referencia: cualquier modelo más complejo debe justificar qué aporta sobre él.

### Mi recorrido

1. Recalculé Elo con el historial de competiciones y lo usé como referencia, con la misma información de sede que los demás modelos.
2. Probé siete alternativas: frecuencias históricas, logística con forma reciente, regresión ordinal, XGBoost 1X2, Poisson, Dixon-Coles y XGBoost Poisson.
3. Detecté un sesgo en la preparación de datos: algunos 0–0 entraban sin eventos completos, mientras que otros marcadores sin esa cobertura se excluían. Así, el conjunto admitido exageraba los empates y producía una mejora aparente, especialmente en amistosos. Exigí que la inclusión no dependiera del resultado, repetí la selección previa a 2023 y conservé los diagnósticos en el registro de decisiones. Una tanda tampoco se convirtió automáticamente en empate a 90 minutos.
4. Dejé por escrito criterios, cortes temporales y condiciones de comparación, y los sellé con hashes y etiquetas de Git. Separé la selección anterior a 2023 de la evaluación formal posterior, manteniendo explícita la exposición previa de DataCamp.
5. Evalué {total} partidos y describí los {inventory['group_forecasts']} de grupos del Mundial, sin usar sus resultados para cambiar coeficientes, variables o conclusiones del protocolo.

### Lo que más me sorprendió

- **Elo es difícil de superar.** En no amistosos, la logística reduce el log loss en {gain:.4f} (≈{100*gain/float(elo['log_loss']):.0f}% relativo), mientras el acierto es prácticamente igual: {100*float(primary['accuracy']):.2f}% frente a {100*float(elo['accuracy']):.2f}%. XGBoost no demuestra una mejora robusta. [Métricas](reports/final_evaluation/semiconfirmatory_metrics.csv).
- **El Mundial no demuestra superioridad.** La logística tiene un log loss ligeramente menor que Elo ({float(gl['log_loss']):.4f} frente a {float(ge['log_loss']):.4f}); las otras alternativas más complejas quedan por encima en el punto estimado. Pero el intervalo de diferencia de logística incluye cero y {inventory['group_forecasts']} partidos no cumplen el mínimo de inferencia fijado. [Comparación de grupos](reports/final_evaluation/worldcup_group_metrics.csv).
- **La ventaja disminuye en tres años consecutivos:** {', '.join(format(float(r['difference_log_loss']),'.4f')+' en '+r['start'][:4] for r in years)}. Es una señal de posible deriva al mantener coeficientes sin reajuste, no una explicación demostrada. [Resultados por periodo](reports/final_evaluation/semiconfirmatory_subperiods.csv).
- **Un gran favorito también puede terminar 0–0.** España tenía {100*float(spain['p_home_win']):.1f}% contra Cabo Verde y el resultado registrado fue {spain['actual_score']}. Es uno de los casos que muestra por qué necesito revisar probabilidades y calibración, no solo aciertos. [Errores del Mundial](reports/final_evaluation/worldcup_largest_errors.csv).
- **Colombia–Portugal me hizo mirar los límites de la información.** Mi modelo daba {100*float(col['p_home_win']):.1f}% a Colombia y {100*float(col['p_away_win']):.1f}% a Portugal. [Predicción sellada](reports/final_evaluation/group_forecasts_logistic.csv). Como contraste exploratorio, [Australia Football]({market['url']}) publicó el {market['publication_date']} una probabilidad implícita bruta de {market['published_implied_percentage']}% para Portugal, sin descontar el margen de las cuotas. Esa referencia es posterior al corte y no forma parte de las métricas del protocolo. Elo conoce resultados; no conoce plantillas, lesiones ni valor de mercado.

### Cómo usé IA

Yo definí la pregunta, el alcance y las condiciones de aceptación: qué información podía entrar, qué fecha debía respetarse y qué evidencia exigir antes de aceptar un modelo más complejo. También pedí las comprobaciones que marcaron el rumbo del proyecto: admisión independiente del marcador, simetría en cancha neutral, sensibilidad de los goles a 90 minutos y separación entre selección y evaluación.

Usé **OpenAI Codex** como asistente de implementación y revisión. La IA escribió y ajustó el código, las pruebas, los verificadores y la herramienta HTML bajo esas condiciones. Mi papel fue dirigir el diseño, cuestionar mejoras que podían ser artefactos y aprobar las decisiones después de revisar la evidencia. No doy por válido el código solo porque lo genere una IA: la verificación quedó en pruebas ejecutadas, comprobaciones de fechas, CSV auditables y hashes que permiten detectar cambios. Reconozco esa ayuda y mantengo la responsabilidad de las decisiones y de cómo presento los resultados.

### Trabajo futuro

El siguiente paso sería dar a los modelos información que Elo no resume: convocatorias y minutos recientes, bajas confirmadas, rendimiento de jugadores, valoraciones históricas y contexto del partido. Priorizaría archivos históricos y APIs; cuando fuera necesario, usaría web scraping permitido para recopilar datos de fuentes identificables. Cada registro tendría fecha de observación y disponibilidad. Una plantilla actual o una valoración publicada después del partido no puede representar lo que se sabía antes de jugar.

Antes de entrenar, comprobaría cobertura por selección, periodo y confederación, y distinguiría un dato faltante de un valor bajo. También buscaría marcadores por periodo para reducir la aproximación de duración supuesta. Incorporaría cada grupo de variables por separado y repetiría la validación temporal: más datos no garantizan que XGBoost mejore, y una ganancia debe mantenerse frente a Elo y la logística con la misma información disponible.

Compararía después con cuotas de mercado registradas a una hora fija previa al partido, descontando su margen y sin tratarlas como probabilidades perfectas. Ese contraste permitiría separar cuánto aporta el modelo de cuánto aporta una fuente nueva. Finalmente, probaría de forma explícita si el escaso anclaje intercontinental hace que Elo sobrevalore algunas confederaciones, incluida CONMEBOL. Hoy esa explicación es una **hipótesis no probada**. Cualquier ampliación tendría un protocolo nuevo; no reabriría este estudio congelado para mejorar retrospectivamente sus cifras.

![Vista previa del informe interactivo](assets/report_preview.png)

'''
    marker='Estudio retrospectivo, construido con el Mundial ya jugado.'
    start=current.index(marker)
    if '## Por qué hice este proyecto' in current:
        first=current.index('## Por qué hice este proyecto')
        current=current[:first]+current[start:]
        start=current.index(marker)
    current=current[:start]+story+current[start:]
    current=current.replace('[Explorar los partidos](reports/final_evaluation/football_report.html)',f'[Explorar el informe en GitHub Pages]({URL}) · [HTML en el repositorio](reports/final_evaluation/football_report.html) · [Portafolio](https://madsh26.github.io/)')
    if '## Publicación en GitHub' in current:
        current=current[:current.index('## Publicación en GitHub')].rstrip()+'\n'
    assert section(current)==section(approved)
    assert '[Completa' not in current and '[completa' not in current
    (ROOT/'README.md').write_text(current,encoding='utf-8',newline='')
    print('Verified narrative added; approved data section retained; no metrics computed.')


if __name__=='__main__':main()
