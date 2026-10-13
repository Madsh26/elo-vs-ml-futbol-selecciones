"""Edit presentation from existing CSV evidence; retain the approved data section."""
import csv
import json
from pathlib import Path
from verify_final_evaluation import frozen_checks, git, utc_now

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'reports/final_evaluation'


def rows(name):
    with (FOLDER / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    frozen_checks()
    approved = git('show', 'docs-data-sources:README.md').decode('utf-8')
    data_section = approved[approved.index('## Datos'):approved.index('## Método y lectura de resultados')]
    metrics = rows('semiconfirmatory_metrics.csv')
    primary = next(r for r in metrics if r['model']=='logistic' and r['stratum']=='non_friendlies')
    baseline = next(r for r in metrics if r['model']=='elo' and r['stratum']=='non_friendlies')
    gain = -float(primary['difference_log_loss'])
    relative = 100 * gain / float(baseline['log_loss'])
    ci = [float(primary['difference_log_loss_ci_low']), float(primary['difference_log_loss_ci_high'])]
    inventory = json.loads((FOLDER / 'data_inventory.json').read_text(encoding='utf-8'))
    n = f"{inventory['semiconfirmatory_matches']:,}".replace(',', '.')
    top = '# ¿Le gana el machine learning a Elo? Evaluación retrospectiva de 8 modelos en fútbol de selecciones y el Mundial 2026\n\n'
    top += f"**{n} partidos · protocolo sellado con hashes · {inventory['group_forecasts']} partidos del Mundial**\n\n"
    top += '**Pregunta:** ¿mejoran el aprendizaje automático y los modelos de goles a un Elo simple al predecir partidos de selecciones?\n\n'
    top += f"**Resultado:** en no amistosos, la logística con Elo y forma reduce el log loss en **{gain:.4f}** (≈{relative:.0f}% relativo; IC [{ci[0]:.4f}; {ci[1]:.4f}]) y el acierto es prácticamente igual ({100*float(primary['accuracy']):.2f}% frente a {100*float(baseline['accuracy']):.2f}%). XGBoost y los modelos de goles no demuestran una mejora robusta en esta evaluación semiconfirmatoria. La ventaja tampoco queda demostrada entre selecciones fuertes ni en los grupos del Mundial. [Fuente: métricas ejecutadas](reports/final_evaluation/semiconfirmatory_metrics.csv).\n\n"
    top += '![Comparación probabilística](assets/model_comparison.png)\n\n'
    top += 'Estudio retrospectivo, construido con el Mundial ya jugado. La evidencia 2023–corte es semiconfirmatoria por exposición previa al periodo. [Explorar los partidos](reports/final_evaluation/football_report.html) · [Resultados](reports/final_evaluation/RESULTADOS.md) · [Explicación sencilla](docs/COMO_ENTENDER_EL_MODELO.md).\n\n'
    periods = [r for r in rows('semiconfirmatory_subperiods.csv') if r['model']=='logistic' and r['stratum']=='non_friendlies' and r['start'][:4] in ['2023','2024','2025']]
    slopes = next(r for r in rows('semiconfirmatory_calibration.csv') if r['model']=='logistic' and r['stratum']=='non_friendlies' and r['class']=='1')
    errors = rows('worldcup_largest_errors.csv')[:10]
    zeros = sum(r['actual_score']=='0-0' for r in errors)
    favourite = max(errors, key=lambda r: float(r['log_loss']))
    match = next(r for r in rows('worldcup_group_scored_logistic.csv') if r['home_team']=='Colombia' and r['away_team']=='Portugal')
    source_note = json.loads((ROOT/'docs/market_plausibility_sources.json').read_text(encoding='utf-8'))
    odds = source_note['verified_match_market']
    critical = '## Limitaciones y lectura crítica\n\n'
    critical += f"- **Efecto pequeño y posible deriva.** La diferencia de log loss frente a Elo pasa por {', '.join(r['start'][:4]+': '+format(float(r['difference_log_loss']),'.4f') for r in periods)}. Mantengo coeficientes sin reajuste; la ventaja disminuye en esos tres años. Es una señal exploratoria de posible deriva, no una causa demostrada. [CSV por periodo](reports/final_evaluation/semiconfirmatory_subperiods.csv).\n"
    favourite_name = {'Spain':'España'}.get(favourite['home_team'],favourite['home_team'])
    critical += f"- **Calibración del empate.** La pendiente diagnóstica es {float(slopes['slope']):.2f} en no amistosos; el ideal es 1. Entre los diez mayores errores de los grupos, {zeros} son 0–0. El mayor es {favourite_name}–{favourite['away_team']}, donde el favorito tenía {100*max(float(favourite[c]) for c in ['p_home_win','p_away_win']):.1f}%. No ajusto el modelo con este diagnóstico. [Calibración](reports/final_evaluation/semiconfirmatory_calibration.csv) · [Errores](reports/final_evaluation/worldcup_largest_errors.csv).\n"
    probabilities = '/'.join(f"{100*float(match[c]):.1f}" for c in ['p_home_win','p_draw','p_away_win'])
    critical += f"- **Elo solo conoce resultados**, no plantillas, lesiones ni valor de mercado. En Colombia–Portugal, el estado con corte exclusivo 2026-06-10 es Elo {float(match['elo_home']):.0f} frente a {float(match['elo_away']):.0f}; la logística sellada el 2026-10-12 asigna {probabilities}% (Colombia/empate/Portugal). [Estado previo sellado](reports/final_evaluation/features_72_frozen.csv) · [Predicción congelada](reports/final_evaluation/group_forecasts_logistic.csv). Como contraste de plausibilidad exploratorio, [Australia Football]({odds['url']}) publicó el {odds['publication_date']} una cuota {odds['decimal_odds_portugal']} para Portugal, equivalente a {odds['published_implied_percentage']}% implícito bruto, sin descontar el margen. Esa información es posterior al corte y no es un benchmark evaluado: no la mezclo con los resultados del protocolo ni la presento como consenso verificado de todo el mercado. [Registro de fuentes y fechas](docs/market_plausibility_sources.json).\n"
    critical += '- **Hipótesis no probada:** el escaso anclaje entre confederaciones podría hacer que Elo sobrevalore algunas selecciones de CONMEBOL. No atribuyo causalidad ni generalizo desde un partido.\n'
    critical += '- **Sin referencia externa de mercado en la evaluación.** Queda como trabajo futuro comparar cuotas, plantillas y valoraciones con fecha, respetando el mismo corte de información.\n\n'
    body = approved[approved.index('## Método y lectura de resultados'):]
    readme = top + data_section + body[:body.index('## Reproducibilidad y documentación técnica')] + critical + body[body.index('## Reproducibilidad y documentación técnica'):]
    readme += '\n## Publicación en GitHub\n\nNombre sugerido: `elo-vs-ml-futbol-selecciones`. Topics: `sports-analytics`, `elo-rating`, `xgboost`, `probabilistic-forecasting`, `reproducible-research`.\n'
    assert readme[readme.index('## Datos'):readme.index('## Método y lectura de resultados')] == data_section
    # The Git blob already contains CRLF. Do not translate its newlines again.
    (ROOT/'README.md').write_text(readme, encoding='utf-8', newline='')
    print('README text generated from existing evidence; approved data section retained exactly.')


if __name__ == '__main__':
    main()
