"""Bounded pre-2023 walk-forward calibration; no held-out evaluation here."""
from collections import defaultdict
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import json
import zipfile
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from .ingestion import before_cutoff_csv, NameRegistry, digest_file
from .preparation import markdown_table

BLOCKS = [('2016-01-01','2018-01-01'),('2018-01-01','2020-01-01'),
          ('2020-01-01','2022-01-01'),('2022-01-01','2023-01-01')]

@dataclass(frozen=True)
class EloParameters:
    friendly_k: float = 12
    nations_k: float = 20
    continental_k: float = 28
    worldcup_k: float = 40
    other_k: float = 16
    margin_strength: float = .5
    home_advantage: float = 60
    initial: float = 1500
    inactivity_rate: float = .1
    inactivity_grace_days: int = 730

def parameter_grid():
    base = EloParameters()
    # Coordinate alternatives avoid a large Cartesian grid on a small PC.
    return [base, replace(base,friendly_k=8,nations_k=16,continental_k=24,worldcup_k=32),
            replace(base,friendly_k=16,nations_k=24,continental_k=32,worldcup_k=48),
            replace(base,margin_strength=0), replace(base,margin_strength=1),
            replace(base,home_advantage=0),replace(base,home_advantage=100),
            replace(base,inactivity_rate=0),replace(base,inactivity_rate=.25),
            replace(base,inactivity_grace_days=365),
            replace(base,initial=1400),replace(base,initial=1600),
            replace(base,margin_strength=0,home_advantage=0,inactivity_rate=0)]

class CalibratedElo:
    def __init__(self,parameters):
        self.parameters = parameters
        self.ratings = defaultdict(lambda: parameters.initial)
        self.last = {}

    def prepare_day(self,teams,date):
        """Apply inactivity once per team before any match of that date."""
        p = self.parameters
        for team in set(teams):
            if team in self.last:
                gap = max(0,(date-self.last[team]).days-p.inactivity_grace_days)
                self.ratings[team] = p.initial+(self.ratings[team]-p.initial)*np.exp(-p.inactivity_rate*gap/365.25)
            else:
                _ = self.ratings[team]

    def update_day(self,rows):
        p = self.parameters
        delta = defaultdict(float)
        for r in rows:
            h,a = r.home_team,r.away_team
            goal_difference = r.elo_home_score-r.elo_away_score
            result = .5 if goal_difference==0 else float(goal_difference>0)
            host = 0 if r.neutral else p.home_advantage*(int(h==r.country)-int(a==r.country))
            expected = 1/(1+10**(-(self.ratings[h]-self.ratings[a]+host)/400))
            k = {'friendly':p.friendly_k,'nations_league':p.nations_k,
                 'continental':p.continental_k,'qualification':p.continental_k,
                 'worldcup':p.worldcup_k,'other_tournament':p.other_k,
                 'non_fifa':p.friendly_k}.get(r.competition_family,p.other_k)
            margin = 1+p.margin_strength*np.log1p(abs(goal_difference))
            change = k*margin*(result-expected)
            delta[h] += change; delta[a] -= change
        for team,value in delta.items(): self.ratings[team] += value
        for r in rows:
            self.last[r.home_team] = self.last[r.away_team] = r.date

def causal_elo(history,parameters):
    state = CalibratedElo(parameters)
    records = []
    for date,day in history.groupby('date',sort=True):
        rows = list(day.itertuples(index=False))
        state.prepare_day([t for r in rows for t in (r.home_team,r.away_team)],date)
        for r in rows:
            records.append({'date':date,'home_team':r.home_team,'away_team':r.away_team,
                            'elo_home':state.ratings[r.home_team],'elo_away':state.ratings[r.away_team],
                            'elo_diff':state.ratings[r.home_team]-state.ratings[r.away_team]})
        state.update_day(rows)
    return pd.DataFrame(records),state

def dated_history(path,boundary):
    with Path(path).open('rb') as stream: frame = before_cutoff_csv(stream,boundary)
    frame['date'] = pd.to_datetime(frame.date)
    for col in ['home_score_90','away_score_90','elo_home_score','elo_away_score']:
        frame[col] = pd.to_numeric(frame[col],errors='coerce')
    for col in ['neutral','goal_training_eligible','duration_assumed']:
        frame[col] = frame[col].str.casefold().eq('true')
    return frame

def semester_rankings(path):
    with zipfile.ZipFile(path) as archive: frame = pd.read_csv(archive.open('fifa_mens_rank.csv'))
    registry = NameRegistry()
    frame['team'] = frame.team.map(registry.normalize)
    frame['available_date'] = [pd.Timestamp(int(year)+(int(semester)==2),1 if int(semester)==2 else 7,1)
                               for year,semester in frame[['date','semester']].itertuples(index=False,name=None)]
    keys = ['team','available_date']
    conflict = frame.groupby(keys)['rank'].nunique().gt(1)
    bad = set(conflict[conflict].index)
    frame = frame[[tuple(x) not in bad for x in frame[keys].itertuples(index=False,name=None)]]
    frame = frame.drop_duplicates(keys)
    return frame[['team','available_date','rank','total.points']].rename(columns={'total.points':'points'})

def backward_rank_join(matches,rankings):
    out = matches.copy()
    for side in ['home','away']:
        left = out[['date',f'{side}_team']].rename(columns={f'{side}_team':'team'}).copy()
        left['_index'] = np.arange(len(left))
        joined = pd.merge_asof(left.sort_values('date'),rankings.sort_values('available_date'),
                               left_on='date',right_on='available_date',by='team',
                               direction='backward',tolerance=pd.Timedelta(days=90),allow_exact_matches=False)
        joined = joined.sort_values('_index')
        for field in ['rank','points','available_date']:
            out[f'fifa_{field}_{side}'] = joined[field].to_numpy()
        out[f'fifa_missing_{side}'] = out[f'fifa_rank_{side}'].isna().astype(int)
    return out

def symmetric_predictions(train,test,features,signs):
    x = train[features].fillna(0).to_numpy(dtype=float)
    xt = test[features].fillna(0).to_numpy(dtype=float)
    y = train.target.to_numpy(dtype=int)
    signs = np.asarray(signs)
    classifier = LogisticRegression(C=1,max_iter=500)
    classifier.fit(np.concatenate([x,x*signs]),np.concatenate([y,2-y]))
    return (classifier.predict_proba(xt)+classifier.predict_proba(xt*signs)[:,::-1])/2

def per_match_metrics(y,p):
    loss = -np.log(np.clip(p[np.arange(len(y)),y],1e-15,1))
    brier = ((p-np.eye(3)[y])**2).sum(axis=1)
    return loss,brier

def block_interval(dates,values,replicas=400,seed=20261012):
    blocks = pd.DataFrame({'block':pd.to_datetime(dates).dt.to_period('Q').astype(str),'value':np.asarray(values)})
    agg = blocks.groupby('block').value.agg(['sum','count']).to_numpy()
    rng = np.random.default_rng(seed)
    indices = rng.integers(0,len(agg),size=(replicas,len(agg)))
    samples = agg[indices,0].sum(axis=1)/agg[indices,1].sum(axis=1)
    return [float(x) for x in np.quantile(samples,[.025,.975])]

def walk_forward(frame,features,signs):
    parts = []
    for start,end in BLOCKS:
        train = frame[(frame.date>='2000-01-01')&(frame.date<start)]
        test = frame[(frame.date>=start)&(frame.date<end)].copy()
        p = symmetric_predictions(train,test,features,signs)
        loss,brier = per_match_metrics(test.target.to_numpy(dtype=int),p)
        parts.append(pd.DataFrame({'date':test.date.to_numpy(),'home_team':test.home_team.to_numpy(),
                                   'away_team':test.away_team.to_numpy(),'block_start':start,
                                   'log_loss':loss,'brier':brier}))
    return pd.concat(parts,ignore_index=True)

def calibrate(root='.',output='reports/feature_design'):
    root,output = Path(root),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    protocol = {'written_at_utc':datetime.now(timezone.utc).isoformat(),'selection_cutoff_exclusive':'2023-01-01',
                'blocks':BLOCKS,'candidates':[asdict(x) for x in parameter_grid()],
                'primary_metric':'Pooled per-match log loss on verified regulation targets.',
                'bootstrap':{'unit':'calendar quarter','replicas':400,'seed':20261012},
                'initial_rating_identifiability':'Common initial rating is translation-invariant for elo_diff; 1500 is a convention, not inferred team strength.',
                'accept_secondary_feature':'Paired log-loss upper 95% CI <0, Brier not worse, better log loss in >=3/4 blocks.',
                'reserved_period':'2023-01-01 through 2026-06-09: not evaluated or used for selection.'}
    (output/'elo_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    history = dated_history(root/'reports/data_preparation/historical_results.csv','2023-01-01')
    scores = []; predictions = {}
    for index,params in enumerate(parameter_grid()):
        print(f'Elo: candidato {index+1}/{len(parameter_grid())}; solo bloques anteriores a 2023',flush=True)
        features,_ = causal_elo(history,params)
        features['elo_scaled'] = features.elo_diff/400
        known = history.goal_training_eligible.to_numpy()
        features = features[known].copy()
        target = history.loc[known]
        features['target'] = np.where(target.home_score_90>target.away_score_90,0,
                                      np.where(target.home_score_90==target.away_score_90,1,2))
        pred = walk_forward(features,['elo_scaled'],[-1])
        predictions[index] = pred
        scores.append({'candidate':index,'log_loss':float(pred.log_loss.mean()),'brier':float(pred.brier.mean()),
                       'log_loss_ci':block_interval(pred.date,pred.log_loss),
                       'brier_ci':block_interval(pred.date,pred.brier),'matches':len(pred),**asdict(params)})
    table = pd.DataFrame(scores)
    best = int(table.sort_values(['log_loss','candidate']).iloc[0].candidate)
    # Exact common-shift duplicates prefer the canonical initial convention.
    if best in (10,11): best = 0
    selected = parameter_grid()[best]
    table.to_csv(output/'elo_calibration.csv',index=False)
    winning = predictions[best]
    winning.to_csv(output/'elo_walk_forward_predictions.csv',index=False)
    folds = winning.groupby('block_start').agg(matches=('log_loss','size'),log_loss=('log_loss','mean'),brier=('brier','mean'))
    folds.to_csv(output/'elo_walk_forward_blocks.csv')
    trained,_ = causal_elo(history,selected)
    known = history.goal_training_eligible.to_numpy()
    trained = trained[known].copy()
    targets = history.loc[known]
    trained['target'] = np.where(targets.home_score_90>targets.away_score_90,0,np.where(targets.home_score_90==targets.away_score_90,1,2))
    ranks = semester_rankings(root/'data/raw/fifa_rank_semesters.zip')
    trained = backward_rank_join(trained,ranks)
    trained['elo_scaled'] = trained.elo_diff/400
    trained['rank_diff'] = (trained.fifa_rank_away-trained.fifa_rank_home).fillna(0)/200
    trained['rank_missing_any'] = ((trained.fifa_missing_home+trained.fifa_missing_away)>0).astype(int)
    enriched = walk_forward(trained,['elo_scaled','rank_diff','rank_missing_any'],[-1,-1,1])
    delta = enriched.log_loss-winning.log_loss
    delta_brier = enriched.brier-winning.brier
    ci = block_interval(winning.date,delta)
    by_block = pd.DataFrame({'block':winning.block_start,'delta':delta}).groupby('block').delta.mean()
    accepted = bool(ci[1]<0 and delta_brier.mean()<=0 and (by_block<0).sum()>=3)
    ranking = {'latest_semester_available_date':str(ranks.available_date.max().date()),
               'latest_observation_semester':'2024 semester 2','last_observation_date':'2024-12-31 (semester end, not actual publication)',
               'both_teams_available_share_validation':float(trained[(trained.date>='2016-01-01')&(trained.date<'2023-01-01')].rank_missing_any.eq(0).mean()),
               'elo_log_loss':float(winning.log_loss.mean()),'elo_plus_ranking_log_loss':float(enriched.log_loss.mean()),
               'paired_log_loss_difference':float(delta.mean()),'paired_difference_ci':ci,
               'elo_brier':float(winning.brier.mean()),'elo_plus_ranking_brier':float(enriched.brier.mean()),
               'blocks_improving':int((by_block<0).sum()),'accepted_secondary_feature':accepted,
               'valid_2026_ranking_available':False,'max_age_days':90,'extrapolation':False}
    (output/'fifa_ablation.json').write_text(json.dumps(ranking,indent=2),encoding='utf-8')
    enriched.to_csv(output/'fifa_walk_forward_predictions.csv',index=False)
    result = {'selected_candidate':best,'parameters':asdict(selected),'selection_completed_at_utc':datetime.now(timezone.utc).isoformat(),
              'protocol_sha256':digest_file(output/'elo_protocol.json'),'max_selection_date':str(history.date.max().date()),
              'reserved_period_evaluated':False,'selected_metrics':scores[best],'fifa':ranking}
    (output/'selected_elo.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    report = f'''# Calibración del estado histórico\n\nConstruyo este estudio retrospectivo con corte deportivo exclusivo 2026-06-10. Seleccioné Elo sin evaluar el periodo reservado desde 2023. Comparé {len(scores)} configuraciones con una logística de una sola variable: diferencia de Elo. Las predicciones se reconcilian con el orden inverso para respetar simetría.\n\n{markdown_table(table[['candidate','log_loss','brier','matches']].rename(columns={'candidate':'Configuración','log_loss':'Log loss','brier':'Brier','matches':'Partidos'}))}\n\nLa configuración seleccionada es {best}. Sus intervalos del 95 % son {scores[best]['log_loss_ci']} para log loss y {scores[best]['brier_ci']} para Brier. Remuestreo trimestres completos con 400 réplicas; no simulo torneos. La rejilla y las reglas se guardaron antes de calcular estas métricas. Seleccionar el mínimo de varias configuraciones introduce optimismo: todavía necesito la prueba reservada para juzgar la mejora.\n\n{markdown_table(folds.reset_index())}\n\n## Inicialización e inactividad\n\nUna puntuación inicial común de 1400, 1500 o 1600 solo desplaza la escala: no distingue la fuerza inicial de las selecciones y no cambia las diferencias. Uso 1500 como convención. La historia completa sirve como calentamiento. La regresión por inactividad reduce la diferencia respecto a ese centro tras el plazo configurado. La rejilla es acotada y no una búsqueda exhaustiva.\n\n## Ranking secundario\n\nEl archivo termina en el segundo semestre de 2024. Asumo disponibilidad desde 2025-01-01, posterior al semestre; esa fecha no es una publicación observada. Exijo antigüedad máxima de 90 días y fecha estrictamente anterior al partido. No hay ranking vigente para 2026.\n\nElo: log loss {ranking['elo_log_loss']:.6f}; Elo con ranking: {ranking['elo_plus_ranking_log_loss']:.6f}. Cambio pareado: {ranking['paired_log_loss_difference']:.6f}, intervalo {ci}. Mejoró en {ranking['blocks_improving']} de cuatro bloques. Aplicando el criterio escrito, {'admito la variable secundaria solo en su rango válido' if accepted else 'descarto el ranking del conjunto principal de variables'}.\n\n## Alcance\n\nEsta operación selecciona parámetros del estado Elo y estudia ranking secundario. No selecciona XGBoost ni una política de duración de amistosos. No evalúa partidos oficiales de 2026 ni congela un pronóstico. No atribuyo estos resultados a una prueba independiente del diseño.\n'''
    (output/'RESULTADOS.md').write_text(report,encoding='utf-8')
    return result

def ablate_rank_points(output):
    """Evaluate rank and points jointly; write protocol before this ablation."""
    output=Path(output)
    protocol={'written_at_utc':datetime.now(timezone.utc).isoformat(),
              'features':['elo_diff / 400','rank_diff / 200','points_diff / points_sum','ranking_missing','points_missing'],
              'fixed_elo_parameters_file':'selected_elo.json','selection_cutoff_exclusive':'2023-01-01',
              'blocks':BLOCKS,'acceptance':'Paired log-loss upper 95% CI < 0; Brier not worse; >=3/4 blocks improve.',
              'context':'Joint rank-and-points check following the rank-only ablation; no held-out results admitted.'}
    (output/'fifa_points_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    frame=pd.read_csv(output/'historical_features.csv',parse_dates=['date'],low_memory=False)
    if (frame.date>=pd.Timestamp('2023-01-01')).any():
        raise ValueError('Reserved dates present in feature ablation')
    frame=frame[frame.goal_training_eligible].copy()
    frame['target']=np.where(frame.home_score_90>frame.away_score_90,0,np.where(frame.home_score_90==frame.away_score_90,1,2))
    frame['elo_scaled']=frame.elo_diff/400
    frame['rank_diff']=(frame.fifa_rank_away-frame.fifa_rank_home).fillna(0)/200
    frame['ranking_missing']=frame.fifa_rank_home.isna()|frame.fifa_rank_away.isna()
    denominator=frame.fifa_points_home+frame.fifa_points_away
    frame['points_diff']=((frame.fifa_points_home-frame.fifa_points_away)/denominator).replace([np.inf,-np.inf],np.nan)
    frame['points_missing']=frame.points_diff.isna().astype(int)
    pred=walk_forward(frame,['elo_scaled','rank_diff','points_diff','ranking_missing','points_missing'],[-1,-1,-1,1,1])
    baseline=pd.read_csv(output/'elo_walk_forward_predictions.csv',parse_dates=['date'])
    if not pred[['date','home_team','away_team']].equals(baseline[['date','home_team','away_team']]):
        raise ValueError('Ablation fixture alignment failed')
    delta=pred.log_loss-baseline.log_loss
    ci=block_interval(pred.date,delta)
    improving=(pd.DataFrame({'block':pred.block_start,'delta':delta}).groupby('block').delta.mean()<0).sum()
    accepted=bool(ci[1]<0 and pred.brier.mean()<=baseline.brier.mean() and improving>=3)
    result={'elo_log_loss':float(baseline.log_loss.mean()),'elo_plus_rank_and_points_log_loss':float(pred.log_loss.mean()),
            'elo_brier':float(baseline.brier.mean()),'elo_plus_rank_and_points_brier':float(pred.brier.mean()),
            'paired_log_loss_difference':float(delta.mean()),'paired_difference_ci':ci,
            'blocks_improving':int(improving),'accepted_secondary_feature':accepted,
            'protocol_sha256':digest_file(output/'fifa_points_protocol.json')}
    pred.to_csv(output/'fifa_points_walk_forward_predictions.csv',index=False)
    (output/'fifa_rank_points_ablation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (output/'RESULTADOS.md').open('a',encoding='utf-8') as stream:
        stream.write(f"\n## Ranking y puntos conjuntamente\n\nAdemás del puesto, contrasté los puntos FIFA, normalizando la diferencia por la suma de puntos para evitar mezclar escalas históricas. Este contraste tiene su propio protocolo fechado antes de ejecutarlo y utiliza los parámetros Elo ya seleccionados. Los faltantes tienen indicadores explícitos.\n\nLog loss: {result['elo_plus_rank_and_points_log_loss']:.6f}; Brier: {result['elo_plus_rank_and_points_brier']:.6f}. Cambio de log loss respecto a Elo: {result['paired_log_loss_difference']:.6f}, intervalo {ci}. Mejoró en {improving} de cuatro bloques. {'Admito el grupo secundario solo en el rango con información válida.' if accepted else 'Descarto también el grupo conjunto de puesto y puntos del modelo principal.'} No uso resultados desde 2023 para esta decisión.\n")
    return result
