"""
15b_diagnose_vt_v3.py -- CarbonVayu mlv3 VT Engine Diagnostics
1. Decomposes each state's change: all-station vs matched-station vs no-COVID (excl. 2020)
   + delta_rec + delta_exp + matched station counts.
2. Sensitivity check: LOYO-cache monotone betas (sia=0.034) vs Production OOF betas (sia=0.156).
3. Joint (E, beta) calendar-week block bootstrap to check true pair-level C_ij discrimination.
"""
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from scipy.optimize import lsq_linear

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

CACHE = Path("results/v3_5yr/diagnostics/stage1_loyo_cache.parquet")
PROD_S2 = Path("models/v3_production/stage2_monotone_v3.json")
VT_V3 = Path("results/v3_5yr/vt_economy/VT_scores_v3_final.csv")
N_BOOT = 300

# 1. Load aligned 5-year data
base = pd.read_parquet("data/features_daily_2019_2023.parquet")
exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()
cache = pd.read_parquet(CACHE)
vt_v3 = pd.read_csv(VT_V3).set_index("state")

base["date"] = pd.to_datetime(base["date"])
exp["date"] = pd.to_datetime(exp["date"])
base["state"] = base["state"].replace({"TamilNadu": "Tamil Nadu"})

WEATHER = [
    "blh_mean", "blh_min", "t2m_c", "rh_pct", "u10", "v10", "wspd10",
    "precip_mm", "u925", "v925", "wspd925", "u850", "v850", "wspd850",
]
CALENDAR = ["doy_sin", "doy_cos", "day_of_week", "is_weekend"]
LOCAL = [
    "edgar_pm25_agriculture", "edgar_pm25_buildings", "edgar_pm25_ind_combustion",
    "edgar_pm25_power_industry", "edgar_pm25_transport", "edgar_pm25_waste",
    "edgar_pm25_total", "edgar_bc_total", "edgar_co_total", "edgar_nh3_total",
    "edgar_nox_total", "edgar_so2_total",
]
BINS = ["0_24h", "24_48h", "48_72h"]
SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES = [f"{s}_{b}" for s, b in SB]

df = base.dropna(subset=WEATHER + CALENDAR + LOCAL + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)
df["year"] = df["date"].dt.year
df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)

STATE_TO_NODE = {"Delhi": "ind_delhi", "Jammu & Kashmir": "ind_jk", "Jammu and Kashmir": "ind_jk"}
for st in sorted(df["state"].dropna().unique()):
    if st not in STATE_TO_NODE:
        cand = "ind_" + st.lower().replace(" ", "_").replace("&", "and")
        if cand in nodes:
            STATE_TO_NODE[st] = cand

st_counts = df["state"].value_counts()
STATES = sorted([s for s in st_counts[st_counts >= 100].index if s in STATE_TO_NODE])
IND_NODES = [STATE_TO_NODE[s] for s in STATES]
EXT_NODES = [n for n in nodes if n.startswith("ext_")]
ind_idx = [nodes.index(n) for n in IND_NODES]
ext_idx = [nodes.index(n) for n in EXT_NODES]
N_ST = len(STATES)

# 2. Load both beta sets: (A) LOYO-cache monotone betas, (B) Production OOF monotone betas
resid_full = df["pm25"].values.astype(np.float64) - cache["pred_c_full"].values
X_base = np.column_stack([
    exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).values for s, b in SB
]).astype(np.float64)

def to_mono_design(Xe):
    Xc = np.zeros_like(Xe)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        Xc[:, c0] = Xe[:, c0]
        Xc[:, c1] = Xe[:, c0] + Xe[:, c1]
        Xc[:, c2] = Xe[:, c0] + Xe[:, c1] + Xe[:, c2]
    return np.hstack([np.ones((len(Xc), 1)), Xc])

def solve_mono(AtA, Aty):
    d = np.sqrt(np.clip(np.diag(AtA), 1e-12, None))
    M = AtA / np.outer(d, d)
    L = np.linalg.cholesky(M + 1e-10 * np.eye(len(M)))
    z = solve_triangular(L, Aty / d, lower=True)
    sol = lsq_linear(L.T, z, bounds=(np.r_[-np.inf, np.zeros(9)], np.inf)).x / d
    rd = sol[1:]
    b = np.zeros(9)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        b[c2], b[c1], b[c0] = rd[c2], rd[c2] + rd[c1], rd[c2] + rd[c1] + rd[c0]
    return b

A_mono = to_mono_design(X_base)
b_cache = solve_mono(A_mono.T @ A_mono, A_mono.T @ resid_full)
prod_json = json.loads(PROD_S2.read_text())
b_prod = np.array([prod_json["betas"][k] for k in NAMES], dtype=np.float64)

# 3. DIAGNOSTIC 1: Delta Decomposition (All vs Matched vs No-COVID + Transport)
m_base = df["year"].isin([2019, 2020, 2021]).values
m_nocov = df["year"].isin([2019, 2021]).values
m_curr = df["year"].isin([2022, 2023]).values

def mean_exp_tensor(mask):
    E = np.zeros((N_ST, len(nodes), 9))
    for r, st in enumerate(STATES):
        rm = mask & (df["state"].values == st)
        if not rm.any():
            rm = df["state"].values == st
        for n_i, n in enumerate(nodes):
            for j, (s, b) in enumerate(SB):
                E[r, n_i, j] = float(exp.loc[rm, f"exp_{n}_{s}_{b}"].mean())
    return E

E_base = mean_exp_tensor(m_base)
E_curr = mean_exp_tensor(m_curr)
off = ~np.eye(N_ST, dtype=bool)

def transport_stats(E_tens, betas):
    T = np.einsum("rnj,j->nr", E_tens, betas)
    M_dom = T[ind_idx, :]
    rec = (M_dom * off).sum(axis=0) + T[ext_idx, :].sum(axis=0)
    exp_d = (M_dom * off).sum(axis=1)
    return rec, exp_d, M_dom

rec_b, exp_b, _ = transport_stats(E_base, b_cache)
rec_c, exp_c, M_cache = transport_stats(E_curr, b_cache)
rec_p, exp_p, M_prod = transport_stats(E_curr, b_prod)

diag_rows = []
for i, st in enumerate(STATES):
    sub = df[df["state"] == st]
    sb = sub[sub["year"].isin([2019, 2020, 2021])]
    sn = sub[sub["year"].isin([2019, 2021])]
    sc = sub[sub["year"].isin([2022, 2023])]

    st_b = set(sb["location_id"].unique())
    st_n = set(sn["location_id"].unique())
    st_c = set(sc["location_id"].unique())
    matched = st_b & st_c
    matched_nc = st_n & st_c

    raw_b = sb["pm25"].mean() if not sb.empty else np.nan
    raw_c = sc["pm25"].mean() if not sc.empty else np.nan
    raw_drop = raw_b - raw_c  # positive = improved

    if matched:
        mb = sb[sb["location_id"].isin(matched)].groupby("location_id")["pm25"].mean()
        mc = sc[sc["location_id"].isin(matched)].groupby("location_id")["pm25"].mean()
        match_drop = float((mb - mc).mean())
    else:
        match_drop = np.nan

    if matched_nc:
        mnb = sn[sn["location_id"].isin(matched_nc)].groupby("location_id")["pm25"].mean()
        mnc = sc[sc["location_id"].isin(matched_nc)].groupby("location_id")["pm25"].mean()
        nocov_drop = float((mnb - mnc).mean())
    else:
        nocov_drop = np.nan

    diag_rows.append({
        "state": st,
        "v3_rank": int(vt_v3.loc[st, "rank"]),
        "v3_vt": float(vt_v3.loc[st, "vt_score"]),
        "n_base": len(st_b), "n_curr": len(st_c), "n_match": len(matched),
        "raw_drop": raw_drop, "match_drop": match_drop, "nocov_drop": nocov_drop,
        "d_rec": rec_c[i] - rec_b[i], "d_exp": exp_c[i] - exp_b[i],
        "exp_cache": exp_c[i], "exp_prod": exp_p[i],
    })

diag_df = pd.DataFrame(diag_rows).sort_values("v3_rank")
print("\n=== DIAGNOSTIC 1: DELTA DECOMPOSITION & NETWORK-EXPANSION BIAS (positive drop = cleaner) ===")
print(diag_df.to_string(index=False))

# 4. DIAGNOSTIC 2: Joint (E, beta) Week-Block Bootstrap for Pairwise C_ij
print(f"\n=== DIAGNOSTIC 2: JOINT (E, beta) WEEK-BLOCK BOOTSTRAP ({N_BOOT}x) FOR TOP CORRIDORS ===")
ub_yw, inv_yw = np.unique(df["yw"].values, return_inverse=True)
W = len(ub_yw)
AtA_w = np.zeros((W, 10, 10))
Aty_w = np.zeros((W, 10))
for w in range(W):
    idx = np.where(inv_yw == w)[0]
    Aw = A_mono[idx]
    AtA_w[w] = Aw.T @ Aw
    Aty_w[w] = Aw.T @ resid_full[idx]

# Precompute weekly sums of exposure in scoring period (2022-2023) per receptor state x domestic source
yw_score_mask = np.isin(ub_yw // 100, [2022, 2023])
W_sc_idx = np.where(yw_score_mask)[0]

# Store weekly sum & count for each receptor state x domestic source x 9 params in 2022-2023
E_w_sum = np.zeros((len(W_sc_idx), N_ST, N_ST, 9), dtype=np.float64)
E_w_cnt = np.zeros((len(W_sc_idx), N_ST), dtype=np.float64)
sc_df_mask = df["year"].isin([2022, 2023]).values

for wi, w in enumerate(W_sc_idx):
    w_rows = np.where(inv_yw == w)[0]
    st_w = df["state"].values[w_rows]
    for r, st in enumerate(STATES):
        rm = w_rows[st_w == st]
        if len(rm) == 0:
            continue
        E_w_cnt[wi, r] = len(rm)
        for s_i, n in enumerate(IND_NODES):
            for j, (sec, b) in enumerate(SB):
                E_w_sum[wi, r, s_i, j] = exp[f"exp_{n}_{sec}_{b}"].values[rm].sum()

rng = np.random.default_rng(42)
M_joint_boot = np.zeros((N_BOOT, N_ST, N_ST), dtype=np.float64)
for k in range(N_BOOT):
    cnt_all = np.bincount(rng.integers(0, W, W), minlength=W).astype(float)
    bk = solve_mono(np.tensordot(cnt_all, AtA_w, 1), cnt_all @ Aty_w)
    cnt_sc = cnt_all[W_sc_idx]
    tot_cnt = np.maximum(cnt_sc @ E_w_cnt, 1.0)  # (N_ST,)
    E_k = np.tensordot(cnt_sc, E_w_sum, 1) / tot_cnt[:, None, None]  # (N_ST_rec, N_ST_src, 9)
    M_joint_boot[k] = np.einsum("rsj,j->sr", E_k, bk)  # (src, rec)

jb_mean = M_joint_boot.mean(axis=0)
jb_std = M_joint_boot.std(axis=0) + 1e-12
jb_lo = np.percentile(M_joint_boot, 2.5, axis=0)
jb_hi = np.percentile(M_joint_boot, 97.5, axis=0)
jb_snr = np.where(jb_lo > 0, jb_mean / jb_std, 0.0)
jb_conf = np.clip(jb_snr / (jb_snr + 1.5), 0.0, 0.99)

pair_rows = []
for i, src in enumerate(STATES):
    for j, dst in enumerate(STATES):
        if i != j and M_cache[i, j] >= 0.5:
            pair_rows.append({
                "src": src, "dst": dst,
                "harm_cache": M_cache[i, j], "harm_prod": M_prod[i, j],
                "joint_lo": jb_lo[i, j], "joint_hi": jb_hi[i, j],
                "joint_snr": jb_snr[i, j], "joint_C": jb_conf[i, j],
            })
pair_df = pd.DataFrame(pair_rows).sort_values("harm_cache", ascending=False)
print(pair_df.head(18).to_string(index=False))	
