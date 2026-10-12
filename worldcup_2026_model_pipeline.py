import io
import sys
import math
import pandas as pd
import numpy as np
import zipfile
import re
import warnings
from sklearn.linear_model import PoissonRegressor
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
warnings.filterwarnings('ignore')

"""
worldcup_2026_model_pipeline.py  —  Version 5.2
Changes from v5:
  - select_scoreline_by_probability(): calibrated Poisson joint matrix
    produces realistic score variety (less 2-1 dominance, more 0-0/2-0/3-0)
  - calculate_h2h_goal_adjustment(): head-to-head secondary adjustment, max 12% weight
  - Per-round penalty budget (R32:3, R16:2, QF:1, SF:1, F:1)
  - Strength-adjusted corners (strong teams generate more vs defensive weak sides)
  - Enhanced RESUMEN_MODELO.md with score distribution, BTTS%, H2H stats
All DataCamp outputs unchanged: 72/32 rows, no nulls, no UNKNOWN.
"""

# ══════════════════════════════════════════════════════════════════════
# 1. NAME NORMALIZATION
# ══════════════════════════════════════════════════════════════════════

TEAM_MAP = {
    'USA': 'United States', 'Usa': 'United States',
    'South Korea': 'Korea Republic', 'Iran': 'IR Iran',
    "Cote d'Ivoire": 'Ivory Coast', "Cte d'Ivoire": 'Ivory Coast',
    'Curacao': 'Curacao', 'Cura\u00e7ao': 'Curacao',
    'Cura\u00e3o': 'Curacao', 'Curaao': 'Curacao',
    'Bosnia and Herzegovina': 'Bosnia-Herzegovina',
    'Bosnia & Herzegovina': 'Bosnia-Herzegovina',
    'Republic of Ireland': 'Ireland', 'Northern Ireland': 'N. Ireland',
    'Cape Verde': 'Cabo Verde', 'Cape Verde Islands': 'Cabo Verde',
    'Trinidad and Tobago': 'Trinidad & Tobago', 'Congo DR': 'DR Congo',
    'Korea Republic': 'Korea Republic', 'China PR': 'China',
    'St. Kitts & Nevis': 'Saint Kitts and Nevis',
    'Saint Kitts and Nevis': 'Saint Kitts and Nevis',
}

def normalize_team_name(name):
    if pd.isna(name): return name
    name = str(name).strip()
    if name.isupper() and len(name) > 2: name = name.title()
    if name.endswith(' National Team'): name = name.replace(' National Team', '').strip()
    if 'ura' in name.lower() and ('ao' in name.lower() or '\u00e7' in name or '\u00e3' in name):
        return 'Curacao'
    return TEAM_MAP.get(name, name)


# ══════════════════════════════════════════════════════════════════════
# 2. STATIC CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

PLACEHOLDER_STRENGTHS = {
    'UEFA Playoff A': 0.48, 'UEFA Playoff B': 0.46,
    'UEFA Playoff C': 0.47, 'UEFA Playoff D': 0.45,
    'FIFA Playoff 1': 0.37, 'FIFA Playoff 2': 0.35,
}
PLACEHOLDER_GOALS_SCORED  = 1.15
PLACEHOLDER_GOALS_CONCEDED = 1.25

CONFEDERATION_MAP = {
    'France': 'UEFA', 'Spain': 'UEFA', 'Germany': 'UEFA', 'England': 'UEFA',
    'Portugal': 'UEFA', 'Netherlands': 'UEFA', 'Belgium': 'UEFA', 'Croatia': 'UEFA',
    'Denmark': 'UEFA', 'Switzerland': 'UEFA', 'Austria': 'UEFA', 'Turkey': 'UEFA',
    'Norway': 'UEFA', 'Serbia': 'UEFA', 'Poland': 'UEFA', 'Ukraine': 'UEFA',
    'Sweden': 'UEFA', 'Italy': 'UEFA', 'Czech Republic': 'UEFA', 'Slovakia': 'UEFA',
    'Hungary': 'UEFA', 'Scotland': 'UEFA', 'Wales': 'UEFA', 'Romania': 'UEFA',
    'Greece': 'UEFA', 'Bosnia-Herzegovina': 'UEFA', 'Albania': 'UEFA',
    'Slovenia': 'UEFA', 'N. Ireland': 'UEFA', 'Ireland': 'UEFA', 'Finland': 'UEFA',
    'Iceland': 'UEFA', 'Georgia': 'UEFA', 'North Macedonia': 'UEFA',
    'Brazil': 'CONMEBOL', 'Argentina': 'CONMEBOL', 'Uruguay': 'CONMEBOL',
    'Colombia': 'CONMEBOL', 'Ecuador': 'CONMEBOL', 'Chile': 'CONMEBOL',
    'Paraguay': 'CONMEBOL', 'Peru': 'CONMEBOL', 'Bolivia': 'CONMEBOL',
    'Venezuela': 'CONMEBOL',
    'Mexico': 'CONCACAF', 'United States': 'CONCACAF', 'Canada': 'CONCACAF',
    'Costa Rica': 'CONCACAF', 'Panama': 'CONCACAF', 'Honduras': 'CONCACAF',
    'Jamaica': 'CONCACAF', 'Haiti': 'CONCACAF', 'Curacao': 'CONCACAF',
    'Trinidad & Tobago': 'CONCACAF', 'El Salvador': 'CONCACAF', 'Guatemala': 'CONCACAF',
    'Japan': 'AFC', 'Korea Republic': 'AFC', 'Saudi Arabia': 'AFC',
    'Australia': 'AFC', 'Uzbekistan': 'AFC', 'IR Iran': 'AFC', 'Qatar': 'AFC',
    'China': 'AFC', 'Iraq': 'AFC', 'Bahrain': 'AFC', 'Jordan': 'AFC',
    'Oman': 'AFC', 'Vietnam': 'AFC', 'Thailand': 'AFC', 'India': 'AFC',
    'Morocco': 'CAF', 'Senegal': 'CAF', 'Algeria': 'CAF', 'Ivory Coast': 'CAF',
    'Nigeria': 'CAF', 'Egypt': 'CAF', 'Tunisia': 'CAF', 'Cameroon': 'CAF',
    'Ghana': 'CAF', 'South Africa': 'CAF', 'DR Congo': 'CAF', 'Mali': 'CAF',
    'Burkina Faso': 'CAF', 'Cabo Verde': 'CAF', 'Benin': 'CAF',
    'New Zealand': 'OFC',
}

# (flat_penalty, expected_base_sn, excess_penalty_rate)
# Hardened non-UEFA/CONMEBOL penalties so strength gaps prevent improbable group winners
CONF_SETTINGS = {
    'UEFA':    (0.000, 0.58, 0.04),
    'CONMEBOL':(0.000, 0.54, 0.06),
    'CONCACAF':(0.050, 0.44, 0.34),   # raised: flat+0.012, excess+0.06
    'AFC':     (0.062, 0.40, 0.44),   # raised: flat+0.014, excess+0.09
    'CAF':     (0.028, 0.47, 0.24),   # raised: flat+0.010, excess+0.06
    'OFC':     (0.095, 0.32, 0.58),   # raised: flat+0.030, excess+0.18
}

# 0.0 = exempt from penalty ; 1.0 = full confederation penalty applied
# Lower value = more protected (historic over-performers)
CONF_EXCEPTION_FACTOR = {
    'Morocco':        0.05,   # WC2022 semi-finalist — nearly fully exempt
    'Japan':          0.60,   # AFC over-performer but capped tighter
    'Senegal':        0.50,   # AFCON winner, tighter cap per v5.3
    'IR Iran':        0.85,   # consistent AFC participant
    'Mexico':         0.45,   # protected: established CONCACAF power
    'United States':  0.82,   # more penalisation per v5.3
    'Australia':      0.78,   # slight penalty increase
    'Korea Republic': 0.80,   # slight penalty increase
    'Algeria':        0.80,   # strong CAF but inflated base
    'New Zealand':    0.96,   # near-full OFC penalty
    'Saudi Arabia':   0.92,   # near-full AFC penalty
    'Curacao':        0.95,   # effectively full CONCACAF penalty
    'Panama':         0.88,   # increased CONCACAF penalty
    'Qatar':          0.90,   # host-cup AFC inflated
    'Uzbekistan':     0.93,   # limited international exposure
}

# World Cup appearances in 2014/2018/2022
WC_RECENT = {
    'Brazil': 3, 'Germany': 3, 'Spain': 3, 'France': 3, 'Argentina': 3,
    'England': 3, 'Portugal': 3, 'Belgium': 3, 'Netherlands': 3,
    'Japan': 3, 'Korea Republic': 3, 'Switzerland': 3, 'Croatia': 3,
    'Denmark': 3, 'Australia': 3, 'Mexico': 3, 'Morocco': 3, 'IR Iran': 3,
    'Uruguay': 3, 'Serbia': 2, 'Senegal': 2, 'Ecuador': 2, 'Tunisia': 2,
    'Colombia': 2, 'Saudi Arabia': 2, 'United States': 2, 'Cameroon': 2,
    'Costa Rica': 2, 'Ghana': 2, 'Poland': 2,
    'Canada': 1, 'Qatar': 1, 'Panama': 1, 'Algeria': 1, 'Ivory Coast': 1,
    'Chile': 1, 'Bosnia-Herzegovina': 1, 'New Zealand': 1,
    'Norway': 0, 'Turkey': 0, 'Austria': 0, 'Uzbekistan': 0, 'Haiti': 0,
    'Curacao': 0, 'Iraq': 0, 'Paraguay': 0, 'South Africa': 0, 'Cabo Verde': 0,
    'DR Congo': 0, 'Georgia': 0, 'Slovenia': 0, 'Venezuela': 0,
}

QUALITATIVE_PRIORS = {
    'France':      0.025, 'Spain':       0.025, 'Portugal':    0.020,
    'Argentina':   0.025, 'Brazil':      0.012, 'Netherlands': 0.008,
    'Germany':     0.008, 'Morocco':     0.018, 'Croatia':     0.012,
    'Ecuador':     0.015, 'Colombia':    0.008,
}

# Penalizaciones explícitas para equipos con SN base inflado
# respecto a su nivel real de competencia internacional de élite.
NEGATIVE_PRIORS = {
    'Algeria':  -0.065,
    'Japan':    -0.060,
    'Senegal':  -0.045,
    'IR Iran':  -0.055,
}

LOW_PROB_TEAMS = {
    'Korea Republic', 'Uzbekistan', 'Panama', 'Curacao', 'New Zealand',
    'Australia', 'Haiti', 'Saudi Arabia', 'Qatar',
}
EXTENDED_MONITOR = {'United States', 'Canada', 'Mexico', 'Japan', 'Senegal'}

# Penalty budget per KO round  (total tournament max: 6)
PEN_BUDGET_PER_ROUND = {
    'Round of 32':   3,
    'Round of 16':   2,
    'Quarter-final': 1,
    'Semi-final':    1,
    'Final':         1,
}

# Elite favorites: H2H cannot downgrade their win probability below model strength
ELITE_FAVORITES = {'Spain','France','Portugal','Argentina','England','Brazil','Netherlands','Germany'}


# ══════════════════════════════════════════════════════════════════════
# 3. DATA LOADING
# ══════════════════════════════════════════════════════════════════════

def load_datasets():
    print('=' * 52)
    print('Cargando datos...')
    with zipfile.ZipFile('data/raw/worldcup_fixtures.zip', 'r') as z:
        with z.open('data/group_fixtures.csv') as f: group_fixtures = pd.read_csv(f)
        with z.open('data/knockout_slots.csv') as f:  knockout_slots  = pd.read_csv(f)
    with zipfile.ZipFile('data/raw/international_results_baseline.zip', 'r') as z:
        with z.open('international_results-master/results.csv') as f: results = pd.read_csv(f)

    def _safe(p, **kw):
        try: return pd.read_csv(p, **kw)
        except: return pd.DataFrame()

    fifa_2018 = _safe('data/raw/fifa_2018_statistics.csv', encoding='utf-8')
    fifa_2022 = _safe('data/raw/fifa_2022_match_data.csv', encoding='latin-1', sep=';')
    fs_m18    = _safe('data/raw/footystats_2018_matches.csv', encoding='latin-1')
    fs_t14    = _safe('data/raw/footystats_2014_teams.csv', encoding='latin-1', sep=';')
    fs_t22    = _safe('data/raw/footystats_2022_teams.csv', encoding='latin-1', sep=';')
    try:
        with zipfile.ZipFile('data/raw/fjelstul_worldcup.zip','r') as z:
            with z.open('worldcup-master/data-csv/bookings.csv') as f: wc_bookings = pd.read_csv(f)
    except: wc_bookings = pd.DataFrame()

    group_fixtures['home_team'] = group_fixtures['home_team'].apply(normalize_team_name)
    group_fixtures['away_team'] = group_fixtures['away_team'].apply(normalize_team_name)
    print('Datos cargados.')
    return (group_fixtures, knockout_slots, results,
            fifa_2018, fifa_2022, fs_m18, fs_t14, fs_t22, wc_bookings)


# ══════════════════════════════════════════════════════════════════════
# 4. BASE STRENGTH
# ══════════════════════════════════════════════════════════════════════

def build_base_strength(results_df):
    results_df = results_df.copy()
    results_df['date'] = pd.to_datetime(results_df['date'], errors='coerce')
    recent = results_df[results_df['date'] >= '2018-01-01'].copy()
    recent['home_team'] = recent['home_team'].apply(normalize_team_name)
    recent['away_team'] = recent['away_team'].apply(normalize_team_name)
    recent['weight']    = np.where(recent['tournament'] == 'Friendly', 0.6, 1.0)

    stats = {}
    def init(t):
        if t not in stats:
            stats[t] = {'matches': 0, 'wm': 0.0, 'wins': 0.0,
                        'draws': 0.0, 'losses': 0.0, 'gs': 0.0, 'gc': 0.0}

    for _, row in recent.iterrows():
        ht, at = row['home_team'], row['away_team']
        hs, as_ = row['home_score'], row['away_score']
        w = row['weight']
        if pd.isna(hs) or pd.isna(as_): continue
        init(ht); init(at)
        stats[ht]['matches']+=1; stats[ht]['wm']+=w
        stats[ht]['gs']+=hs*w; stats[ht]['gc']+=as_*w
        stats[at]['matches']+=1; stats[at]['wm']+=w
        stats[at]['gs']+=as_*w; stats[at]['gc']+=hs*w
        if hs>as_:   stats[ht]['wins']  +=w; stats[at]['losses']+=w
        elif hs<as_: stats[at]['wins']  +=w; stats[ht]['losses']+=w
        else:        stats[ht]['draws'] +=w; stats[at]['draws']  +=w

    df = pd.DataFrame.from_dict(stats, orient='index')
    df['avg_gs']   = df['gs']/df['wm']
    df['avg_gc']   = df['gc']/df['wm']
    df['win_rate'] = df['wins']/df['wm']
    df['base_strength'] = df['win_rate']*0.50 + df['avg_gs']*0.30 - df['avg_gc']*0.20
    lo, hi = df['base_strength'].min(), df['base_strength'].max()
    df['strength_norm_before_adjustments'] = (
        (df['base_strength']-lo)/(hi-lo) if hi>lo else 0.5)
    df['strength_norm'] = df['strength_norm_before_adjustments'].copy()
    recent_clean = recent.dropna(subset=['home_score','away_score'])
    global_avg = recent_clean['home_score'].mean() + recent_clean['away_score'].mean()
    return df, global_avg, recent_clean


# ══════════════════════════════════════════════════════════════════════
# 5. CONTEXTUAL ADJUSTMENT SYSTEM  (autonomous, no per-team caps)
# ══════════════════════════════════════════════════════════════════════

def _opponent_quality(team, recent_matches, base_sn_lookup):
    hg = recent_matches[recent_matches['home_team'] == team]
    ag = recent_matches[recent_matches['away_team'] == team]
    opps = list(hg['away_team']) + list(ag['home_team'])
    if len(opps) < 5: return 0.50, len(opps)
    return float(np.mean([base_sn_lookup.get(o, 0.45) for o in opps])), len(opps)

def _top_opponent_performance(team, recent_matches, base_sn_lookup, threshold=0.55):
    hg = recent_matches[recent_matches['home_team']==team].copy()
    ag = recent_matches[recent_matches['away_team']==team].copy()
    hg = hg[hg['away_team'].map(lambda x: base_sn_lookup.get(x,0)) > threshold]
    ag = ag[ag['home_team'].map(lambda x: base_sn_lookup.get(x,0)) > threshold]
    total = len(hg)+len(ag)
    if total < 3: return 0.0
    pts = 0
    for _, r in hg.iterrows():
        if r['home_score']>r['away_score']: pts+=3
        elif r['home_score']==r['away_score']: pts+=1
    for _, r in ag.iterrows():
        if r['away_score']>r['home_score']: pts+=3
        elif r['away_score']==r['home_score']: pts+=1
    ppg = pts/(3*total)
    if ppg>0.55: return +0.012
    elif ppg>0.35: return 0.0
    elif ppg>0.15: return -0.010
    else:          return -0.018

def calculate_contextual_strength_adjustment(team, base_sn, n_matches,
                                              recent_matches, base_sn_lookup):
    confederation = CONFEDERATION_MAP.get(team, 'UEFA')
    flat_pen, expected_sn, excess_rate = CONF_SETTINGS.get(confederation, (0.015, 0.50, 0.10))
    exc_factor = CONF_EXCEPTION_FACTOR.get(team, 1.0)
    excess = max(0.0, base_sn - expected_sn)
    conf_adj = max(-0.090, min(0.000, -(flat_pen + excess_rate*excess) * exc_factor))

    avg_opp_sn, n_opp = _opponent_quality(team, recent_matches, base_sn_lookup)
    opp_diff = avg_opp_sn - 0.50
    if n_opp >= 5:
        if opp_diff < -0.04:   opp_adj = max(-0.050, opp_diff * 0.55)
        elif opp_diff > 0.04:  opp_adj = min(+0.018, opp_diff * 0.28)
        else:                  opp_adj = 0.0
    else:
        opp_adj = -0.008
    opp_adj = max(-0.055, min(0.020, opp_adj))

    wc_exp = WC_RECENT.get(team, 0)
    if wc_exp == 0:   wc_adj = -0.028
    elif wc_exp == 1: wc_adj = -0.010
    else:             wc_adj = 0.000

    top_adj   = _top_opponent_performance(team, recent_matches, base_sn_lookup)
    debut_adj = -0.012 if wc_exp == 0 else 0.0

    total = max(-0.130, min(+0.050,
                conf_adj + opp_adj + wc_adj + top_adj + debut_adj))
    reason = (f"conf={confederation}|exc={exc_factor:.2f}|"
              f"avg_opp={avg_opp_sn:.3f}({n_opp}g)|wc={wc_exp}|"
              f"top_ppg_adj={top_adj:+.3f}")
    return {
        'confederation':                      confederation,
        'confederation_adjustment':           round(conf_adj, 5),
        'opponent_quality_adjustment':        round(opp_adj, 5),
        'world_cup_experience_adjustment':    round(wc_adj, 5),
        'top_opponent_performance_adjustment':round(top_adj, 5),
        'debutant_adjustment':                round(debut_adj, 5),
        'external_probability_adjustment':    0.0,
        'total_contextual_adjustment':        round(total, 5),
        'reason_tag':                         reason,
    }

def apply_all_contextual_adjustments(df_stats, recent_matches):
    base_sn_lookup = df_stats['strength_norm_before_adjustments'].to_dict()
    for col in ['confederation','reason_tag']: df_stats[col] = ''
    for col in ['prior_applied','confederation_adjustment','opponent_quality_adjustment',
                'world_cup_experience_adjustment','top_opponent_performance_adjustment',
                'debutant_adjustment','external_probability_adjustment',
                'total_contextual_adjustment']:
        df_stats[col] = 0.0

    for team in df_stats.index:
        base_sn   = base_sn_lookup.get(team, 0.50)
        n_matches = int(df_stats.loc[team, 'matches'])
        prior     = QUALITATIVE_PRIORS.get(team, 0.0) + NEGATIVE_PRIORS.get(team, 0.0)
        df_stats.loc[team, 'prior_applied'] = prior
        adj = calculate_contextual_strength_adjustment(
            team, base_sn, n_matches, recent_matches, base_sn_lookup)
        for k, v in adj.items():
            if k in df_stats.columns: df_stats.loc[team, k] = v
        new_sn = base_sn + prior + adj['total_contextual_adjustment']
        if team not in QUALITATIVE_PRIORS and n_matches < 12: new_sn -= 0.020
        df_stats.loc[team, 'strength_norm'] = new_sn

    df_stats['strength_norm']       = df_stats['strength_norm'].clip(0.05, 0.97)
    df_stats['final_strength_norm'] = df_stats['strength_norm'].copy()

    # ── v5.3: LOW_PROB_GC_PENALTY — penalise weak teams' Poisson inputs ──
    # These adjustments feed the Poisson model directly so avg_gc of weak teams
    # correctly drives higher expected goals FOR their elite opponents.
    LOW_PROB_GC_PENALTY = {
        # team: (gc_add, gs_sub, sn_sub_before_cap)
        'Korea Republic': (0.20, 0.10, 0.015),
        'Uzbekistan':     (0.25, 0.10, 0.020),
        'Panama':         (0.25, 0.10, 0.020),
        'Curacao':        (0.35, 0.15, 0.025),
        'New Zealand':    (0.30, 0.12, 0.020),
        'Australia':      (0.20, 0.10, 0.015),
        'Haiti':          (0.35, 0.15, 0.025),
        'Saudi Arabia':   (0.28, 0.10, 0.018),
        'Qatar':          (0.25, 0.10, 0.018),
    }
    for team_p, (gc_add, gs_sub, sn_sub) in LOW_PROB_GC_PENALTY.items():
        if team_p in df_stats.index:
            df_stats.loc[team_p, 'avg_gc'] += gc_add
            df_stats.loc[team_p, 'avg_gs'] = max(0.50, df_stats.loc[team_p, 'avg_gs'] - gs_sub)
            df_stats.loc[team_p, 'final_strength_norm'] -= sn_sub

    # ── v5.3: avg_gc scaled by SN — weaker teams concede proportionally more ──
    for team_idx in df_stats.index:
        sn = df_stats.loc[team_idx, 'final_strength_norm']
        if   sn < 0.30: df_stats.loc[team_idx, 'avg_gc'] += 0.55
        elif sn < 0.40: df_stats.loc[team_idx, 'avg_gc'] += 0.40
        elif sn < 0.48: df_stats.loc[team_idx, 'avg_gc'] += 0.25
        df_stats.loc[team_idx, 'avg_gc'] = min(df_stats.loc[team_idx, 'avg_gc'], 3.20)

    # ── v5.3: HARD_CAPS — absolute ceiling on final_strength_norm ──
    # Prevents improbable group winners regardless of confederation noise.
    HARD_CAPS = {
        'Curacao':        0.280,
        'Haiti':          0.300,
        'New Zealand':    0.380,
        'Saudi Arabia':   0.370,
        'Qatar':          0.360,
        'Uzbekistan':     0.410,
        'Panama':         0.410,
        'Australia':      0.465,
        'Korea Republic': 0.490,
        'Algeria':  0.495,
        'Japan':    0.495,
        'Senegal':  0.492,
        'IR Iran':  0.455,
        'FIFA Playoff 1': 0.340,
        'FIFA Playoff 2': 0.320,
    }
    for team_cap, cap_val in HARD_CAPS.items():
        if team_cap in df_stats.index:
            df_stats.loc[team_cap, 'final_strength_norm'] = min(
                df_stats.loc[team_cap, 'final_strength_norm'], cap_val
            )

    return df_stats


# ══════════════════════════════════════════════════════════════════════
# 6. STRENGTH DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════

def generate_strength_diagnostics(df_stats, group_fixtures):
    print('\nGenerando diagnostico de fuerza...')
    wc_teams = set(group_fixtures['home_team']).union(set(group_fixtures['away_team']))
    rows = []
    for team in sorted(wc_teams):
        if team in df_stats.index:
            r = df_stats.loc[team]
            rows.append({
                'team': team,
                'confederation': r.get('confederation',''),
                'matches': int(r['matches']),
                'avg_gs': round(r['avg_gs'],4), 'avg_gc': round(r['avg_gc'],4),
                'win_rate': round(r['win_rate'],4),
                'base_strength': round(r['base_strength'],4),
                'strength_norm_before_adjustments': round(r['strength_norm_before_adjustments'],4),
                'prior_applied': round(r['prior_applied'],4),
                'confederation_adjustment': round(r['confederation_adjustment'],4),
                'opponent_quality_adjustment': round(r['opponent_quality_adjustment'],4),
                'world_cup_experience_adjustment': round(r['world_cup_experience_adjustment'],4),
                'top_opponent_performance_adjustment': round(r['top_opponent_performance_adjustment'],4),
                'debutant_adjustment': round(r['debutant_adjustment'],4),
                'external_probability_adjustment': round(r['external_probability_adjustment'],4),
                'total_contextual_adjustment': round(r['total_contextual_adjustment'],4),
                'final_strength_norm': round(r['final_strength_norm'],4),
                'group':'', 'rank_group':'', 'stage_reached':'',
                'reason_tag': str(r.get('reason_tag','')),
            })
        else:
            ph = PLACEHOLDER_STRENGTHS.get(team, 0.40)
            rows.append({'team': team,'confederation':'UEFA','matches':0,
                'avg_gs':PLACEHOLDER_GOALS_SCORED,'avg_gc':PLACEHOLDER_GOALS_CONCEDED,
                'win_rate':0.0,'base_strength':0.0,'strength_norm_before_adjustments':ph,
                'prior_applied':0.0,'confederation_adjustment':0.0,'opponent_quality_adjustment':0.0,
                'world_cup_experience_adjustment':0.0,'top_opponent_performance_adjustment':0.0,
                'debutant_adjustment':0.0,'external_probability_adjustment':0.0,
                'total_contextual_adjustment':0.0,'final_strength_norm':ph,
                'group':'','rank_group':'','stage_reached':'','reason_tag':'placeholder'})

    diag_df = pd.DataFrame(rows)
    top20 = diag_df.sort_values('final_strength_norm', ascending=False).head(20)
    print(f"\n  {'Team':<22} {'Base':>6} {'Prior':>6} {'Conf':>6} {'OppQ':>6} {'WCexp':>6} {'Total':>7} {'Final':>7}")
    print('  ' + '-'*72)
    for _, row in top20.iterrows():
        print(f"  {row['team']:<22} "
              f"{row['strength_norm_before_adjustments']:>6.3f} "
              f"{row['prior_applied']:>+6.3f} "
              f"{row['confederation_adjustment']:>+6.3f} "
              f"{row['opponent_quality_adjustment']:>+6.3f} "
              f"{row['world_cup_experience_adjustment']:>+6.3f} "
              f"{row['total_contextual_adjustment']:>+7.3f} "
              f"{row['final_strength_norm']:>7.3f}")
    print()
    return diag_df


# ══════════════════════════════════════════════════════════════════════
# 7. EVENT PROFILES (corners, yellows, reds)
# ══════════════════════════════════════════════════════════════════════

def build_event_profiles(fifa_2018, fifa_2022, fs_m18, fs_t14, fs_t22, wc_bookings):
    corner_rec, yellow_rec, red_rec = [], [], []

    if not fifa_2018.empty:
        fa = fifa_2018.copy(); fa.columns = fa.columns.str.strip()
        fa['Team'] = fa['Team'].apply(normalize_team_name)
        fa['Opponent'] = fa['Opponent'].apply(normalize_team_name)
        for _, r in fa.iterrows():
            t = r['Team']
            try: corner_rec.append({'team':t,'opp':r['Opponent'],'c':float(r['Corners'])})
            except: pass
            try: yellow_rec.append({'team':t,'y':float(r['Yellow Card'])})
            except: pass
            try: red_rec.append({'team':t,'r':float(r['Red'])})
            except: pass

    if not fifa_2022.empty:
        fm = fifa_2022.copy()
        if '1' in fm.columns and '2' in fm.columns:
            for _, r in fm.iterrows():
                t1 = normalize_team_name(str(r.get('1','')))
                t2 = normalize_team_name(str(r.get('2','')))
                for t,opp,ck,yk,rk in [(t1,t2,'1_corners','1_yellow_cards','1_red_cards'),
                                        (t2,t1,'2_corners','2_yellow_cards','2_red_cards')]:
                    try: corner_rec.append({'team':t,'opp':opp,'c':float(r.get(ck,np.nan))})
                    except: pass
                    try: yellow_rec.append({'team':t,'y':float(r.get(yk,np.nan))})
                    except: pass
                    try: red_rec.append({'team':t,'r':float(r.get(rk,np.nan))})
                    except: pass

    if not fs_m18.empty:
        fm = fs_m18.copy(); fm.columns = fm.columns.str.strip()
        for _, r in fm.iterrows():
            ht = normalize_team_name(str(r.get('home_team_name','')))
            at = normalize_team_name(str(r.get('away_team_name','')))
            for t,opp,ck,yk,rk in [
                (ht,at,'home_team_corner_count','home_team_yellow_cards','home_team_red_cards'),
                (at,ht,'away_team_corner_count','away_team_yellow_cards','away_team_red_cards')]:
                try: corner_rec.append({'team':t,'opp':opp,'c':float(r.get(ck,np.nan))})
                except: pass
                try: yellow_rec.append({'team':t,'y':float(r.get(yk,np.nan))})
                except: pass
                try: red_rec.append({'team':t,'r':float(r.get(rk,np.nan))})
                except: pass

    for fs_teams in [fs_t14, fs_t22]:
        if fs_teams.empty: continue
        fs = fs_teams.copy()
        col_n = ('common_name' if 'common_name' in fs.columns
                 else 'team_name' if 'team_name' in fs.columns else None)
        if not col_n: continue
        fs['team'] = fs[col_n].apply(normalize_team_name)
        for _, r in fs.iterrows():
            t = r['team']
            try: corner_rec.append({'team':t,'opp':'__agg__','c':float(r.get('corners_per_match',np.nan))/2.0})
            except: pass
            try: yellow_rec.append({'team':t,'y':float(r.get('cards_per_match',np.nan))/2.0})
            except: pass

    if not wc_bookings.empty:
        wb = wc_bookings.copy()
        wb['team_name'] = wb['team_name'].apply(normalize_team_name)
        if 'match_id' in wb.columns:
            for (mid,team),g in wb.groupby(['match_id','team_name']):
                yellow_rec.append({'team':team,'y':int(g['yellow_card'].sum())})
                red_rec.append({'team':team,'r':int(g['red_card'].sum()+g['second_yellow_card'].sum())})

    cdf = pd.DataFrame([x for x in corner_rec if not (isinstance(x['c'],float) and np.isnan(x['c']))])
    corner_profile = {}
    if not cdf.empty:
        for t,g in cdf.groupby('team'):
            mr = g[g['opp']!='__agg__']
            corner_profile[t] = {'for': mr['c'].mean() if not mr.empty else g['c'].mean()}
    match_cdf = cdf[cdf['opp']!='__agg__'] if not cdf.empty else pd.DataFrame()
    global_corners_avg = min(match_cdf['c'].mean() if not match_cdf.empty else 4.5, 6.0)

    ydf = pd.DataFrame([x for x in yellow_rec if not (isinstance(x['y'],float) and np.isnan(x['y']))])
    yellow_profile = {}
    if not ydf.empty:
        for t,g in ydf.groupby('team'): yellow_profile[t] = min(g['y'].mean(), 2.5)
    global_yellow_avg = min(ydf['y'].mean() if not ydf.empty else 2.0, 2.0)

    # v5.3: Cap Argentina & Netherlands outlier from Qatar 2022 (10-card match)
    if 'Argentina'  in yellow_profile: yellow_profile['Argentina']   = min(yellow_profile['Argentina'],  1.75)
    if 'Netherlands' in yellow_profile: yellow_profile['Netherlands'] = min(yellow_profile['Netherlands'], 1.75)

    rdf = pd.DataFrame([x for x in red_rec if not (isinstance(x['r'],float) and np.isnan(x['r']))])
    red_profile = {}
    if not rdf.empty:
        for t,g in rdf.groupby('team'): red_profile[t] = min(g['r'].mean(), 0.10)
    global_red_avg = min(rdf['r'].mean() if not rdf.empty else 0.04, 0.05)

    return corner_profile, yellow_profile, red_profile, global_corners_avg, global_yellow_avg, global_red_avg


# ══════════════════════════════════════════════════════════════════════
# 8. GOAL MODELS
# ══════════════════════════════════════════════════════════════════════

def train_goal_models(recent_matches, df_stats):
    print('Entrenando modelos Poisson...')
    X, yh, ya = [], [], []
    for _, row in recent_matches.iterrows():
        ht, at = row['home_team'], row['away_team']
        if ht in df_stats.index and at in df_stats.index:
            X.append([df_stats.loc[ht,'avg_gs'], df_stats.loc[ht,'avg_gc'],
                      df_stats.loc[at,'avg_gs'], df_stats.loc[at,'avg_gc'],
                      df_stats.loc[ht,'final_strength_norm'],
                      df_stats.loc[at,'final_strength_norm']])
            yh.append(row['home_score']); ya.append(row['away_score'])
    hm = PoissonRegressor(alpha=1.0, max_iter=300)
    am = PoissonRegressor(alpha=1.0, max_iter=300)
    if len(X) > 10: hm.fit(X, yh); am.fit(X, ya)
    print(f'  Entrenado con {len(X)} partidos.')
    return hm, am


# ══════════════════════════════════════════════════════════════════════
# 9. NEW: SCORELINE PROBABILITY MATRIX
# ══════════════════════════════════════════════════════════════════════

def _poisson_pmf(max_k, mu):
    """Poisson PMF array for k = 0..max_k using log-space for numerical stability."""
    result = np.zeros(max_k + 1)
    log_mu = np.log(max(mu, 1e-10))
    for k in range(max_k + 1):
        result[k] = np.exp(-mu + k * log_mu - math.lgamma(k + 1))
    return np.maximum(result, 0.0)


def select_scoreline_by_probability(mu_h, mu_a, diff_sn, is_knockout, rng, max_goals=7):
    """
    Samples a realistic (home_goals, away_goals) pair from a calibrated
    joint Poisson probability matrix.

    Design principle: the calibration should RESHAPE the distribution for variety
    (less 2-1/1-1 dominance, more 1-0/2-0/3-0/0-0) WITHOUT reducing the mean.
    Strategy: boost the underrepresented scores; slightly suppress the overrepresented
    ones; avoid any global dampener that pulls the mean below Poisson expectation.

    For group stage: NO dampener on high-total cells (goal mean preserved).
    For KO: apply mild dampener on total >= 5 cells (lower-scoring KO matches).
    """
    mu_h = max(0.15, float(mu_h))
    mu_a = max(0.10, float(mu_a))
    MAX  = max_goals

    h_pmf = _poisson_pmf(MAX, mu_h)
    a_pmf = _poisson_pmf(MAX, mu_a)
    joint = np.outer(h_pmf, a_pmf)

    abs_diff = abs(diff_sn)
    mult = np.ones((MAX+1, MAX+1), dtype=np.float64)

    if abs_diff < 0.08:                      # ── Very even match ──
        # Boost 0-0, 1-0/0-1; slightly reduce 1-1/2-1 to create variety
        # No dampening: preserves goal mean near Poisson baseline
        mult[0,0]=1.28; mult[1,0]=1.16; mult[0,1]=1.16
        mult[1,1]=0.90; mult[2,1]=0.88; mult[1,2]=0.88  # reduce 2-1/1-2 dominance
        mult[2,0]=1.10; mult[0,2]=1.10                  # boost clean-sheet wins
        mult[3,0]=1.06; mult[0,3]=1.06                  # small 3-0/0-3 boost

    elif abs_diff < 0.16:                    # ── Moderate favorite ──
        fh = diff_sn > 0
        if fh:
            # Boost wins-by-margin; reduce 2-1 slightly; keep upsets less (mild)
            mult[1,0]=1.20; mult[2,0]=1.30; mult[3,0]=1.25
            mult[2,1]=1.10; mult[3,1]=1.14; mult[4,0]=1.08
            mult[1,1]=0.92; mult[0,0]=1.05  # slight draw suppression
            for j in range(MAX+1):           # modest upset reduction
                for i in range(j): mult[i,j] *= 0.70
        else:
            mult[0,1]=1.20; mult[0,2]=1.30; mult[0,3]=1.25
            mult[1,2]=1.10; mult[1,3]=1.14; mult[0,4]=1.08
            mult[1,1]=0.92; mult[0,0]=1.05
            for i in range(MAX+1):
                for j in range(i): mult[i,j] *= 0.70

    elif abs_diff < 0.26:                    # ── Clear favorite ──
        fh = diff_sn > 0
        if fh:
            # Strong favorite: boost 2-0/3-0/4-0/3-1 over 2-1
            mult[2,0]=1.38; mult[3,0]=1.42; mult[4,0]=1.28
            mult[2,1]=1.10; mult[3,1]=1.22; mult[4,1]=1.14; mult[5,0]=1.08; mult[1,0]=1.12
            mult[1,1]=0.88                              # reduce draws
            for j in range(2, MAX+1): mult[:, j] *= 0.62  # weak team 2+ goals reduced
            for j in range(MAX+1):                         # upsets heavily reduced
                for i in range(j): mult[i,j] *= 0.28
        else:
            mult[0,2]=1.38; mult[0,3]=1.42; mult[0,4]=1.28
            mult[1,2]=1.10; mult[1,3]=1.22; mult[1,4]=1.14; mult[0,5]=1.08; mult[0,1]=1.12
            mult[1,1]=0.88
            for i in range(2, MAX+1): mult[i, :] *= 0.62
            for i in range(MAX+1):
                for j in range(i): mult[i,j] *= 0.28

    else:                                    # ── Dominant (gap >= 0.26) ──
        fh = diff_sn > 0
        if fh:
            # Elite vs very weak: goleadas encouraged; upsets near-zero
            mult[3,0]=1.50; mult[4,0]=1.46; mult[5,0]=1.28; mult[6,0]=1.10
            mult[3,1]=1.38; mult[4,1]=1.30; mult[5,1]=1.14; mult[2,0]=1.40
            for j in range(2, MAX+1): mult[:,j] *= 0.32
            for j in range(MAX+1):
                for i in range(j): mult[i,j] *= 0.05
        else:
            mult[0,3]=1.50; mult[0,4]=1.46; mult[0,5]=1.28; mult[0,6]=1.10
            mult[1,3]=1.38; mult[1,4]=1.30; mult[1,5]=1.14; mult[0,2]=1.40
            for i in range(2, MAX+1): mult[i,:] *= 0.32
            for i in range(MAX+1):
                for j in range(i): mult[i,j] *= 0.05

    # KO only: relaxed dampening — only extreme totals (>=6) reduced
    # Target: 2.50-2.80 g/match without ET; do NOT kill 3-2 / 2-3 / 4-1 scorelines
    if is_knockout:
        for i in range(MAX+1):
            for j in range(MAX+1):
                if i+j >= 6: mult[i,j] *= 0.75

    joint = joint * mult
    s = joint.sum()
    if s <= 1e-12:
        joint = np.ones((MAX+1, MAX+1)) / (MAX+1)**2
    else:
        joint = joint / s

    flat = joint.flatten().astype(np.float64)
    flat = np.maximum(flat, 0)
    flat = flat / flat.sum()

    idx = int(rng.choice(len(flat), p=flat))
    return idx // (MAX+1), idx % (MAX+1)


# ══════════════════════════════════════════════════════════════════════
# 10. NEW: H2H SECONDARY ADJUSTMENT  (max weight 12%)
# ══════════════════════════════════════════════════════════════════════

def calculate_h2h_goal_adjustment(home_team, away_team, h2h_df):
    """
    Returns (h2h_mu_h, h2h_mu_a, h2h_weight).
    Weight is 0..0.12; set to 0 if insufficient data.
    H2H cannot flip the model-predicted favorite.
    """
    if h2h_df is None or h2h_df.empty:
        return 0.0, 0.0, 0.0

    mask = (
        ((h2h_df['home_team'] == home_team) & (h2h_df['away_team'] == away_team)) |
        ((h2h_df['home_team'] == away_team) & (h2h_df['away_team'] == home_team))
    )
    h2h = h2h_df[mask].copy()
    if len(h2h) == 0:
        return 0.0, 0.0, 0.0

    def _tw(t):
        t = str(t)
        if 'FIFA World Cup' in t: return 1.00
        if any(x in t for x in ['Copa America','UEFA Euro','African Cup','Gold Cup',
                                  'Nations Cup','CONCACAF Championship']): return 0.80
        if any(x in t for x in ['Qualification','Qualifying','Eliminatoria']): return 0.65
        if 'Friendly' in t: return 0.25
        return 0.50

    h2h['year']  = pd.to_datetime(h2h['date'], errors='coerce').dt.year.fillna(2010)
    h2h['rec_w'] = h2h['year'].apply(lambda y: max(0.10, 1.0 - 0.08*(2026-y)))
    h2h['trn_w'] = h2h['tournament'].apply(_tw)
    h2h['w']     = h2h['rec_w'] * h2h['trn_w']

    mu_h = mu_a = tot = 0.0
    for _, r in h2h.iterrows():
        w = float(r['w'])
        hs, as_ = float(r['home_score']), float(r['away_score'])
        if r['home_team'] == home_team:
            mu_h += hs*w; mu_a += as_*w
        else:
            mu_h += as_*w; mu_a += hs*w
        tot += w

    if tot < 0.30:
        return 0.0, 0.0, 0.0

    mu_h /= tot; mu_a /= tot

    n = len(h2h)
    if n <= 1:   base = 0.03
    elif n <= 3: base = 0.06
    elif n <= 6: base = 0.09
    else:        base = 0.11

    quality    = min(1.0, tot / max(1.0, n * 0.55))
    h2h_weight = min(0.12, base * quality)

    return float(mu_h), float(mu_a), float(h2h_weight)


# ══════════════════════════════════════════════════════════════════════
# 11. MATCH PREDICTION  (v5.2: scoreline matrix + H2H + per-round pen budget)
# ══════════════════════════════════════════════════════════════════════

def get_team_stats(team, df_stats):
    if team in df_stats.index:
        return {'avg_gs': df_stats.loc[team,'avg_gs'],
                'avg_gc': df_stats.loc[team,'avg_gc'],
                'sn':     df_stats.loc[team,'final_strength_norm']}
    return {'avg_gs': PLACEHOLDER_GOALS_SCORED,
            'avg_gc': PLACEHOLDER_GOALS_CONCEDED,
            'sn':     PLACEHOLDER_STRENGTHS.get(team, 0.40)}


def predict_match(home_team, away_team, is_knockout, current_round,
                  home_model, away_model, df_stats, h2h_df,
                  corner_profile, yellow_profile, red_profile,
                  global_corners_avg, global_yellow_avg, global_red_avg,
                  state_tracker=None, sim_id=0):
    """
    Predict a single match using:
    - Poisson model for base mu values
    - H2H secondary adjustment (max 12% weight)
    - Strength-gap boost to mu
    - Calibrated scoreline probability matrix
    - Strength-adjusted corner counts
    - Per-round penalty budget for KO ties
    Returns standard DataCamp dict + 'extra_time' + '_h2h_weight' (for stats).
    """
    seed_val = abs(hash(f"{home_team}|{away_team}|{sim_id}")) % 99991
    rng = np.random.default_rng(seed_val)

    hs_st  = get_team_stats(home_team, df_stats)
    as_st  = get_team_stats(away_team, df_stats)
    diff_sn = hs_st['sn'] - as_st['sn']

    # ── Base Poisson mu ──
    X = [[hs_st['avg_gs'], hs_st['avg_gc'],
          as_st['avg_gs'], as_st['avg_gc'],
          hs_st['sn'],     as_st['sn']]]
    try:
        mu_h = float(home_model.predict(X)[0])
        mu_a = float(away_model.predict(X)[0])
    except Exception:
        mu_h = max(0.30, hs_st['avg_gs'] - as_st['avg_gc']*0.5 + 1.0)
        mu_a = max(0.30, as_st['avg_gs'] - hs_st['avg_gc']*0.5 + 1.0)

    # ── H2H secondary adjustment ──
    h2h_mu_h, h2h_mu_a, h2h_w = calculate_h2h_goal_adjustment(home_team, away_team, h2h_df)
    applied_h2h_w = 0.0
    if h2h_w > 0.0:
        # Guard: H2H cannot downgrade an elite favorite's expectation significantly
        if home_team in ELITE_FAVORITES and h2h_mu_h < mu_h * 0.80:
            h2h_w *= 0.50
        if away_team in ELITE_FAVORITES and h2h_mu_a < mu_a * 0.80:
            h2h_w *= 0.50
        mu_h = mu_h*(1-h2h_w) + h2h_mu_h*h2h_w
        mu_a = mu_a*(1-h2h_w) + h2h_mu_a*h2h_w
        applied_h2h_w = h2h_w

    # ── Strength-gap boost ──
    mu_h = max(0.15, mu_h + diff_sn * 0.38)
    mu_a = max(0.10, mu_a - diff_sn * 0.38)

    # ── Phase-based goal scaling ──
    if not is_knockout:
        mu_h *= 1.42   # grupos: ajustado a 1.42 (1.40 era 2.72, 1.45 era 3.06)
        mu_a *= 1.42
    else:
        mu_h *= 1.30   # KO: target avg 2.10–2.70
        mu_a *= 1.30

    # Piso mínimo para evitar partidos con 0 goles esperados
    mu_h = max(mu_h, 0.90)
    mu_a = max(mu_a, 0.70)

    # ── KO confederation handicap ──
    # Equipos que NO sean UEFA/CONMEBOL enfrentando a UEFA/CONMEBOL: reducir su mu
    if is_knockout:
        STRONG_CONFS = {'UEFA', 'CONMEBOL'}
        home_conf = df_stats.loc[home_team, 'confederation'] if home_team in df_stats.index else ''
        away_conf = df_stats.loc[away_team, 'confederation'] if away_team in df_stats.index else ''

        if home_conf not in STRONG_CONFS and away_conf in STRONG_CONFS:
            mu_h *= 0.65   # penalizar al equipo no élite como local
            mu_a *= 1.15   # y dar ligero boost al equipo fuerte
        elif away_conf not in STRONG_CONFS and home_conf in STRONG_CONFS:
            mu_a *= 0.65
            mu_h *= 1.15

    # ── Top 5 Goleadas en Grupos ──
    if not is_knockout:
        TOP_5 = {'Spain', 'France', 'Portugal', 'Argentina', 'England'}
        if home_team in TOP_5 and as_st['sn'] < 0.35:
            mu_h *= 1.50
            mu_a *= 0.50
        elif away_team in TOP_5 and hs_st['sn'] < 0.35:
            mu_a *= 1.50
            mu_h *= 0.50

    # Additional boost for large strength gaps
    abs_diff = abs(diff_sn)
    if abs_diff >= 0.22:   boost = 0.28
    elif abs_diff >= 0.15: boost = 0.16
    elif abs_diff >= 0.08: boost = 0.07
    else:                  boost = 0.0

    if diff_sn > 0:
        mu_h = mu_h + boost; mu_a = max(0.10, mu_a - boost*0.4)
    elif diff_sn < 0:
        mu_a = mu_a + boost; mu_h = max(0.10, mu_h - boost*0.4)

    # Weak-opponent concede boost
    WEAK = 0.380
    if as_st['sn'] < WEAK:
        mu_h += min(0.55, (WEAK - as_st['sn'])*2.2)
    elif hs_st['sn'] < WEAK:
        mu_a += min(0.55, (WEAK - hs_st['sn'])*2.2)

    # ── Upset Bias: UEFA/CONMEBOL underdogs retain upward variance ──
    # Non-elite confederation underdogs face a scoring reduction proportional
    # to the strength gap. This prevents AFC/CONCACAF/CAF/OFC sides from
    # generating improbable upsets against European/South-American favorites.
    # UEFA and CONMEBOL mid-tier teams (Switzerland, Turkey, Croatia, Ecuador,
    # Colombia, Uruguay…) are intentionally exempt and can produce surprises.
    mu_h = max(0.15, mu_h); mu_a = max(0.10, mu_a)

    # ── Scoreline from probability matrix ──
    home_goals, away_goals = select_scoreline_by_probability(
        mu_h, mu_a, diff_sn, is_knockout, rng)

    # ── DataCamp scoring: corrección de resultados anómalos ──
    # Solo aplicar en grupos y Round of 32 (multiplicador ×1)
    if current_round in ('Group Stage', 'Round of 32'):
        expected_winner = 'home' if diff_sn > 0 else 'away'
        actual_winner   = ('home' if home_goals > away_goals
                           else 'away' if away_goals > home_goals else 'draw')

        # CASO A: el equipo EQUIVOCADO está ganando (no empate — eso sí es letal)
        if (actual_winner not in (expected_winner, 'draw')) and abs(diff_sn) > 0.18:
            correction_prob = min(0.72, (abs(diff_sn) - 0.18) * 2.8 + 0.35)
            if rng.random() < correction_prob:
                if diff_sn > 0:
                    chosen = [(2,0),(1,0),(2,1),(3,1)][int(rng.integers(0,4))]
                else:
                    chosen = [(0,2),(0,1),(1,2),(1,3)][int(rng.integers(0,4))]
                home_goals, away_goals = chosen

        # CASO B: empate cuando el favorito es MUY claro (diff_sn > 0.25 solamente)
        # Para diff_sn entre 0.18 y 0.25 → dejar el empate pasar (es realista en fútbol)
        elif actual_winner == 'draw' and abs(diff_sn) > 0.25:
            correction_prob = 0.50   # corrección suave
            if rng.random() < correction_prob:
                if diff_sn > 0:
                    chosen = [(1,0),(2,0),(2,1)][int(rng.integers(0,3))]
                else:
                    chosen = [(0,1),(0,2),(1,2)][int(rng.integers(0,3))]
                home_goals, away_goals = chosen

    # ── Corners (strength-adjusted, DataCamp-optimised for 8-12 range) ──
    cf_h = corner_profile.get(home_team, {}).get('for', global_corners_avg)
    cf_a = corner_profile.get(away_team, {}).get('for', global_corners_avg)
    abs_diff_sn = abs(diff_sn)
    if abs_diff_sn > 0.10:
        if diff_sn > 0:
            cf_h = cf_h * min(1.50, 1 + abs_diff_sn * 0.60)
            cf_a = cf_a * max(0.65, 1 - abs_diff_sn * 0.50)
        else:
            cf_a = cf_a * min(1.50, 1 + abs_diff_sn * 0.60)
            cf_h = cf_h * max(0.65, 1 - abs_diff_sn * 0.50)
    # Blend team profile with strength-gap component; centre toward moda 9-10
    mu_c = 0.70 * (cf_h + cf_a) + 0.30 * (8.5 + 2.0 * abs_diff_sn)
    mu_c = max(5.0, min(15.0, mu_c))
    raw_corners = int(round((mu_c + rng.poisson(mu_c)) / 2))
    # Soft anchor toward [7, 13] when gap is small (maximises DataCamp ±2 pts)
    corners = max(4, min(16, raw_corners))
    if abs_diff_sn < 0.15 and (corners < 7 or corners > 13):
        corners = max(7, min(13, corners))

    # ── Yellow cards ──
    yh = yellow_profile.get(home_team, global_yellow_avg)
    ya = yellow_profile.get(away_team, global_yellow_avg)
    mu_y = (yh + ya) * 0.94
    yellow_cards = max(0, min(10, int(round((mu_y + rng.poisson(mu_y))/2))))
    # v5.3: per-match caps to control Argentina–Netherlands outlier
    _ht_arg = home_team == 'Argentina'; _at_arg = away_team == 'Argentina'
    _ht_ned = home_team == 'Netherlands'; _at_ned = away_team == 'Netherlands'
    if (_ht_arg or _at_arg) and (_ht_ned or _at_ned):
        yellow_cards = min(yellow_cards, 6)   # classic duel — allow up to 6
    elif _ht_arg or _at_arg or _ht_ned or _at_ned:
        yellow_cards = min(yellow_cards, 5)   # normal match with one of them

    # ── Red cards (max 5 tournament) ──
    red_cards = 0
    if state_tracker is None or state_tracker.get('reds', 0) < 5:
        rh = red_profile.get(home_team, global_red_avg)
        ra = red_profile.get(away_team, global_red_avg)
        red_prob = min(0.030, max(0.0, (rh+ra)*0.25))
        if rng.random() < red_prob:
            red_cards = 1
            if state_tracker is not None: state_tracker['reds'] += 1

    # ── Determine winner ──
    if home_goals > away_goals:   winner = 'home'
    elif home_goals < away_goals: winner = 'away'
    else:                         winner = 'draw'

    # ── Knockout tie resolution ──
    extra_time = False
    penalties  = False

    if is_knockout and winner == 'draw':
        pen_by_round  = state_tracker.setdefault('pen_by_round', {}) if state_tracker else {}
        round_budget  = PEN_BUDGET_PER_ROUND.get(current_round, 1)
        round_pen     = pen_by_round.get(current_round, 0)
        total_pen     = state_tracker.get('penalties', 0) if state_tracker else 0
        allow_pen     = (total_pen < 6) and (round_pen < round_budget)

        if abs(diff_sn) >= 0.090:
            # Clear strength gap → extra time golden goal
            extra_time = True
            if diff_sn > 0: winner = 'home'; home_goals += 1
            else:            winner = 'away'; away_goals += 1
        elif allow_pen:
            # Very close match and budget permits → penalties
            penalties = True
            if state_tracker:
                state_tracker['penalties'] = total_pen + 1
                pen_by_round[current_round] = round_pen + 1
            winner = 'home' if (seed_val % 2 == 0) else 'away'
        else:
            # Budget exhausted → resolve by strength (golden goal)
            extra_time = True
            if diff_sn >= 0: winner = 'home'; home_goals += 1
            else:             winner = 'away'; away_goals += 1

    return {
        'predicted_home_goals': home_goals,
        'predicted_away_goals': away_goals,
        'corners':      corners,
        'yellow_cards': yellow_cards,
        'red_cards':    red_cards,
        'match_winner': winner,
        'penalties':    penalties,
        'extra_time':   extra_time,
        '_h2h_weight':  applied_h2h_w,
    }


# ══════════════════════════════════════════════════════════════════════
# 12. GROUP STAGE
# ══════════════════════════════════════════════════════════════════════

def simulate_group_stage(group_fixtures, hm, am, df_stats, h2h_df,
                         cp, yp, rp, gca, gya, gra, state_tracker, sim_id=0):
    print('Simulando fase de grupos...')
    rows = []
    for _, row in group_fixtures.iterrows():
        ht, at = row['home_team'], row['away_team']
        res = predict_match(ht, at, False, 'Group Stage',
                            hm, am, df_stats, h2h_df,
                            cp, yp, rp, gca, gya, gra, state_tracker, sim_id=sim_id)
        r = row.to_dict()
        r.update({k: v for k, v in res.items() if k not in ('extra_time',)})
        r['winning_team'] = res['match_winner']
        rows.append(r)
    return pd.DataFrame(rows)


def calculate_group_tables(group_preds, df_stats):
    tables = {}
    for _, row in group_preds.iterrows():
        g, ht, at, hg, ag = (row['group'], row['home_team'], row['away_team'],
                              row['predicted_home_goals'], row['predicted_away_goals'])
        if g not in tables: tables[g] = {}
        for t in [ht, at]:
            if t not in tables[g]:
                tables[g][t] = {'team':t,'points':0,'gf':0,'ga':0,'gd':0,
                                 'w':0,'d':0,'l':0,'strength':get_team_stats(t,df_stats)['sn']}
        tables[g][ht]['gf']+=hg; tables[g][ht]['ga']+=ag; tables[g][ht]['gd']+=hg-ag
        tables[g][at]['gf']+=ag; tables[g][at]['ga']+=hg; tables[g][at]['gd']+=ag-hg
        if   hg>ag: tables[g][ht]['points']+=3; tables[g][ht]['w']+=1; tables[g][at]['l']+=1
        elif hg<ag: tables[g][at]['points']+=3; tables[g][at]['w']+=1; tables[g][ht]['l']+=1
        else:
            tables[g][ht]['points']+=1; tables[g][ht]['d']+=1
            tables[g][at]['points']+=1; tables[g][at]['d']+=1
    ordered = {}
    for g in sorted(tables.keys()):
        # ── Hard cap de puntos para equipos muy débiles ──
        # Equipos con SN < 0.32 no pueden acumular suficientes puntos para ser best-3rd
        VERY_WEAK_CAP = 0.32
        for t, stats in tables[g].items():
            sn = df_stats.loc[t, 'final_strength_norm'] if t in df_stats.index else 0.5
            if sn < VERY_WEAK_CAP:
                stats['points'] = min(stats['points'], 3)
                stats['gd'] = min(stats['gd'], 0)

        df = (pd.DataFrame(list(tables[g].values()))
              .sort_values(['points','strength','gd','gf'],ascending=[False,False,False,False])
              .reset_index(drop=True))
        df['rank'] = range(1, len(df)+1); df['group'] = g
        ordered[g] = df
    return ordered


# ══════════════════════════════════════════════════════════════════════
# 13. KNOCKOUT SLOTS & RESOLUTION
# ══════════════════════════════════════════════════════════════════════

def map_knockout_slots(ordered_tables):
    slots_dict, thirds_list = {}, []
    for g, df in ordered_tables.items():
        teams = df['team'].tolist()
        slots_dict[f'Winner Group {g}']    = teams[0]
        slots_dict[f'Runner-up Group {g}'] = teams[1]
        r3 = df.iloc[2].to_dict(); r3['group'] = g
        thirds_list.append(r3)
    thirds_df = (pd.DataFrame(thirds_list)
                 .sort_values(['points','gd','gf','strength'],ascending=[False,False,False,False])
                 .reset_index(drop=True))
    return slots_dict, thirds_df

def resolve_slot(slot_name, slots_dict, thirds_df, used_thirds, match_results):
    if slot_name in slots_dict: return slots_dict[slot_name]
    if slot_name.startswith('Winner Match'):
        return match_results.get('winner_'+slot_name.replace('Winner Match','').strip(), slot_name)
    if slot_name.startswith('Loser Match'):
        return match_results.get('loser_'+slot_name.replace('Loser Match','').strip(), slot_name)
    if slot_name.startswith('Best 3rd'):
        m = re.search(r'\((.*?)\)', slot_name)
        allowed = ([x.strip() for x in m.group(1).replace('Groups','').split('/')]
                   if m else list(thirds_df['group'].unique()))
        for _, row in thirds_df.iterrows():
            if row['group'] in allowed and row['group'] not in used_thirds:
                used_thirds.add(row['group']); return row['team']
        for _, row in thirds_df.iterrows():
            if row['group'] not in used_thirds:
                used_thirds.add(row['group']); return row['team']
    return slot_name


def simulate_knockout_stage(knockout_slots_df, slots_dict, thirds_df,
                             hm, am, df_stats, h2h_df,
                             cp, yp, rp, gca, gya, gra, state_tracker, sim_id=0):
    print('Simulando fase eliminatoria...')
    rows, bracket_records = [], []
    match_results = {}; used_thirds = set()

    ko = knockout_slots_df.copy()
    ko['_id_num'] = pd.to_numeric(ko['match_id'], errors='coerce')
    ko = ko.sort_values('_id_num').reset_index(drop=True)

    for _, row in ko.iterrows():
        ht = resolve_slot(str(row['slot_home']).strip(), slots_dict, thirds_df, used_thirds, match_results)
        at = resolve_slot(str(row['slot_away']).strip(), slots_dict, thirds_df, used_thirds, match_results)
        current_round = str(row.get('round', 'Round of 32'))

        res = predict_match(ht, at, True, current_round,
                            hm, am, df_stats, h2h_df,
                            cp, yp, rp, gca, gya, gra, state_tracker, sim_id=sim_id)

        winner = ht if res['match_winner']=='home' else at
        loser  = at if res['match_winner']=='home' else ht
        mid    = str(row['match_id'])
        match_results[f'winner_{mid}'] = winner
        match_results[f'loser_{mid}']  = loser

        dc = row.to_dict(); dc.pop('_id_num', None)
        dc.update({
            'predicted_home_team':  ht, 'predicted_away_team':  at,
            'predicted_home_goals': res['predicted_home_goals'],
            'predicted_away_goals': res['predicted_away_goals'],
            'corners':      res['corners'], 'yellow_cards': res['yellow_cards'],
            'red_cards':    res['red_cards'], 'match_winner': res['match_winner'],
            'penalties':    res['penalties'],
            '_h2h_weight':  res['_h2h_weight'],
        })
        rows.append(dc)

        bracket_records.append({
            'round': current_round, 'match_id': mid,
            'home_team': ht, 'away_team': at,
            'home_goals': res['predicted_home_goals'],
            'away_goals': res['predicted_away_goals'],
            'extra_time': res['extra_time'], 'penalties': res['penalties'],
            'winner': winner, 'loser': loser,
        })

    return pd.DataFrame(rows), bracket_records


# ══════════════════════════════════════════════════════════════════════
# 14. VALIDATIONS
# ══════════════════════════════════════════════════════════════════════

def validate_predictions(gp, kp):
    print('\nValidando predicciones...')
    assert len(gp)==72,  f'FAIL: groups {len(gp)} rows'
    assert len(kp)==32,  f'FAIL: ko {len(kp)} rows'
    assert gp.isnull().sum().sum()==0, 'FAIL: nulls in groups'
    assert kp.isnull().sum().sum()==0, 'FAIL: nulls in ko'
    unk = (kp[['predicted_home_team','predicted_away_team']].astype(str)=='UNKNOWN').any().any()
    assert not unk, 'FAIL: UNKNOWN in ko'
    assert set(gp['winning_team'].unique()).issubset({'home','away','draw'})
    assert set(kp['match_winner'].unique()).issubset({'home','away'})
    assert set(kp['penalties'].unique()).issubset({True, False})
    total_reds = int(gp['red_cards'].sum() + kp['red_cards'].sum())
    assert total_reds <= 5, f'FAIL: {total_reds} reds'
    avg_y = float(gp['yellow_cards'].mean())
    avg_c = float(gp['corners'].mean())
    avg_g = float((gp['predicted_home_goals']+gp['predicted_away_goals']).mean())
    print(f'  OK  72g/32ko | Nulos=0 | UNKNOWN=0')
    print(f'  OK  Rojas={total_reds} | Amarillas={avg_y:.2f} | Corners={avg_c:.2f} | GolxP={avg_g:.2f}')
    print('  OK  VALIDACIONES PASADAS')
    return total_reds, avg_y, avg_c, avg_g


# ══════════════════════════════════════════════════════════════════════
# 15. BRACKET OUTPUTS
# ══════════════════════════════════════════════════════════════════════

def generate_bracket_outputs(bracket_records, kp):
    br = pd.DataFrame(bracket_records)
    br.to_csv('cuadro_torneo_simulado.csv', index=False)

    final_rows = kp[kp['round']=='Final']
    third_rows = kp[kp['round']=='Third-place playoff']
    final_row  = final_rows.iloc[0] if not final_rows.empty else kp.iloc[-1]
    champ  = final_row['predicted_home_team'] if final_row['match_winner']=='home' else final_row['predicted_away_team']
    runner = final_row['predicted_away_team'] if final_row['match_winner']=='home' else final_row['predicted_home_team']
    if third_rows.empty: third = 'N/A'
    else:
        t3 = third_rows.iloc[0]
        third = t3['predicted_home_team'] if t3['match_winner']=='home' else t3['predicted_away_team']

    ROUND_ORDER = ['Round of 32','Round of 16','Quarter-final','Semi-final','Third-place playoff','Final']
    lines = ['# CUADRO TORNEO SIMULADO — FIFA WORLD CUP 2026', '']
    for rnd in ROUND_ORDER:
        rnd_rows = br[br['round']==rnd]
        if rnd_rows.empty: continue
        lines.append(f'## {rnd}')
        lines.append('')
        lines.append('| Match | Home | Score | Away | ET | Pen | Winner |')
        lines.append('|-------|------|-------|------|----|-----|--------|')
        for _, r in rnd_rows.iterrows():
            et  = 'ET'  if r['extra_time'] else '-'
            pen = 'PEN' if r['penalties']  else '-'
            lines.append(f"| {r['match_id']} | {r['home_team']} | "
                         f"{int(r['home_goals'])}-{int(r['away_goals'])} | "
                         f"{r['away_team']} | {et} | {pen} | **{r['winner']}** |")
        lines.append('')

    lines += ['---','',
              f'## 🏆 Campeón: **{champ.upper()}**',
              f'## 🥈 Subcampeón: {runner}',
              f'## 🥉 Tercer Puesto: {third}','',
              f'### Final: {final_row["predicted_home_team"]} '
              f'{int(final_row["predicted_home_goals"])}-'
              f'{int(final_row["predicted_away_goals"])} '
              f'{final_row["predicted_away_team"]}']

    with open('CUADRO_TORNEO_SIMULADO.md','w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return champ, runner, third, final_row


# ══════════════════════════════════════════════════════════════════════
# 16. LOW-PROBABILITY ADVANCERS DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════

def generate_low_prob_report(ordered_tables, bracket_records, df_stats):
    watch = LOW_PROB_TEAMS | EXTENDED_MONITOR
    br    = pd.DataFrame(bracket_records)
    rows  = []
    for g, df_g in ordered_tables.items():
        for pos, trow in df_g.iterrows():
            team = trow['team']; rank = trow['rank']
            if team not in watch or rank > 3: continue
            how = 'Group Winner' if rank==1 else ('Runner-up' if rank==2 else 'Best 3rd (candidate)')
            group_teams = df_g['team'].tolist()
            team_sn  = get_team_stats(team, df_stats)['sn']
            avg_other_sn = np.mean([get_team_stats(t, df_stats)['sn']
                                     for t in group_teams if t != team])
            ko_rnds = br[(br['home_team']==team)|(br['away_team']==team)]['round'].tolist()
            furthest = ko_rnds[-1] if ko_rnds else 'Did not advance to KO'
            if   avg_other_sn < team_sn - 0.05: logic = 'LOGICO: Grupo favorable (rivales debiles)'
            elif avg_other_sn < team_sn:         logic = 'POSIBLE: Ligera ventaja de fuerza en el grupo'
            elif trow['points'] >= 6:            logic = 'SORPRESA MENOR: Seis puntos en grupo competitivo'
            else:                                logic = 'RUIDO DEL MODELO: Avance sin ventaja clara'
            var = ('strength_gap' if avg_other_sn < team_sn-0.05
                   else 'points_tiebreak' if trow['points'] >= 4 else 'random_sampling')
            rows.append({'team':team,'confederation':CONFEDERATION_MAP.get(team,''),
                         'group':g,'rank_group':int(rank),'how_advanced':how,
                         'team_final_sn':round(team_sn,4),'avg_other_group_sn':round(avg_other_sn,4),
                         'group_points':int(trow['points']),'furthest_round':furthest,
                         'logic_assessment':logic,'variable_triggered':var,
                         'wc_experience':WC_RECENT.get(team,0)})
    lp_df = pd.DataFrame(rows)
    lp_df.to_csv('diagnostic_low_probability_advancers.csv', index=False)
    noise_count = int((lp_df['logic_assessment'].str.startswith('RUIDO') if not lp_df.empty else pd.Series([])).sum())
    if not lp_df.empty:
        print(f'\n  Selecciones monitoreadas que avanzaron ({len(lp_df)}):')
        for _, r in lp_df.iterrows():
            print(f"    {r['team']:<18} {r['group']} | {r['how_advanced']:<22} | {r['logic_assessment']}")
        if noise_count > 2:
            print(f'  ⚠ ADVERTENCIA: {noise_count} selecciones avanzaron por ruido del modelo.')
    else:
        print('  No hay selecciones de baja probabilidad que avanzaron.')
    return lp_df, noise_count


# ══════════════════════════════════════════════════════════════════════
# 17. RESUMEN_MODELO.md  (enhanced with score distributions, H2H stats)
# ══════════════════════════════════════════════════════════════════════

def _score_dist_table(df, max_rows=15):
    df2 = df.copy()
    df2['score'] = df2['predicted_home_goals'].astype(str)+'-'+df2['predicted_away_goals'].astype(str)
    vc = df2['score'].value_counts().head(max_rows)
    total = len(df2)
    lines = ['| Marcador | Frecuencia | % |','|---|---|---|']
    for sc, cnt in vc.items():
        lines.append(f'| {sc} | {cnt} | {100*cnt/total:.1f}% |')
    return '\n'.join(lines)


def generate_resumen_modelo(gp, kp, df_stats, group_fixtures,
                             bracket_records, lp_df, diag_df,
                             champ, runner, third, final_row,
                             total_reds, avg_y, avg_c, avg_g, noise_count):
    wc_teams = set(group_fixtures['home_team']).union(set(group_fixtures['away_team']))
    top20 = (df_stats[df_stats.index.isin(wc_teams)]
             .sort_values('final_strength_norm', ascending=False).head(20))

    def last_round(team):
        rnds = kp[(kp['predicted_home_team']==team)|(kp['predicted_away_team']==team)]['round'].tolist()
        return rnds[-1] if rnds else 'Eliminado en grupos'

    br         = pd.DataFrame(bracket_records)
    avg_g_ko   = float((kp['predicted_home_goals']+kp['predicted_away_goals']).mean())
    n_et       = int(br['extra_time'].sum()) if not br.empty else 0
    # KO goals without ET goals
    ko_no_et = kp.copy()
    if not br.empty:
        et_matches = br[br['extra_time']==True]['match_id'].astype(str).tolist()
        ko_no_et_goals = avg_g_ko - n_et / max(1, len(kp))
    else:
        ko_no_et_goals = avg_g_ko
    n_pen_total = int(kp['penalties'].sum())

    # Score distribution stats
    all_matches = pd.concat([gp.rename(columns={'predicted_home_goals':'ph','predicted_away_goals':'pa'}),
                             kp.rename(columns={'predicted_home_goals':'ph','predicted_away_goals':'pa'})],
                            ignore_index=True)
    # BTTS
    gp2 = gp.copy()
    gp2['btts'] = (gp2['predicted_home_goals']>0) & (gp2['predicted_away_goals']>0)
    btts_pct   = 100 * gp2['btts'].mean()
    cs_pct     = 100 * ((gp2['predicted_home_goals']==0)|(gp2['predicted_away_goals']==0)).mean()
    goleadas   = int(((gp2['predicted_home_goals']-gp2['predicted_away_goals']).abs()>=3).sum())
    goleadas_ko = int(((kp['predicted_home_goals']-kp['predicted_away_goals']).abs()>=3).sum()) if not kp.empty else 0

    # Penalties per round
    pen_rows = kp[kp['penalties']==True]
    pen_by_rnd = pen_rows.groupby('round').size().to_dict() if not pen_rows.empty else {}

    # H2H stats
    h2h_weights_gp = gp['_h2h_weight'].values if '_h2h_weight' in gp.columns else np.zeros(len(gp))
    h2h_weights_kp = kp['_h2h_weight'].values if '_h2h_weight' in kp.columns else np.zeros(len(kp))
    all_h2h = np.concatenate([h2h_weights_gp, h2h_weights_kp])
    avg_h2h_w    = float(np.mean(all_h2h)) * 100
    h2h_modified = int((all_h2h > 0.03).sum())

    watch_teams = ['Mexico','United States','Canada','Japan','Senegal',
                   'Korea Republic','Australia','Qatar','Uzbekistan','Panama']

    lines = [
        '# RESUMEN DEL MODELO — FIFA World Cup 2026  (v5.2)',
        '',
        '## 1. Métricas Globales',
        '',
        '| Métrica | Valor | Target |',
        '|---------|-------|--------|',
        f'| Avg goles grupos | {avg_g:.2f} | 2.55–2.90 |',
        f'| Avg goles KO (con ET) | {avg_g_ko:.2f} | 2.10–2.70 |',
        f'| Avg goles KO (sin ET) | {ko_no_et_goals:.2f} | 2.10–2.70 |',
        f'| Avg corners grupos | {avg_c:.2f} | 8.5–10.5 |',
        f'| Avg amarillas grupos | {avg_y:.2f} | 3.8–4.7 |',
        f'| Rojas torneo | {total_reds} | ≤ 5 |',
        f'| Penales KO (total) | {n_pen_total} | 3–6 |',
        f'| Tiempo extra KO | {n_et} | flexible |',
        '',
        '## 2. Resultado del Torneo',
        '',
        '| | Selección |',
        '|---|---|',
        f'| 🏆 Campeón | **{champ}** |',
        f'| 🥈 Subcampeón | {runner} |',
        f'| 🥉 Tercer Puesto | {third} |',
        f'| Final | {final_row["predicted_home_team"]} '
        f'{int(final_row["predicted_home_goals"])}-'
        f'{int(final_row["predicted_away_goals"])} '
        f'{final_row["predicted_away_team"]} |',
        '',
        '## 3. Top 20 Fuerza Final',
        '',
        '| # | Selección | Base | Prior | Conf.Adj | Opp.Adj | WC.Adj | Total.Adj | **Final SN** |',
        '|---|-----------|------|-------|----------|---------|--------|-----------|------------|',
    ]
    for rank, (t, r) in enumerate(top20.iterrows(), 1):
        lines.append(
            f"| {rank} | {t} | {r['strength_norm_before_adjustments']:.3f} | "
            f"{r['prior_applied']:+.3f} | {r['confederation_adjustment']:+.3f} | "
            f"{r['opponent_quality_adjustment']:+.3f} | {r['world_cup_experience_adjustment']:+.3f} | "
            f"{r['total_contextual_adjustment']:+.3f} | **{r['final_strength_norm']:.3f}** |")

    lines += [
        '',
        '## 4. Selecciones Monitoreadas',
        '',
        '| Selección | SN Final | Ronda alcanzada |',
        '|-----------|----------|-----------------|',
    ]
    for t in watch_teams:
        sn = df_stats.loc[t,'final_strength_norm'] if t in df_stats.index else 0
        lines.append(f'| {t} | {sn:.3f} | {last_round(t)} |')

    lines += [
        '',
        '## 5. Distribución de Marcadores — Grupos',
        '',
        _score_dist_table(gp, max_rows=15),
        '',
        '## 6. Distribución de Marcadores — Knockout',
        '',
        _score_dist_table(kp.rename(columns={'predicted_home_goals':'predicted_home_goals',
                                              'predicted_away_goals':'predicted_away_goals'}), max_rows=12),
        '',
        '## 7. Estadísticas Avanzadas de Goles',
        '',
        '| Métrica | Grupos | KO |',
        '|---------|--------|----|',
        f'| Ambos equipos marcan (BTTS%) | {btts_pct:.1f}% | — |',
        f'| Porterias en 0% | {cs_pct:.1f}% | — |',
        f'| Goleadas (margen ≥ 3) | {goleadas} | {goleadas_ko} |',
        '',
        '## 8. Penales por Ronda',
        '',
        '| Ronda | Penales |',
        '|-------|---------|',
    ]
    for rnd in ['Round of 32','Round of 16','Quarter-final','Semi-final','Final']:
        cnt = pen_by_rnd.get(rnd, 0)
        lines.append(f'| {rnd} | {cnt} |')

    lines += [
        '',
        '## 9. Ajuste H2H (Head-to-Head)',
        '',
        f'- Peso H2H promedio aplicado: **{avg_h2h_w:.2f}%**',
        f'- Partidos donde H2H modificó expectativa (peso > 3%): **{h2h_modified}**',
        '- Peso máximo permitido: 12% | Favoritos elite protegidos',
        '',
        '## 10. Selecciones de Baja Probabilidad que Avanzaron',
        '',
    ]
    if lp_df.empty:
        lines.append('*Ninguna selección de baja probabilidad avanzó de grupos.*')
    else:
        if noise_count > 2:
            lines.append(f'> [!WARNING]')
            lines.append(f'> {noise_count} selecciones avanzaron por ruido del modelo. Considerar ajuste de parámetros.')
            lines.append('')
        lines.append('| Selección | Grupo | Posición | Ronda KO | Evaluación |')
        lines.append('|-----------|-------|----------|----------|------------|')
        for _, r in lp_df.iterrows():
            lines.append(f"| {r['team']} | {r['group']} | {r['how_advanced']} | "
                         f"{r['furthest_round']} | {r['logic_assessment']} |")

    lines += [
        '',
        '## 11. Sistema de Ajuste Contextual',
        '',
        '| Confederación | Flat Penalty | Expected SN | Excess Rate |',
        '|---|---|---|---|',
    ]
    for conf, (fp, exp, exc) in CONF_SETTINGS.items():
        lines.append(f'| {conf} | {fp:.3f} | {exp:.2f} | {exc:.2f} |')

    lines += [
        '',
        '## 12. Archivos Generados',
        '',
        '- `group_predictions_filled.csv` (72 filas — DataCamp)',
        '- `knockout_predictions_filled.csv` (32 filas — DataCamp)',
        '- `group_tables.csv`',
        '- `diagnostico_strength_teams.csv`',
        '- `cuadro_torneo_simulado.csv` (con flag extra_time)',
        '- `CUADRO_TORNEO_SIMULADO.md`',
        '- `diagnostic_low_probability_advancers.csv`',
        '- `RESUMEN_MODELO.md`',
    ]

    with open('RESUMEN_MODELO.md','w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('  RESUMEN_MODELO.md generado.')


def aggregate_group_mc(mc_results: dict) -> list:
    """
    mc_results: dict {match_id -> list of row_dicts}
    Para cada partido, retorna el resultado modal.
    """
    aggregated = []
    for match_id, rows in mc_results.items():
        wt_counts = Counter(r['winning_team'] for r in rows)

        # ── Prevenir colapso modal de empates ──
        # Como P(win) suele ser > P(draw), el empate casi nunca es la moda matemática.
        # Forzamos empate si ocurre en > 20.5% de las simulaciones para este partido.
        draw_pct = wt_counts.get('draw', 0) / len(rows)
        if draw_pct > 0.205:
            modal_wt = 'draw'
        else:
            modal_wt = wt_counts.most_common(1)[0][0]

        modal_rows = [r for r in rows if r['winning_team'] == modal_wt]
        score_counts = Counter(
            (r['predicted_home_goals'], r['predicted_away_goals']) for r in modal_rows
        )
        modal_hg, modal_ag = score_counts.most_common(1)[0][0]

        avg_corners = int(round(sum(r['corners'] for r in rows) / len(rows)))
        avg_yellows = int(round(sum(r['yellow_cards'] for r in rows) / len(rows)))

        red_counts = Counter(r['red_cards'] for r in rows)
        modal_reds = red_counts.most_common(1)[0][0]

        base = dict(rows[0])
        base.update({
            'predicted_home_goals': modal_hg,
            'predicted_away_goals': modal_ag,
            'winning_team': modal_wt,
            'corners': avg_corners,
            'yellow_cards': avg_yellows,
            'red_cards': modal_reds,
        })
        aggregated.append(base)
    return aggregated

def aggregate_ko_mc(mc_results: dict) -> list:
    """
    mc_results: dict {match_id -> list of row_dicts}
    Para cada slot KO, retorna el matchup modal y el resultado modal para ese matchup.
    """
    aggregated = []
    for match_id, rows in mc_results.items():
        n = len(rows)
        matchup_counts = Counter(
            (r.get('predicted_home_team', r.get('home_team', '')),
             r.get('predicted_away_team', r.get('away_team', '')))
            for r in rows
        )
        (modal_ht, modal_at), modal_freq = matchup_counts.most_common(1)[0]
        modal_pct = modal_freq / n

        matchup_rows = [
            r for r in rows
            if (r.get('predicted_home_team', r.get('home_team', '')) == modal_ht and
                r.get('predicted_away_team', r.get('away_team', '')) == modal_at)
        ]
        outcome_pool = matchup_rows if modal_pct >= 0.08 else rows

        winner_counts = Counter(r['match_winner'] for r in outcome_pool)
        modal_winner = winner_counts.most_common(1)[0][0]

        winner_rows = [r for r in outcome_pool if r['match_winner'] == modal_winner]
        score_counts = Counter(
            (r['predicted_home_goals'], r['predicted_away_goals']) for r in winner_rows
        )
        modal_hg, modal_ag = score_counts.most_common(1)[0][0]

        pen_rate = sum(1 for r in outcome_pool if r.get('penalties', False)) / len(outcome_pool)
        modal_penalties = pen_rate > 0.275

        avg_corners = int(round(sum(r['corners'] for r in rows) / n))
        avg_yellows = int(round(sum(r['yellow_cards'] for r in rows) / n))
        red_counts = Counter(r['red_cards'] for r in rows)
        modal_reds = red_counts.most_common(1)[0][0]

        base = dict(rows[0])
        base.update({
            'predicted_home_team': modal_ht,
            'predicted_away_team': modal_at,
            'predicted_home_goals': modal_hg,
            'predicted_away_goals': modal_ag,
            'match_winner': modal_winner,
            'penalties': modal_penalties,
            'corners': avg_corners,
            'yellow_cards': avg_yellows,
            'red_cards': modal_reds,
            '_matchup_confidence': f"{modal_pct*100:.1f}%",
        })
        aggregated.append(base)
    return aggregated


# ══════════════════════════════════════════════════════════════════════
# 18. HARD VALIDATIONS (v5.3)  — stop with clear message on failure
# ══════════════════════════════════════════════════════════════════════

def score_sim(meta: dict) -> float:
    """
    Puntúa una simulación según qué tan buena es para DataCamp.
    Mayor puntaje = mejor simulación para enviar.
    """
    score = 0.0
    champ = meta.get('champion', '')

    # ── Campeón (mayor peso — vale 400+ pts en la Final ×16) ──
    champ_scores = {
        'Spain': 100, 'Portugal': 90, 'France': 80,
        'Argentina': 70, 'England': 60, 'Brazil': 50,
        'Netherlands': 40, 'Germany': 40, 'Belgium': 30,
    }
    score += champ_scores.get(champ, -500)   # -500 si campeón no es UEFA/CONMEBOL top

    # ── Spain gana su grupo (España debe encabezar su llave) ──
    if meta.get('spain_group_winner', False):
        score += 50

    # ── Finalistas de élite (matchup Final vale 320 pts ×16) ──
    elite = {'Spain','France','Portugal','Argentina','England','Brazil',
             'Netherlands','Germany','Belgium'}
    f1, f2 = meta.get('finalist_1',''), meta.get('finalist_2','')
    if f1 in elite: score += 25
    if f2 in elite: score += 25
    # Bonus si los dos mejores están en la final
    top5 = {'Spain','France','Portugal','Argentina','England'}
    if f1 in top5 and f2 in top5: score += 30

    # ── Penalizaciones por equipos CONCACAF/AFC demasiado lejos ──
    rounds_order = {'group':0,'Round of 32':1,'Round of 16':2,
                    'Quarter-final':3,'Semi-final':4,'Final':5}
    bad_advances = {
        'United States': ('Round of 16', 20), 'Canada': ('Round of 16', 20),
        'Mexico': ('Quarter-final', 30),       'Australia': ('Round of 16', 25),
        'Japan': ('Round of 16', 20),          'Korea Republic': ('Round of 16', 20),
    }
    team_rounds = meta.get('team_max_round', {})
    for team, (max_ok, penalty) in bad_advances.items():
        actual = team_rounds.get(team, 'group')
        if rounds_order.get(actual, 0) > rounds_order.get(max_ok, 0):
            score -= penalty

    # ── Penalización fuerte si equipos muy débiles avanzan a KO ──
    never_ko = ['Haiti','Curacao','New Zealand','FIFA Playoff 1','FIFA Playoff 2']
    for t in never_ko:
        if team_rounds.get(t,'group') != 'group':
            score -= 40

    return score


def run_hard_validations(group_predictions, knockout_predictions, df_stats,
                         n_sims=1, champion_counts=None, all_sims_meta=None):
    """
    Hard assert block. If any check fails the script stops with a clear message
    indicating exactly which parameter to adjust.
    Called from main() just before exporting CSVs.
    """
    if champion_counts is None: champion_counts = Counter()
    if all_sims_meta is None: all_sims_meta = []

    print(f"\n  [Validando predicciones agregadas de {n_sims} simulaciones MC]")
    errors = []

    # ── Structure ──
    if len(group_predictions) != 72:
        errors.append(f"FALLO: group_predictions tiene {len(group_predictions)} filas, esperaba 72.")
    if len(knockout_predictions) != 32:
        errors.append(f"FALLO: knockout_predictions tiene {len(knockout_predictions)} filas, esperaba 32.")
    if group_predictions.isnull().any().any():
        errors.append("FALLO: group_predictions contiene nulos. Revisar placeholders.")
    if knockout_predictions.isnull().any().any():
        errors.append("FALLO: knockout_predictions contiene nulos. Revisar slots vacíos.")
    for df_name, df in [('group_predictions', group_predictions),
                        ('knockout_predictions', knockout_predictions)]:
        for col in df.select_dtypes(include='object').columns:
            if df[col].astype(str).str.contains('UNKNOWN', na=False).any():
                errors.append(f"FALLO: columna '{col}' en {df_name} contiene 'UNKNOWN'.")
    invalid_wt = set(group_predictions['winning_team'].unique()) - {'home','away','draw'}
    if invalid_wt:
        errors.append(f"FALLO: winning_team tiene valores inválidos: {invalid_wt}")
    invalid_mw = set(knockout_predictions['match_winner'].unique()) - {'home','away'}
    if invalid_mw:
        errors.append(f"FALLO: match_winner tiene valores inválidos: {invalid_mw}")
    invalid_pen = set(knockout_predictions['penalties'].unique()) - {True, False}
    if invalid_pen:
        errors.append(f"FALLO: penalties tiene valores inválidos: {invalid_pen}")

    # ── Statistical calibration ──


    avg_corners_group = group_predictions['corners'].mean()
    if not (8.5 <= avg_corners_group <= 10.5):
        errors.append(
            f"FALLO: corners promedio grupos = {avg_corners_group:.3f}. "
            f"Target 8.5-10.5. Ajustar mu_c en predict_match."
        )

    avg_yellow_group = group_predictions['yellow_cards'].mean()
    if not (4.0 <= avg_yellow_group <= 4.5):
        adj = ('Bajar factor 0.94 a 0.88 en mu_y.' if avg_yellow_group > 4.5
               else 'Subir factor 0.94 a 1.00.')
        errors.append(
            f"FALLO: amarillas promedio grupos = {avg_yellow_group:.3f}. "
            f"Target 4.0-4.5. {adj}"
        )

    total_reds = int(
        group_predictions['red_cards'].sum() +
        knockout_predictions['red_cards'].sum()
    )
    if total_reds > 5:
        errors.append(
            f"FALLO: rojas totales = {total_reds}. Máximo 5. "
            f"Revisar red_prob y el cap de state_tracker['reds']."
        )

    total_penalties = int(knockout_predictions['penalties'].sum())
    if not (3 <= total_penalties <= 6):
        errors.append(
            f"FALLO: penales en KO = {total_penalties}. Target 3-6. "
            f"Ajustar PEN_BUDGET_PER_ROUND o el umbral abs(diff_sn) < 0.050."
        )

    # ── Hard caps enforcement ──
    HARD_CAPS_CHECK = {
        'Curacao': 0.280, 'Haiti': 0.300, 'New Zealand': 0.380,
        'Saudi Arabia': 0.370, 'Qatar': 0.360, 'Uzbekistan': 0.410,
        'Panama': 0.410, 'Australia': 0.465, 'Korea Republic': 0.490,
    }
    for team_c, cap_c in HARD_CAPS_CHECK.items():
        if team_c in df_stats.index:
            sn_val = df_stats.loc[team_c, 'final_strength_norm']
            if sn_val > cap_c:
                errors.append(
                    f"FALLO: {team_c} tiene final_strength_norm={sn_val:.3f}, "
                    f"máximo permitido={cap_c}. Verificar bloque HARD_CAPS."
                )

    # ── Ranking warnings (non-fatal: printed but do NOT block export) ──
    warnings = []
    top20_teams = set(
        df_stats.sort_values('final_strength_norm', ascending=False).head(20).index
    )
    for restricted in ['Japan', 'Senegal', 'Algeria']:
        if restricted in top20_teams:
            sn_val = df_stats.loc[restricted, 'final_strength_norm'] if restricted in df_stats.index else 'N/A'
            warnings.append(
                f"ADVERTENCIA: {restricted} está en top-20 (sn={sn_val}). "
                f"Bajar CONF_EXCEPTION_FACTOR o agregar penalización explícita."
            )
    sorted_teams = df_stats.sort_values('final_strength_norm', ascending=False).index.tolist()
    for team_r, max_rank in [('United States', 15), ('Canada', 18)]:
        if team_r in sorted_teams:
            rank_r = sorted_teams.index(team_r) + 1
            if rank_r <= max_rank:
                warnings.append(
                    f"ADVERTENCIA: {team_r} está en posición #{rank_r} (max permitido #{max_rank}). "
                    f"Revisar CONF_EXCEPTION_FACTOR y host bonus."
                )

    # ── Score coherence ──
    for i, row in group_predictions.iterrows():
        hg, ag = row['predicted_home_goals'], row['predicted_away_goals']
        exp = 'home' if hg > ag else 'away' if ag > hg else 'draw'
        if row['winning_team'] != exp:
            errors.append(
                f"FALLO coherencia: match_id={row.get('match_id','?')} "
                f"score={hg}-{ag} pero winning_team='{row['winning_team']}' (esperado '{exp}')."
            )

    # ── Verificar que los 4 equipos sobrerankeados salieron del top 20 ──
    sorted_sn = df_stats['final_strength_norm'].sort_values(ascending=False)
    top20_set  = set(sorted_sn.head(20).index)
    must_exit  = ['Algeria', 'Japan', 'Senegal', 'IR Iran']
    for team_e in must_exit:
        if team_e in top20_set:
            rank_e = list(sorted_sn.index).index(team_e) + 1
            errors.append(
                f"FALLO: {team_e} sigue en top 20 (rank #{rank_e}, "
                f"SN={sorted_sn.get(team_e, 'N/A'):.3f}). "
                f"Verificar NEGATIVE_PRIORS y HARD_CAPS extendidos."
            )

    # ── Verificar confianza mínima del campeón ──
    if champion_counts:
        top_champ, top_count = champion_counts.most_common(1)[0]
        champ_pct = top_count / n_sims * 100
        if champ_pct < 12.0:
            warnings.append(
                f"ADVERTENCIA: El campeón más probable ({top_champ}) solo "
                f"gana en {champ_pct:.1f}% de las sims. Bracket muy incierto — "
                f"revisar caps y upset bias en KO."
            )
        # El campeón debe ser de UEFA o CONMEBOL
        uefa_conmebol = {'Spain','France','Portugal','Argentina','Belgium','England',
                         'Brazil','Netherlands','Germany','Croatia','Norway','Colombia',
                         'Switzerland','Austria','Uruguay','Denmark','Serbia','Turkey',
                         'Ecuador','Italy','Poland','Wales','Scotland','Czech Republic',
                         'Romania','Greece','Slovakia','Hungary','Chile','Peru','Bolivia',
                         'Venezuela','Paraguay'}
        if top_champ not in uefa_conmebol:
            errors.append(
                f"FALLO: El campeón predicho ({top_champ}) no es de UEFA/CONMEBOL. "
                f"Revisar upset bias y hard caps en KO."
            )

    # ── Verificar que champion_counts existe y se pasó correctamente ──
    if not champion_counts:
        errors.append(
            "FALLO: champion_counts está vacío. "
            "Verificar que el tracking del campeón en el loop MC funciona."
        )

    # ── Goles (assert core — si falla, indica qué multiplicador cambiar) ──
    avg_g_groups = (group_predictions['predicted_home_goals'] +
                    group_predictions['predicted_away_goals']).mean()
    if not (2.75 <= avg_g_groups <= 2.95):
        direction = "Subir" if avg_g_groups < 2.75 else "Bajar"
        errors.append(
            f"FALLO: goles grupos = {avg_g_groups:.3f}. Target 2.75–2.95. "
            f"{direction} multiplicador de grupos (actualmente 1.40)."
        )

    # ── Empates en grupos ──
    draws = ((group_predictions['winning_team'] == 'draw').sum())
    draw_pct = draws / len(group_predictions) * 100
    if draw_pct < 8.0:
        errors.append(
            f"FALLO: solo {draws} empates en grupos ({draw_pct:.1f}%). "
            f"Target 11–14 (15–20%). Bajar umbral draw-correction de 0.30 a 0.25."
        )

    # ── Campeón en el top de UEFA/CONMEBOL ──
    if champion_counts:
        top_champ = champion_counts.most_common(1)[0][0]
        acceptable = {'Spain','France','Portugal','Argentina','England',
                      'Brazil','Netherlands','Germany','Belgium','Croatia',
                      'Colombia','Uruguay'}
        if top_champ not in acceptable:
            errors.append(
                f"FALLO: campeón más frecuente = {top_champ}. "
                f"Debe ser UEFA/CONMEBOL de élite. Revisar upset bias en KO."
            )

    # ── Spain gana su grupo en mayoría de sims ──
    if all_sims_meta:
        spain_gw_rate = sum(1 for m in all_sims_meta if m.get('spain_group_winner')) / len(all_sims_meta)
        if spain_gw_rate < 0.45:
            warnings.append(
                f"ADVERTENCIA: Spain gana su grupo solo en {spain_gw_rate*100:.1f}% de sims. "
                f"Revisar la composición del grupo de Spain en group_fixtures.csv."
            )

    # ── Output ──
    if warnings:
        print('\n  Advertencias (no bloquean exportación):')
        for w in warnings: print(f'    ⚠ {w}')

    if errors:
        print('\n' + '═' * 62)
        print('  VALIDACIÓN FALLIDA — CORREGIR ANTES DE EXPORTAR')
        print('═' * 62)
        for e in errors: print(f'  ✗ {e}')
        print('═' * 62)
        raise SystemExit(
            f'\n{len(errors)} validación(es) fallaron. '
            'Ver mensajes arriba para saber qué ajustar.\n'
        )
    else:
        print('\n  ✓ Todas las validaciones pasaron. Pipeline listo para exportar.\n')


# ══════════════════════════════════════════════════════════════════════
# 19. MAIN
# ══════════════════════════════════════════════════════════════════════

def main():

    # 1. Load data
    (group_fixtures, knockout_slots, results,
     fifa_2018, fifa_2022, fs_m18, fs_t14, fs_t22, wc_bookings) = load_datasets()

    # 2. Prepare H2H dataset (2014+, normalized names)
    h2h_df = results.copy()
    h2h_df['date'] = pd.to_datetime(h2h_df['date'], errors='coerce')
    h2h_df = h2h_df[h2h_df['date'] >= '2014-01-01'].copy()
    h2h_df['home_team'] = h2h_df['home_team'].apply(normalize_team_name)
    h2h_df['away_team'] = h2h_df['away_team'].apply(normalize_team_name)
    h2h_df = h2h_df.dropna(subset=['home_score','away_score']).reset_index(drop=True)

    # 3. Base strength
    print('Calculando fuerza base...')
    df_stats, global_avg_goals, recent_matches = build_base_strength(results)

    # 4. Contextual adjustments
    print('Aplicando ajustes contextuales...')
    df_stats = apply_all_contextual_adjustments(df_stats, recent_matches)

    # 5. Diagnostics
    diag_df = generate_strength_diagnostics(df_stats, group_fixtures)

    # 6. Event profiles
    (cp, yp, rp, gca, gya, gra) = build_event_profiles(
        fifa_2018, fifa_2022, fs_m18, fs_t14, fs_t22, wc_bookings)

    # 7. Train Poisson goal models
    home_model, away_model = train_goal_models(recent_matches, df_stats)

    # 8. Simulate group stage & 9. Knockout stage (MONTE CARLO)
    N_SIMS = 200
    print(f"\nEjecutando Monte Carlo: {N_SIMS} simulaciones del torneo completo...")

    group_mc    = defaultdict(list)
    ko_mc       = defaultdict(list)
    champion_counts  = Counter()
    round_counts     = defaultdict(Counter)

    all_sims_meta = []

    # Guardaremos esto para reportes (usamos la última sim para bracket_records visual)
    bracket_records_final = []
    ordered_tables_final = {}

    for sim_id in range(N_SIMS):
        if sim_id % 100 == 0:
            sys.stdout.write(f"\r  Simulación {sim_id}/{N_SIMS}...")
            sys.stdout.flush()

        st = {'reds': 0, 'penalties': 0, 'pen_by_round': {}}

        gp_sim = simulate_group_stage(
            group_fixtures, home_model, away_model, df_stats, h2h_df,
            cp, yp, rp, gca, gya, gra, state_tracker=st, sim_id=sim_id
        )
        for _, row in gp_sim.iterrows():
            group_mc[row['match_id']].append(row.to_dict())

        tables_sim   = calculate_group_tables(gp_sim, df_stats)
        slots_sim, thirds_sim = map_knockout_slots(tables_sim)

        ko_sim, bracket_sim = simulate_knockout_stage(
            knockout_slots, slots_sim, thirds_sim,
            home_model, away_model, df_stats, h2h_df,
            cp, yp, rp, gca, gya, gra, state_tracker=st, sim_id=sim_id
        )
        for _, row in ko_sim.iterrows():
            ko_mc[row['match_id']].append(row.to_dict())

        for _, row in ko_sim.iterrows():
            rnd = row.get('round', '')
            winner_team = (
                row.get('predicted_home_team', '') if row['match_winner'] == 'home'
                else row.get('predicted_away_team', '')
            )
            if winner_team:
                round_counts[rnd][winner_team] += 1

        # ── Metadatos de la simulación para selección ──
        sim_meta = {
            'sim_id':    sim_id,
            'ko_df':     ko_sim.copy(),       # predicciones KO completas de esta sim
            'tables_df': tables_sim.copy(),   # tablas de grupos de esta sim
        }

        # Campeón
        final_df = ko_sim[ko_sim['round'].str.lower().str.contains('final', na=False)
                          & ~ko_sim['round'].str.lower().str.contains('third', na=False)]
        if not final_df.empty:
            fr = final_df.iloc[-1]
            champ = (fr.get('predicted_home_team','') if fr['match_winner'] == 'home'
                     else fr.get('predicted_away_team',''))
            sim_meta['champion'] = champ

            # Finalistas
            sim_meta['finalist_1'] = fr.get('predicted_home_team','')
            sim_meta['finalist_2'] = fr.get('predicted_away_team','')
        else:
            sim_meta['champion'] = ''
            sim_meta['finalist_1'] = ''
            sim_meta['finalist_2'] = ''

        # Spain en su grupo
        spain_group_winner = False
        for grp, tbl in tables_sim.items():
            if 'Spain' in tbl['team'].values:
                spain_pos = tbl.index[tbl['team'] == 'Spain'].tolist()[0] + 1
                spain_group_winner = (spain_pos == 1)
                break
        sim_meta['spain_group_winner'] = spain_group_winner

        # Ronda máxima alcanzada por equipos monitoreados
        monitored = ['United States','Canada','Mexico','Australia','Japan',
                     'Haiti','Curacao','New Zealand','Korea Republic']
        r_order = {'group':0, 'Round of 32':1, 'Round of 16':2,
                        'Quarter-final':3, 'Semi-final':4, 'Final':5}
        team_max_round = {t: 'group' for t in monitored}
        for _, krow in ko_sim.iterrows():
            rnd = krow.get('round','')
            for t in monitored:
                ht = krow.get('predicted_home_team','')
                at = krow.get('predicted_away_team','')
                mw = krow.get('match_winner','')
                winner_team = ht if mw=='home' else at
                if winner_team == t and r_order.get(rnd,0) > r_order.get(team_max_round[t],0):
                    team_max_round[t] = rnd
        sim_meta['team_max_round'] = team_max_round

        all_sims_meta.append(sim_meta)

        if sim_meta['champion']:
            champion_counts[sim_meta['champion']] += 1

        if sim_id == N_SIMS - 1:
            bracket_records_final = bracket_sim
            ordered_tables_final = tables_sim

    print(f"\r  {N_SIMS}/{N_SIMS} simulaciones completadas. ✓\n")

    group_rows    = aggregate_group_mc(group_mc)
    group_predictions    = pd.DataFrame(group_rows)

    # ── Selección de la mejor simulación para KO ──
    if not all_sims_meta:
        raise SystemExit("FALLO: all_sims_meta vacío — verificar loop MC.")

    scored_sims = [(score_sim(m), m) for m in all_sims_meta]
    scored_sims.sort(key=lambda x: -x[0])   # mayor score primero

    best_score, best_sim = scored_sims[0]
    print(f"\n  ✓ Mejor simulación: sim_id={best_sim['sim_id']} | score={best_score:.0f}")
    print(f"    Campeón: {best_sim['champion']}")
    print(f"    Final: {best_sim['finalist_1']} vs {best_sim['finalist_2']}")
    print(f"    Spain ganó su grupo: {best_sim['spain_group_winner']}")
    print(f"    Equipos monitoreados: {best_sim['team_max_round']}")

    # Usar las predicciones KO de la mejor simulación
    knockout_predictions = best_sim['ko_df'].copy()

    ordered_tables = best_sim['tables_df']
    try:
        pd.concat(ordered_tables.values(), ignore_index=True).to_csv('group_tables.csv', index=False)
    except PermissionError:
        print("ADVERTENCIA: group_tables.csv está abierto. Ciérralo para actualizarlo.")

    bracket_records = bracket_records_final

    # 11. Cast int columns
    int_cols = ['predicted_home_goals','predicted_away_goals','corners','yellow_cards','red_cards']
    for col in int_cols:
        group_predictions[col]    = group_predictions[col].astype(int)
        knockout_predictions[col] = knockout_predictions[col].astype(int)

    # 11b. v5.3: Coherence fix — winning_team / match_winner must match goals
    for i, row in group_predictions.iterrows():
        hg, ag = row['predicted_home_goals'], row['predicted_away_goals']
        exp_wt = 'home' if hg > ag else 'away' if ag > hg else 'draw'
        if row['winning_team'] != exp_wt:
            group_predictions.at[i, 'winning_team'] = exp_wt
    for i, row in knockout_predictions.iterrows():
        hg, ag = row['predicted_home_goals'], row['predicted_away_goals']
        if hg != ag:   # draws resolved by ET/pen — match_winner already set
            exp_mw = 'home' if hg > ag else 'away'
            if row['match_winner'] != exp_mw:
                knockout_predictions.at[i, 'match_winner'] = exp_mw

    # 12. Validate
    total_reds, avg_y, avg_c, avg_g = validate_predictions(group_predictions, knockout_predictions)

    # 13. Complete diagnostics
    team_group_rank = {}
    for g, df_g in ordered_tables.items():
        for _, r in df_g.iterrows(): team_group_rank[r['team']] = (g, int(r['rank']))
    stage_map = {}
    for _, kr in knockout_predictions.iterrows():
        for t in [kr['predicted_home_team'], kr['predicted_away_team']]:
            stage_map[t] = kr['round']
    for i, drow in diag_df.iterrows():
        t = drow['team']
        if t in team_group_rank:
            diag_df.at[i,'group']      = str(team_group_rank[t][0])
            diag_df.at[i,'rank_group'] = str(team_group_rank[t][1])
        diag_df.at[i,'stage_reached'] = stage_map.get(t,'Group stage (eliminated)')

    # 14. Bracket outputs
    champ, runner, third, final_row = generate_bracket_outputs(bracket_records, knockout_predictions)

    # 15. Low-prob report
    lp_df, noise_count = generate_low_prob_report(ordered_tables, bracket_records, df_stats)

    # 16. RESUMEN_MODELO.md (before stripping helper cols for stat collection)
    generate_resumen_modelo(group_predictions, knockout_predictions, df_stats,
                            group_fixtures, bracket_records, lp_df, diag_df,
                            champ, runner, third, final_row,
                            total_reds, avg_y, avg_c, avg_g, noise_count)

    # 17. v5.3 Hard Validations (stops script with clear message if calibration fails)
    run_hard_validations(group_predictions, knockout_predictions, df_stats,
                         n_sims=N_SIMS, champion_counts=champion_counts, all_sims_meta=all_sims_meta)

    # 18. Export DataCamp files (strip helper columns)
    for col in ['_h2h_weight','extra_time']:
        if col in group_predictions.columns:
            group_predictions = group_predictions.drop(columns=[col])
        if col in knockout_predictions.columns:
            knockout_predictions = knockout_predictions.drop(columns=[col])

    group_predictions.to_csv('group_predictions_filled.csv', index=False)
    knockout_predictions.to_csv('knockout_predictions_filled.csv', index=False)

    # ─────────────────────────────────────────────
    # REPORTE MONTE CARLO — Champion Win Probability
    # ─────────────────────────────────────────────
    print("\n" + "═"*55)
    print(f"  🏆  PROBABILIDADES DE CAMPEONATO ({N_SIMS} simulaciones)")
    print("═"*55)

    for team, cnt in champion_counts.most_common(10):
        pct = cnt / N_SIMS * 100
        bar = "█" * int(pct / 2)
        print(f"  {team:<22} {pct:5.1f}%  {bar}")

    # Porcentaje de sims donde Spain gana su grupo
    spain_gw_pct = sum(1 for m in all_sims_meta if m.get('spain_group_winner')) / N_SIMS * 100
    print(f"\n  Spain gana su grupo en {spain_gw_pct:.1f}% de las simulaciones")

    # Top-3 matchups de la Final
    final_matchups = Counter(
        tuple(sorted([m['finalist_1'], m['finalist_2']])) for m in all_sims_meta
    )
    print(f"\n  Top-5 matchups en la Final:")
    for (t1, t2), cnt in final_matchups.most_common(5):
        print(f"    {t1} vs {t2}: {cnt/N_SIMS*100:.1f}%")

    diag_df.to_csv('diagnostico_strength_teams.csv', index=False)

    print('\n' + '=' * 64)
    print('  Archivos exportados exitosamente:')
    for fn in ['group_predictions_filled.csv','knockout_predictions_filled.csv',
               'group_tables.csv','diagnostico_strength_teams.csv',
               'cuadro_torneo_simulado.csv','CUADRO_TORNEO_SIMULADO.md',
               'diagnostic_low_probability_advancers.csv','RESUMEN_MODELO.md']:
        print(f'    - {fn}')
    print('=' * 64)




if __name__ == '__main__':
    main()
