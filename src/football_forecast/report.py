"""Offline, precomputed report. Opening it never trains a model."""
import html
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def write_report(out, matches, teams, metrics, test, probabilities, audit):
    fig, axes = plt.subplots(1,3, figsize=(12,4), sharex=True, sharey=True)
    for idx,label in enumerate(['Victoria A','Empate','Victoria B']):
        ax = axes[idx]
        ax.plot([0,1],[0,1], '--', color='#999', linewidth=1)
        for name in ['dixon_coles','xgboost_1x2','xgboost_dixon_coles']:
            p = probabilities[name][:,idx]
            bins = np.minimum((p*8).astype(int),7)
            xs,ys = [],[]
            for b in range(8):
                mask = bins == b
                if mask.sum() >= 15:
                    xs.append(p[mask].mean())
                    ys.append((test.target.to_numpy()[mask]==idx).mean())
            ax.plot(xs,ys,'o-', label=name, markersize=3)
        ax.set(title=label, xlabel='Probabilidad prevista', xlim=(0,1), ylim=(0,1))
        ax.grid(alpha=.15)
    axes[0].set_ylabel('Frecuencia observada')
    axes[2].legend(fontsize=7)
    fig.suptitle('Calibración en prueba temporal · bins con al menos 15 partidos')
    fig.tight_layout()
    fig.savefig(out/'calibration.png', dpi=150)
    plt.close(fig)
    records = json.loads(matches.to_json(orient='records'))
    encoded = json.dumps(records, ensure_ascii=False).replace('</','<\\/')
    selected = audit['selected_score_model']
    table = metrics[metrics.split=='test'].drop(columns=['split','fit_seconds']).to_html(
        index=False, float_format=lambda v:f'{v:.4f}', classes='metrics', border=0)
    title = 'Probabilidades del Mundial 2026'
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Probabilidades del Mundial 2026</title><style>
:root{font-family:Segoe UI,Arial,sans-serif;color:#183047;background:#f2f5f8}body{margin:0}main{max-width:1180px;margin:auto;padding:32px 24px}h1{font-size:34px;margin:8px 0}h2{margin-top:32px;font-size:22px}.sub{color:#526579;line-height:1.6}.badge{display:inline-block;background:#e1ece8;color:#145e45;padding:7px 12px;border-radius:24px;font-size:13px}.controls{display:flex;gap:18px;flex-wrap:wrap;margin:24px 0}label{display:block;font-size:13px;color:#526579}select{display:block;margin-top:7px;padding:10px;border:1px solid #ccd8e2;border-radius:8px;background:white;min-width:230px}.card{background:white;padding:22px;border-radius:14px;border:1px solid #e0e6ed;margin:16px 0}.triple{display:flex;gap:12px;flex-wrap:wrap}.prob{flex:1;min-width:130px;background:#f1f6fa;padding:18px;border-radius:9px}.prob strong{display:block;font-size:28px;margin-top:8px}.bar{height:8px;background:#dfe8ee;border-radius:10px;margin-top:12px}.bar span{display:block;height:100%;background:#187b77;border-radius:10px}.score{display:flex;gap:20px;margin:12px 0;align-items:center}.score b{width:45px}.score .bar{flex:1;margin:0}.score em{width:75px;font-style:normal}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:11px 8px;border-bottom:1px solid #e3eaf0;text-align:left}th{color:#526579}.scroll{overflow-x:auto}img{max-width:100%}button{cursor:pointer;border:0;background:transparent;color:#087870;padding:0;text-align:left;font:inherit}.note{font-size:13px;line-height:1.6;color:#526579}a{color:#087870}details{line-height:1.7}.metrics{font-size:12px}footer{margin:30px 0;color:#526579;font-size:12px}
</style><main><span class="badge">Datos locales · 0 simulaciones de torneos</span><h1>Probabilidades del Mundial 2026</h1>
<p class="sub">Estudio retrospectivo de los 72 partidos de grupos. Probabilidades a 90 minutos, calculadas directamente desde modelos de goles o un clasificador de tres clases.</p>
<p class="note">Corte exclusivo: __CUTOFF__. No se descargaron datos. El histórico contiene partidos de 2026 programados sin resultados. Los participantes de repechajes se resolvieron con ese calendario local; su disponibilidad histórica no está certificada.</p>
<div class="controls"><label>Modelo<select id="model"></select></label><label>Selección<select id="team"></select></label><label>Partido<select id="match"></select></label></div>
<section class="card"><h2 id="heading" style="margin-top:0"></h2><p id="context" class="note"></p><div class="triple" id="probs"></div><h3>Marcadores más probables</h3><div id="scores"></div><p id="tail" class="note"></p></section>
<section class="card"><h2 style="margin-top:0">Todos los partidos del filtro</h2><div class="scroll"><table><thead><tr><th>Grupo</th><th>Partido</th><th>Gana A</th><th>Empate</th><th>Gana B</th><th>Marcador más probable</th></tr></thead><tbody id="fixtures"></tbody></table></div></section>
<section class="card"><h2 style="margin-top:0">Evaluación independiente</h2><p class="note">Prueba: 2023 hasta el corte. Selección del modelo de marcadores: verosimilitud de 2022. Estas métricas corresponden a modelos congelados del backtest, no a los modelos posteriormente reentrenados para el fixture. Menor log loss, Brier y NLL es mejor. Brier multiclase sin dividir entre dos.</p><div class="scroll">__METRICS__</div><img src="calibration.png" alt="Curvas de calibración de las tres clases en prueba temporal"></section>
<section class="card"><h2 style="margin-top:0">Qué significan las cifras</h2><details open><summary>Metodología y límites</summary><ul><li>Las probabilidades son condicionales al rival, sede y datos disponibles; no son probabilidades de ser campeón.</li><li>Los cinco marcadores mostrados no cubren toda la distribución. Se exporta la matriz completa en CSV.</li><li>Entrenamiento conservador: amistosos (supuestos a 90 minutos) y Mundiales masculinos con goles de prórroga descontados mediante eventos locales. Otras competiciones se excluyen por duración no verificada.</li><li>XGBoost aprende tasas de goles y, en un modelo separado, probabilidades 1X2. Las tasas previstas no son xG de calidad de tiros.</li><li>Dixon-Coles ajusta cuatro marcadores bajos. El híbrido con tasas XGBoost es un experimento propio.</li><li>El reporte carga resultados precomputados. No entrena ni simula al abrirlo.</li></ul></details><p><a href="match_probabilities.csv">Partidos CSV</a> · <a href="team_match_probabilities.csv">Perspectivas por equipo</a> · <a href="scoreline_probabilities.csv">Marcadores CSV</a> · <a href="data_audit.json">Auditoría</a></p></section><footer>Proyecto de ML con información local · Semilla 2026 · CPU limitada</footer>
<script>const data=__DATA__;const preferred=__SELECTED__;const $=id=>document.getElementById(id);const pct=x=>(100*x).toFixed(1)+'%';
const models=[...new Set(data.map(x=>x.model))];models.forEach(x=>$('model').add(new Option(x+(x===preferred?' · elegido en validación':''),x)));$('model').value=preferred;
const teams=[...new Set(data.flatMap(x=>[x.home_team,x.away_team]))].sort();$('team').add(new Option('Todas las selecciones',''));teams.forEach(x=>$('team').add(new Option(x,x)));
function filtered(){return data.filter(x=>x.model===$('model').value&&(!$('team').value||[x.home_team,x.away_team].includes($('team').value)))}
function refresh(){const rows=filtered();$('match').replaceChildren();rows.forEach(x=>$('match').add(new Option(x.home_team+' vs '+x.away_team,String(x.match_id))));$('fixtures').replaceChildren();rows.forEach(x=>{const tr=document.createElement('tr');const vals=[x.group,x.home_team+' vs '+x.away_team,pct(x.p_home_win),pct(x.p_draw),pct(x.p_away_win),(x.top_scorelines||'Sin modelo de marcadores').split(';')[0]];vals.forEach((v,i)=>{const td=document.createElement('td');if(i===1){const b=document.createElement('button');b.textContent=v;b.onclick=()=>{$('match').value=String(x.match_id);detail()};td.append(b)}else td.textContent=v;tr.append(td)});$('fixtures').append(tr)});detail()}
function detail(){const x=filtered().find(x=>String(x.match_id)===$('match').value);if(!x)return;$('heading').textContent=x.home_team+' vs '+x.away_team;$('context').textContent='Grupo '+x.group+' · '+x.date_utc+' · '+x.model;$('probs').replaceChildren();[[x.home_team,x.p_home_win],['Empate',x.p_draw],[x.away_team,x.p_away_win]].forEach(([label,p])=>{const box=document.createElement('div');box.className='prob';box.append(document.createTextNode(label));const strong=document.createElement('strong');strong.textContent=pct(p);box.append(strong);const bar=document.createElement('div');bar.className='bar';const fill=document.createElement('span');fill.style.width=pct(p);bar.append(fill);box.append(bar);$('probs').append(box)});$('scores').replaceChildren();if(!x.top_scorelines){$('scores').textContent='Este clasificador estima 1X2; no genera marcadores.';$('tail').textContent='Se muestra por separado para compararlo con los modelos de goles.';return}let covered=0;x.top_scorelines.split('; ').forEach(s=>{const [score,prob]=s.split(': ');const p=Number(prob);covered+=p;const row=document.createElement('div');row.className='score';const b=document.createElement('b');b.textContent=score;const bar=document.createElement('div');bar.className='bar';const fill=document.createElement('span');fill.style.width=(100*p/.3)+'%';fill.style.maxWidth='100%';bar.append(fill);const value=document.createElement('em');value.textContent=pct(p);row.append(b,bar,value);$('scores').append(row)});$('tail').textContent='Otros marcadores: '+pct(1-covered)+'. Masa de cola omitida antes de normalizar: '+Number(x.tail_mass_omitted).toExponential(2)+'.'}
$('model').onchange=refresh;$('team').onchange=refresh;$('match').onchange=detail;refresh();</script></main></html>'''
    page = page.replace('__CUTOFF__',html.escape(audit['prediction_cutoff_exclusive']))
    page = page.replace('__METRICS__',table).replace('__DATA__',encoded)
    page = page.replace('__SELECTED__',json.dumps(selected))
    (out/'report.html').write_text(page, encoding='utf-8')
    summary = f'''# Resultados del pipeline local

Modelo de marcadores elegido en validación 2022: **{selected}**.

{len(matches)} filas de probabilidades: 72 encuentros y seis modelos. Cuatro modelos exportan distribuciones de marcadores; dos clasificadores se comparan por separado. Las perspectivas por equipo corresponden a los cuatro modelos de marcadores.

## Protocolo

Entrenamiento 2010-2017; parada anticipada 2018-2019; dependencia del híbrido 2020-2021; selección de marcadores/calibración 2022; prueba 2023 hasta el corte. Variables actualizadas solo con partidos de fechas anteriores. Tras archivar el backtest, modelos de despliegue ajustados con todo el historial elegible y calibración mediante predicciones fuera de tiempo.

El backtest es secuencial, no una evaluación con todas las variables congeladas antes de un torneo. Los modelos finales de despliegue no tienen nuevas métricas de prueba independientes.

## Datos

Corte exclusivo: {audit['prediction_cutoff_exclusive']}. Último resultado local con goles: {audit['latest_scored_date']}. Registros de 2026 programados: {audit['worldcup_2026_scheduled_rows']}; con resultados: {audit['worldcup_2026_scored_rows']}.

Política de duración: {audit['duration_policy']}

Se usa información local de participantes del calendario sin certificar su disponibilidad en la fecha histórica. No es una predicción publicada antes del Mundial.

## Evaluación temporal

```text
{metrics[metrics.split=='test'][['model','log_loss','brier_multiclass_unscaled','score_nll']].to_string(index=False)}
```

Las tasas de goles no son un modelo de xG basado en tiros. La importancia de variables no demuestra causalidad. La temperatura del clasificador no altera las matrices de marcadores de otros modelos.

Ejecución: {audit['elapsed_seconds']:.1f} segundos, {audit['threads']} hilos para XGBoost, cero simulaciones de torneos. Este tiempo corresponde a esta máquina y ejecución.
'''
    (out/'RESULTADOS.md').write_text(summary,encoding='utf-8')
