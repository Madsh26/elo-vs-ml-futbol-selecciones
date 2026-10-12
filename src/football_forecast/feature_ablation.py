"""Fixed temporal ablations of context, recent form and coverage weighting."""
from pathlib import Path
from datetime import datetime,timezone
import json
import numpy as np
import pandas as pd
from .elo_calibration import (BLOCKS,walk_forward,symmetric_predictions,per_match_metrics,block_interval)
from .context_features import coverage_weights
from .preparation import markdown_table
from .ingestion import digest_file

def ablate_feature_groups(root,output):
    root,output=Path(root),Path(output)
    groups={
        'recent_form':(['gf_diff','ga_diff','form_diff','opponent_diff','goal_coverage_sum'],[-1,-1,-1,-1,1]),
        'rest':(['rest_diff','rest_missing'],[-1,1]),
        'competition_and_venue':(['home_advantage_sign','competitive','worldcup','neutral'],[-1,1,1,1]),
        'altitude':(['altitude_scaled','venue_altitude_missing'],[1,1]),
    }
    labels={'recent_form':'Goles y forma reciente','rest':'Días desde el último partido',
            'competition_and_venue':'Competición y sede','altitude':'Altitud de sede',
            'coverage_weights':'Ponderación por cobertura','joint_accepted_groups':'Grupos admitidos conjuntamente'}
    protocol={'written_at_utc':datetime.now(timezone.utc).isoformat(),'cutoff_exclusive':'2023-01-01',
              'blocks':BLOCKS,'groups':groups,'weighting':'Training-only confederation ratios clipped 0.5 to 2; mean one.',
              'criterion':'Paired log-loss upper 95% CI <0, Brier not worse, >=3/4 blocks improve.',
              'model':'Symmetric logistic, fixed C=1; selected Elo parameters remain fixed.',
              'multiple_comparisons':'Exploratory feature selection on validation blocks; reserved evaluation required.'}
    (output/'feature_ablation_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    history=pd.read_csv(output/'historical_features.csv',parse_dates=['date'],low_memory=False)
    if (history.date>='2023-01-01').any(): raise ValueError('Reserved outcomes present')
    frame=history[history.goal_training_eligible].copy()
    frame['target']=np.where(frame.home_score_90>frame.away_score_90,0,np.where(frame.home_score_90==frame.away_score_90,1,2))
    frame['elo_scaled']=frame.elo_diff/400
    frame['gf_diff']=frame.gf5_home-frame.gf5_away
    frame['ga_diff']=frame.ga5_home-frame.ga5_away
    frame['form_diff']=frame.form5_home-frame.form5_away
    frame['opponent_diff']=(frame.opponent_elo_home-frame.opponent_elo_away)/400
    frame['goal_coverage_sum']=frame.goals_90_coverage5_home+frame.goals_90_coverage5_away
    frame['rest_diff']=(np.log1p(frame.days_rest_home)-np.log1p(frame.days_rest_away))/5
    frame['rest_missing']=frame.days_rest_home.isna()|frame.days_rest_away.isna()
    frame['altitude_scaled']=frame.venue_altitude_m/1000
    baseline=pd.read_csv(output/'elo_walk_forward_predictions.csv',parse_dates=['date'])
    mappings=pd.read_csv(root/'reports/data_preparation/confederations.csv').set_index('team').confederation.to_dict()
    rows=[]; accepted=[]; results=[]
    def summarize(name,prediction):
        if not prediction[['date','home_team','away_team']].equals(baseline[['date','home_team','away_team']]):
            raise ValueError('Ablation evaluation alignment failed')
        delta=prediction.log_loss-baseline.log_loss
        interval=block_interval(prediction.date,delta)
        improving=int((pd.DataFrame({'block':prediction.block_start,'delta':delta}).groupby('block').delta.mean()<0).sum())
        adopt=bool(interval[1]<0 and prediction.brier.mean()<=baseline.brier.mean() and improving>=3)
        rows.append({'group':name,'log_loss':float(prediction.log_loss.mean()),'brier':float(prediction.brier.mean()),
                     'paired_log_loss_difference':float(delta.mean()),'paired_ci_lower':interval[0],
                     'paired_ci_upper':interval[1],'blocks_improving':improving,'admitted':adopt})
        prediction=prediction.copy();prediction['group']=name;results.append(prediction)
        return adopt
    for name,(columns,signs) in groups.items():
        if summarize(name,walk_forward(frame,['elo_scaled']+columns,[-1]+signs)): accepted.append(name)
    parts=[]
    for start,end in BLOCKS:
        train=frame[(frame.date>='2000-01-01')&(frame.date<start)]
        test=frame[(frame.date>=start)&(frame.date<end)]
        complete=history[(history.date>='2000-01-01')&(history.date<start)]
        weights=coverage_weights(train,complete,mappings,start).to_numpy()
        p=symmetric_predictions(train,test,['elo_scaled'],[-1],weights)
        loss,brier=per_match_metrics(test.target.to_numpy(dtype=int),p)
        parts.append(pd.DataFrame({'date':test.date.to_numpy(),'home_team':test.home_team.to_numpy(),
                                   'away_team':test.away_team.to_numpy(),'block_start':start,'log_loss':loss,'brier':brier}))
    weighting=summarize('coverage_weights',pd.concat(parts,ignore_index=True))
    combined_admitted=False
    if accepted:
        columns=['elo_scaled']+sum([groups[g][0] for g in accepted],[])
        signs=[-1]+sum([groups[g][1] for g in accepted],[])
        combined_admitted=summarize('joint_accepted_groups',walk_forward(frame,columns,signs))
    table=pd.DataFrame(rows)
    table.to_csv(output/'feature_ablation.csv',index=False)
    pd.concat(results,ignore_index=True).to_csv(output/'feature_ablation_predictions.csv',index=False)
    decision={'individual_groups_passing':accepted,'joint_groups_passing':combined_admitted,
              'coverage_weighting_passing':weighting,'protocol_sha256':digest_file(output/'feature_ablation_protocol.json'),
              'coverage_weighting_membership_asof_verified':False,
              'coverage_weighting_role':'Sensitivity diagnostic using explicitly current administrative strata; historical affiliation dates unavailable, not an approved as-of production policy.',
              'reserved_period_used':False,'all_metrics_validation_only':True}
    (output/'feature_selection.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    display=table.copy();display['group']=display.group.map(labels)
    display['admitted']=display.admitted.map({True:'Sí',False:'No'})
    display.columns=['Grupo','Log loss','Brier','Cambio de log loss','IC inferior','IC superior','Bloques con mejora','Admitido']
    path=output/'RESULTADOS.md'
    report=path.read_text(encoding='utf-8').split('\n## Ablación de variables y cobertura')[0]
    report+='\n## Ablación de variables y cobertura\n\nComparé cada grupo con la misma logística sobre Elo, en los mismos partidos y bloques anteriores a 2023. Mantengo fijos los parámetros seleccionados y C=1. Cada contraste usa el criterio escrito antes de ejecutarlo.\n\n'+markdown_table(display,precision=6)
    report+='\n\nLa ponderación utiliza solo cobertura del bloque de entrenamiento y conserva el estrato sin cruce. No abre resultados del bloque siguiente para calcular pesos. La selección de variables comparte los bloques de validación: los intervalos son descriptivos y la comparación independiente sigue pendiente. No atribuyo este resultado a XGBoost.\n'
    report+='\nLos estratos de esa sensibilidad son administrativos actuales; no certifican afiliación histórica por fecha. No habilito esa ponderación como política de producción.\n'
    path.write_text(report,encoding='utf-8')
    coverage_diagnostics(output)
    return decision

def coverage_diagnostics(output):
    output=Path(output)
    metadata=pd.read_csv(output/'historical_features.csv',usecols=['date','home_team','away_team','competition_family','duration_reason'])
    predictions=pd.read_csv(output/'feature_ablation_predictions.csv')
    baseline=pd.read_csv(output/'elo_walk_forward_predictions.csv')
    baseline['group']='elo'
    full=pd.concat([predictions,baseline],ignore_index=True).merge(metadata,on=['date','home_team','away_team'],validate='many_to_one')
    full['scope']=np.where(full.competition_family.eq('friendly'),'Amistosos','No amistosos')
    table=full.groupby(['group','scope']).agg(matches=('log_loss','size'),log_loss=('log_loss','mean'),brier=('brier','mean')).reset_index()
    table.to_csv(output/'feature_ablation_subgroups.csv',index=False)
    paired=full[full.group=='joint_accepted_groups'].merge(full[full.group=='elo'],on=['date','home_team','away_team'],suffixes=('_candidate','_elo'),validate='one_to_one')
    competitive=paired[paired.scope_candidate=='No amistosos']
    interval=block_interval(pd.to_datetime(competitive.date),competitive.log_loss_candidate-competitive.log_loss_elo) if len(competitive) else None
    decision_path=output/'feature_selection.json'
    decision=json.loads(decision_path.read_text(encoding='utf-8'))
    decision['competitive_subset_paired_ci']=interval
    observed_friendlies=full[(full.group=='elo')&(full.scope=='Amistosos')]
    zero_invariants=int(observed_friendlies.duration_reason.eq('zero_score_invariant').sum())
    decision['friendly_evaluation_count']=len(observed_friendlies)
    decision['friendly_zero_invariant_count']=zero_invariants
    decision['friendly_evaluation_limitation']='Not a representative sample. Competition features partly learn observation selection.'
    decision_path.write_text(json.dumps(decision,indent=2),encoding='utf-8')
    display=table[table.group.isin(['elo','joint_accepted_groups'])].copy()
    display.group=display.group.map({'elo':'Solo Elo','joint_accepted_groups':'Elo, forma y contexto'})
    display.columns=['Modelo','Conjunto observado','Partidos','Log loss','Brier']
    path=output/'RESULTADOS.md'
    report=path.read_text(encoding='utf-8').split('\n## Sesgo observable de amistosos')[0]
    report+='\n## Sesgo observable de amistosos\n\n'+markdown_table(display,precision=6)
    report+=f'\n\nDe los {len(observed_friendlies)} amistosos verificables de validación, {zero_invariants} corresponden a marcadores finales 0–0 invariantes. El indicador de competición aprende en parte esta selección: su excelente resultado en esos amistosos no permite afirmar capacidad de pronóstico sobre amistosos generales. En los partidos no amistosos, el intervalo pareado del cambio de log loss de la combinación es {interval}. «No amistosos» incluye las categorías de la fuente, no certifica reconocimiento oficial de cada torneo. La mejora queda limitada a esta validación y requiere la evaluación reservada.\n'
    path.write_text(report,encoding='utf-8')
