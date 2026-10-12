"""Register the human-approved conditions without rewriting the original seal."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
from verify_final_evaluation import frozen_checks,digest,utc_now
from football_forecast.preparation import markdown_table
import pandas as pd

frozen_checks()
folder=ROOT/'reports/final_evaluation'
preflight=json.loads((folder/'threshold_preflight.json').read_text(encoding='utf-8'))
counts=pd.read_csv(folder/'threshold_pre2023_counts.csv')
if not counts[counts.scope.eq('total')].estimable_under_requested_minimum.all():
    raise RuntimeError('Threshold not viable in the complete stratum; request approval of another threshold')
path=folder/'protocol_approved.json'
if path.exists():raise RuntimeError('Approved protocol already exists; do not overwrite it')
protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
protocol['previous_protocol']={'file':'reports/final_evaluation/protocol.json','sha256':digest(folder/'protocol.json'),'tag':'phase4-protocol'}
protocol['written_at_utc']=utc_now()
protocol['status']='approved_by_human_after_pre2023_threshold_verification'
protocol['approval']={'registered_at_utc':utc_now(),'source':'explicit user approval in this chat with three prior conditions',
 'conditions':['pre2023 threshold viability','>=200 matches and >=30 events in each class','quarter-cluster counts and monthly sensitivity'],
 'threshold_retained':1700,'preflight_sha256':digest(folder/'threshold_preflight.json'),
 'approval_is_not_a_backdated_forecast':True}
protocol['estimability']={'minimum_matches':200,'minimum_events_each_class':30,
 'rule':'N>=200 and all three observed class counts>=30',
 'scope':'each reported population and subperiod separately; no pooling to relabel an insufficient block',
 'if_insufficient':'report N, class counts and descriptive point metrics; no inferential superiority or calibration regression; bootstrap intervals labelled descriptive if shown',
 'worldcup_72':'descriptive by design; below inference minimum, never a superiority claim',
 'threshold_preflight':'all four complete strong-team blocks meet minimum; 2022 non-friendly intersection N=184 is descriptive'}
protocol['uncertainty']['monthly_sensitivity']={'unit':'whole calendar months','bootstrap_replicates':2000,'seed':20261012,
 'paired':True,'primary_criterion_unchanged':'quarterly bootstrap only'}
protocol['uncertainty']['cluster_reporting']={'planned_calendar_quarters':14,'planned_calendar_months':42,
 'actual':'report observed distinct quarter/month counts for every stratum and subperiod, including zero',
 'windows':'2023Q1 through 2026Q2; January 2023 through June 2026, final quarter/month partial'}
protocol['git_tags']['protocol']='phase4-protocol-approved'
path.write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding='utf-8')
human=f'''# Protocolo aprobado y condiciones previas

El protocolo completo y autoritativo es **reports/final_evaluation/protocol_approved.json**. Su SHA256 cubre exactamente los bytes de ese archivo JSON, no el directorio, el modelo ni este documento. Conservo protocol.json, su sello y la etiqueta phase4-protocol sin modificaciones.

Registro la aprobación explícita y estas condiciones en {protocol['written_at_utc']}. Creo un commit y etiqueta nuevos: phase4-protocol-approved. Antes de calcular cualquier métrica desde 2023 generaré y congelaré los 72 pronósticos, con su propio commit phase4-predictions-frozen.

## Umbral comprobado sin datos desde 2023

Mantengo ambos Elo previos estrictamente >1700, sin ventaja de sede. El estrato completo cumple los mínimos en los cuatro bloques; el cruce no amistoso de 2022 queda descriptivo con N=184.

{markdown_table(counts.rename(columns={'start':'Inicio','end_exclusive':'Fin exclusivo','scope':'Población','all_matches':'Todos','both_elo_above_1700':'Ambos >1700','home_wins':'Victorias A','draws':'Empates','away_wins':'Victorias B','estimable_under_requested_minimum':'Estimable'}))}

Al 2022-12-31, {preflight['worldcup_48_above_1700_at_2022_12_31']} de 48 selecciones superan 1700. Guardo sus 48 valores en worldcup_48_elo_2022_12_31.csv, calculados con resultados anteriores a 2023; la fecha del último resultado es {preflight['latest_result']}.

## Mínimos e incertidumbre

Un estrato o subperiodo es estimable para inferencia solo con **al menos 200 partidos y 30 eventos de cada clase**. Cuando no alcanza el mínimo, muestro recuentos y métricas descriptivas, sin superioridad ni regresiones de calibración. Los 72 partidos del Mundial serán descriptivos por diseño.

El periodo semiconfirmatorio permite **14 trimestres y 42 meses de calendario**, con el último incompleto. Reportaré el número de clústeres efectivamente observados para cada población. El criterio primario mantiene 2.000 réplicas trimestrales pareadas; añado 2.000 réplicas mensuales como sensibilidad, con semilla 20261012. No sustituyo el criterio trimestral por el resultado mensual.

Se mantienen las demás reglas del [protocolo previo](PROTOCOLO.md): comparación principal de logística contra Solo Elo, cuatro subperiodos, duración supuesta marcada, separación Logística/Poisson, modelos sin reajuste, exclusión de DataCamp y congelado anterior a resultados oficiales. 2023–corte sigue siendo semiconfirmatorio por exposición previa.
'''
(folder/'PROTOCOLO_APROBADO.md').write_text(human,encoding='utf-8')
seal={'protocol_file':'reports/final_evaluation/protocol_approved.json','protocol_sha256':digest(path),
 'sealed_at_utc':utc_now(),'human_protocol_file':'reports/final_evaluation/PROTOCOLO_APROBADO.md',
 'human_protocol_sha256':digest(folder/'PROTOCOLO_APROBADO.md'),'git_tag':'phase4-protocol-approved',
 'explicit_approval_received':True,'conditions_verified_before_post2022_metrics':True}
(folder/'active_protocol.json').write_text(json.dumps(seal,indent=2,ensure_ascii=False),encoding='utf-8')
with (folder/'chronology.jsonl').open('a',encoding='utf-8') as stream:
    stream.write(json.dumps({'at_utc':seal['sealed_at_utc'],'event':'approved_conditions_and_protocol_sealed',
                 'file':seal['protocol_file'],'sha256':seal['protocol_sha256']},ensure_ascii=False)+'\n')
print(json.dumps(seal,indent=2,ensure_ascii=False))
