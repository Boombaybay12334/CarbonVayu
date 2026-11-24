"""
15_vt_scoring_engine_v3.py -- CarbonVayu mlv3 Vaayu Token (VT) Economy Engine (v4 Logic)
Drop-in compatible with upload_to_supabase_v3.py and the deployed frontend.
Fixes all v3 audit findings:
  1. No-COVID (2019+2021 vs 2022-2023) matched-station trends + Empirical Bayes shrinkage
  2. Dual-pillar fixed-target score: 65% Accountable Standing + 35% Deadbanded Progress
  3. Smooth tanh mapping (500 + 200*tanh) -> comparable across years, no zero-width clips
  4. Joint (E, beta) calendar-week block bootstrap for honest VT CIs & pair C_ij
  5. Log-scaled fine claims (harm >= 1.0 ug/m3, C > 0.75, CI_low > 0) -> no 150-pt ceiling ties
"""
import time
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from scipy.optimize import lsq_linear

warnings.filterwarnings("ignore")
t0 = time.time()

OUT = Path("results/v3_5yr/vt_economy")
OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path("results/v3_5yr/diagnostics/stage1_loyo_cache.parquet")
N_BOOT = 300

pd.set_option("display.width", 220)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

if not CACHE.exists():
    raise SystemExit(f"{CACHE} not found -- run 13_diagnostics_and_placebos_v3.py first.")

TYPE_F = {
    "Arunachal Pradesh", "Meghalaya", "Mizoram", "Nagaland", "Manipur",
    "Tripura", "Sikkim", "Himachal Pradesh", "Uttarakhand", "Assam", "Goa",
}
TYPE_I = {
    "Maharashtra", "Gujarat", "Tamil Nadu", "Telangana", "Haryana",
    "Jharkhand", "Punjab", "West Bengal", "Andhra Pradesh", "Delhi",
}
RE_FRACTION = {
    "Karnataka": 0.72, "Rajasthan": 0.68, "Gujarat": 0.65, "Tamil Nadu": 0.62,
    "Himachal Pradesh": 0.90, "Uttarakhand": 0.85, "Arunachal Pradesh": 0.88,
    "Sikkim": 0.82, "Meghalaya": 0.75, "Manipur": 0.60, "Mizoram": 0.55,
    "Nagaland": 0.58, "Tripura": 0.30, "Assam": 0.25, "Kerala": 0.55,
    "Goa": 0.20, "Maharashtra": 0.42, "Madhya Pradesh": 0.45,
    "Chhattisgarh": 0.22, "Odisha": 0.20, "Jharkhand": 0.12,
    "West Bengal": 0.18, "Uttar Pradesh": 0.32, "Bihar": 0.15,
    "Punjab": 0.28, "Haryana": 0.30, "Telangana": 0.50, "Delhi": 0.10,
    "Andhra Pradesh": 0.58, "Chandigarh": 0.15, "Puducherry": 0.20,
}
ARCH_WEIGHTS = {
    "F": (0.10, 0.15, 0.35, 0.25, 0.15),
    "I": (0.35, 0.25, 0.10, 0.15, 0.15),
    "M": (0.20, 0.20, 0.20, 0.20, 0.20),
}

def get_archetype(state: str) -> str:
    return "F" if state in TYPE_F else ("I" if state in TYPE_I else "M")

# ------------------------------------------------------------------ 1. Load & Align
print("[1/6] Loading 5-year features, exposures, and cached Stage-1 LOYO residuals...")
base = pd.read_parquet("data/features_daily_2019_2023.parquet")
exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()
cache = pd.read_parquet(CACHE)

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

df = base.dropna(subset=WEATHER + CALENDAR + LOCAL + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)
assert len(df) == len(cache), f"Cache mismatch: {len(cache)} vs {len(df)}"

df["year"] = df["date"].dt.year
df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)
y_all = df["pm25"].values.astype(np.float64)
resid_full = y_all - cache["pred_c_full"].values

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

# ------------------------------------------------------------------ 2. Joint (E, beta) Week-Block Bootstrap
print(f"[2/6] Fitting Monotone-Decay betas + {N_BOOT}x JOINT (E, beta) calendar-week bootstrap...")
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
    b = np.zeros(9, dtype=np.float64)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        b[c2], b[c1], b[c0] = rd[c2], rd[c2] + rd[c1], rd[c2] + rd[c1] + rd[c0]
    return b

A_mono = to_mono_design(X_base)
ub_yw, inv_yw = np.unique(df["yw"].values, return_inverse=True)
W = len(ub_yw)
AtA_w = np.zeros((W, 10, 10))
Aty_w = np.zeros((W, 10))
for w in range(W):
    idx = np.where(inv_yw == w)[0]
    Aw = A_mono[idx]
    AtA_w[w] = Aw.T @ Aw
    Aty_w[w] = Aw.T @ resid_full[idx]

b_pt = solve_mono(AtA_w.sum(axis=0), Aty_w.sum(axis=0))

# Precompute weekly exposure sums in scoring period (2022-2023) for joint resampling
W_sc_idx = np.where(np.isin(ub_yw // 100, [2022, 2023]))[0]
E_w_sum = np.zeros((len(W_sc_idx), N_ST, len(nodes), 9), dtype=np.float64)
E_w_cnt = np.zeros((len(W_sc_idx), N_ST), dtype=np.float64)

for wi, w in enumerate(W_sc_idx):
    w_rows = np.where(inv_yw == w)[0]
    st_w = df["state"].values[w_rows]
    for r, st in enumerate(STATES):
        rm = w_rows[st_w == st]
        if len(rm) == 0:
            continue
        E_w_cnt[wi, r] = len(rm)
        for n_i, n in enumerate(nodes):
            for j, (sec, b) in enumerate(SB):
                E_w_sum[wi, r, n_i, j] = exp[f"exp_{n}_{sec}_{b}"].values[rm].sum()

E_score_pt = E_w_sum.sum(axis=0) / np.maximum(E_w_cnt.sum(axis=0)[:, None, None], 1.0)
T_all_pt = np.einsum("rnj,j->nr", E_score_pt, b_pt)
M_dom_pt = T_all_pt[ind_idx, :]
ext_rec_pt = T_all_pt[ext_idx, :].sum(axis=0)

rng = np.random.default_rng(42)
M_dom_boot = np.zeros((N_BOOT, N_ST, N_ST), dtype=np.float64)
ext_rec_boot = np.zeros((N_BOOT, N_ST), dtype=np.float64)
for k in range(N_BOOT):
    cnt_all = np.bincount(rng.integers(0, W, W), minlength=W).astype(float)
    bk = solve_mono(np.tensordot(cnt_all, AtA_w, 1), cnt_all @ Aty_w)
    cnt_sc = cnt_all[W_sc_idx]
    tot_cnt = np.maximum(cnt_sc @ E_w_cnt, 1.0)
    E_k = np.tensordot(cnt_sc, E_w_sum, 1) / tot_cnt[:, None, None]
    T_k = np.einsum("rnj,j->nr", E_k, bk)
    M_dom_boot[k] = T_k[ind_idx, :]
    ext_rec_boot[k] = T_k[ext_idx, :].sum(axis=0)

# Joint bootstrap confidence C[i, j]
jb_mean = M_dom_boot.mean(axis=0)
jb_std = M_dom_boot.std(axis=0) + 1e-12
jb_lo = np.percentile(M_dom_boot, 2.5, axis=0)
jb_hi = np.percentile(M_dom_boot, 97.5, axis=0)
jb_snr = np.where(jb_lo > 0, jb_mean / jb_std, 0.0)
C_mat = np.clip(jb_snr / (jb_snr + 1.5), 0.0, 0.99)
np.fill_diagonal(C_mat, 1.0)

pd.DataFrame(M_dom_pt, index=STATES, columns=STATES).to_csv(OUT / "M2_matrix_v3_ugm3.csv")
pd.DataFrame(C_mat, index=STATES, columns=STATES).to_csv(OUT / "M2_confidence_v3_boot.csv")

m_score = df["year"].isin([2022, 2023]).values
src_edgar_mean = np.array([
    float(df.loc[m_score & (df["state"] == s), "edgar_pm25_total"].mean()) for s in STATES
])
pd.DataFrame(M_dom_pt / np.maximum(src_edgar_mean[:, None], 1e-9), index=STATES, columns=STATES).to_csv(
    OUT / "transfer_rates_v3_per_edgar.csv"
)

# ------------------------------------------------------------------ 3. Matched No-COVID Trends & M3 Effort
print("[3/6] Computing matched no-COVID (2019+2021 vs 2022-2023) trends & M3 Effort...")
BASE_YEARS = [2019, 2021]   # Excludes 2020 COVID lockdown anomaly
SCORING_YEARS = [2022, 2023]
EB_PRIOR_N = 5.0            # Empirical Bayes shrinkage prior weight

m3_rows = []
for i, st in enumerate(STATES):
    arch = get_archetype(st)
    w1, w2, w3, w4, w5 = ARCH_WEIGHTS[arch]
    sub = df[df["state"] == st]
    sb = sub[sub["year"].isin(BASE_YEARS)]
    sc = sub[sub["year"].isin(SCORING_YEARS)]

    pm_curr = float(sc["pm25"].mean()) if not sc.empty else float(sub["pm25"].mean())
    matched = set(sb["location_id"].unique()) & set(sc["location_id"].unique())
    n_match = len(matched)

    if n_match > 0:
        mb = sb[sb["location_id"].isin(matched)].groupby("location_id")["pm25"].mean()
        mc = sc[sc["location_id"].isin(matched)].groupby("location_id")["pm25"].mean()
        pm_base_matched = float(mb.mean())
        raw_drop_ugm3 = float((mb - mc).mean())  # positive = cleaner
        # Empirical Bayes shrinkage toward 0 for small-n states
        shrunk_drop_ugm3 = (n_match / (n_match + EB_PRIOR_N)) * raw_drop_ugm3
    else:
        pm_base_matched = pm_curr
        raw_drop_ugm3 = 0.0
        shrunk_drop_ugm3 = 0.0

    # S1: EDGAR PM2.5 emission trajectory (2019 -> 2022)
    e19 = float(sub.loc[sub["year"] == 2019, "edgar_pm25_total"].mean())
    e22 = float(sub.loc[sub["year"] == 2022, "edgar_pm25_total"].mean())
    if np.isfinite(e19) and e19 > 0 and np.isfinite(e22):
        emi_delta = (e22 - e19) / e19
        s1 = float(np.clip(1.0 - (emi_delta / 0.05), 0.0, 1.0))
    else:
        emi_delta, s1 = 0.0, 0.5

    # S2: Renewable energy fraction
    s2 = float(RE_FRACTION.get(st, 0.35))
    # S3: Clean-air standing (inverse PM2.5 relative to 120 ug/m3)
    s3 = float(np.clip(1.0 - (pm_curr / 120.0), 0.0, 1.0))
    # S4: Matched no-COVID CPCB PM2.5 trend (deadbanded +/- 3 ug/m3)
    eff_drop = np.sign(shrunk_drop_ugm3) * max(abs(shrunk_drop_ugm3) - 3.0, 0.0)
    s4 = float(np.clip(0.5 + (eff_drop / 30.0), 0.0, 1.0))
    # S5: Real CPCB NAAQS daily compliance rate (PM2.5 <= 60 ug/m3)
    s5 = float((sc["pm25"] <= 60.0).mean()) if not sc.empty else float((sub["pm25"] <= 60.0).mean())

    s_bar = w1 * s1 + w2 * s2 + w3 * s3 + w4 * s4 + w5 * s5
    eff = float(np.clip(0.5 + 1.5 * s_bar, 0.5, 2.0))

    m3_rows.append({
        "state": st, "archetype": arch, "n_matched_stations": n_match,
        "pm25_base": pm_base_matched, "pm25_curr": pm_curr,
        "matched_drop_ugm3": raw_drop_ugm3, "shrunk_drop_ugm3": shrunk_drop_ugm3,
        "emi_delta_19_22": emi_delta, "S1_emi_trend": s1, "S2_renewable": s2,
        "S3_clean_sink": s3, "S4_cpcb_trend": s4, "S5_naaqs_comp": s5,
        "effort_multiplier": eff,
    })

m3_df = pd.DataFrame(m3_rows)
m3_df.to_csv(OUT / "M3_effort_v3.csv", index=False)

# ------------------------------------------------------------------ 4. Fixed-Target Dual-Pillar VT Scoring
print("[4/6] Computing Fixed-Target Dual-Pillar VT Scores + Joint Bootstrap 95% CIs...")
pm_curr_vec = m3_df["pm25_curr"].values
pm_base_vec = m3_df["pm25_base"].values
shrunk_drop_vec = m3_df["shrunk_drop_ugm3"].values
eff_vec = m3_df["effort_multiplier"].values
off_mask = ~np.eye(N_ST, dtype=bool)

def compute_vt_vector(M_dom, ext_rec):
    rec_dom = (M_dom * off_mask).sum(axis=0)
    rec_tot = rec_dom + ext_rec
    exp_dom = (M_dom * off_mask).sum(axis=1)

    # Accountable PM2.5 burden = victim-protected local PM2.5 + exported harm
    acct_curr = np.maximum(pm_curr_vec - rec_tot, 0.0) + exp_dom

    # Pillar 1 (65%): Fixed-target Distance-to-Target standing (15 ug/m3 = 1.0, 60 = 0.5, 105 = 0.0)
    p_stand = np.clip((105.0 - acct_curr) / (105.0 - 15.0), 0.0, 1.0)

    # Pillar 2 (35%): Matched no-COVID progress with +/- 3 ug/m3 noise deadband
    deadbanded = np.sign(shrunk_drop_vec) * np.maximum(np.abs(shrunk_drop_vec) - 3.0, 0.0)
    p_prog = np.clip(0.5 + (deadbanded / 35.0), 0.0, 1.0)

    # Composite modulated gently by M3 effort multiplier
    raw_score = (0.65 * p_stand + 0.35 * p_prog) * np.power(eff_vec, 0.35)

    # Fixed-target smooth squash around 0.50 -> (300, 700), comparable across years
    vt = 500.0 + 200.0 * np.tanh((raw_score - 0.50) / 0.28)
    return vt, rec_dom, ext_rec, exp_dom, acct_curr, p_stand, p_prog, raw_score

vt_pt, rec_dom_pt, ext_rec_pt, exp_dom_pt, acct_curr_pt, p_stand_pt, p_prog_pt, raw_sc_pt = compute_vt_vector(
    M_dom_pt, ext_rec_pt
)

vt_boot = np.zeros((N_BOOT, N_ST), dtype=np.float64)
for k in range(N_BOOT):
    vt_boot[k], *_ = compute_vt_vector(M_dom_boot[k], ext_rec_boot[k])

vt_df = m3_df[["state", "archetype", "pm25_base", "pm25_curr", "effort_multiplier"]].copy()
vt_df["received_dom_ugm3"] = rec_dom_pt
vt_df["received_ext_ugm3"] = ext_rec_pt
vt_df["exported_dom_ugm3"] = exp_dom_pt
vt_df["acct_burden_base"] = pm_base_vec
vt_df["acct_burden_curr"] = acct_curr_pt
vt_df["rel_improvement"] = p_prog_pt
vt_df["adj_improvement"] = raw_sc_pt
vt_df["vt_score"] = vt_pt
vt_df["vt_ci_low"] = np.percentile(vt_boot, 2.5, axis=0)
vt_df["vt_ci_high"] = np.percentile(vt_boot, 97.5, axis=0)
vt_df = vt_df.sort_values("vt_score", ascending=False).reset_index(drop=True)
vt_df["rank"] = np.arange(1, len(vt_df) + 1)
vt_df.to_csv(OUT / "VT_scores_v3_final.csv", index=False)

# ------------------------------------------------------------------ 5. Log-Scaled Fine Claims (Joint Bootstrap Gated)
print("[5/6] Generating joint-bootstrap-gated, log-scaled fine claims (harm >= 1.0 ug/m3)...")
HARM_FLOOR = 1.0
elig_pairs = []
for i, src in enumerate(STATES):
    for j, dst in enumerate(STATES):
        if i != j and C_mat[i, j] > 0.75 and jb_lo[i, j] > 0.0 and M_dom_pt[i, j] >= HARM_FLOOR:
            elig_pairs.append((i, j, src, dst, M_dom_pt[i, j], M_dom_pt[i, j] * C_mat[i, j]))

claim_rows = []
if elig_pairs:
    units_arr = np.array([p[5] for p in elig_pairs])
    u_min, u_max = float(units_arr.min()), float(units_arr.max())
    log_denom = max(np.log(u_max / max(u_min, 1e-9)), 1e-6)
    for i, j, src, dst, harm, units in elig_pairs:
        fine_pts = 20.0 + 130.0 * (np.log(units / u_min) / log_denom) if u_max > u_min else 85.0
        claim_rows.append({
            "defendant": src, "claimant": dst,
            "harm_ugm3": harm, "harm_ci_low": jb_lo[i, j], "harm_ci_high": jb_hi[i, j],
            "confidence": C_mat[i, j], "fine_vt_units": units, "fine_vt_points": round(float(fine_pts), 1),
        })

claims_df = pd.DataFrame(claim_rows).sort_values("fine_vt_points", ascending=False)
claims_df.to_csv(OUT / "fine_claims_v3.csv", index=False)

# Attribution network
net_rows = []
for i in range(N_ST):
    for j in range(i + 1, N_ST):
        a, b = STATES[i], STATES[j]
        hab, hba = M_dom_pt[i, j], M_dom_pt[j, i]
        net = hab - hba
        agg, vic = (a, b) if net >= 0 else (b, a)
        net_rows.append({
            "state_A": a, "state_B": b, "harm_A_to_B_ugm3": hab, "harm_B_to_A_ugm3": hba,
            "net_harm_ugm3": abs(net), "net_aggressor": agg, "net_victim": vic,
            "conf_A_to_B": C_mat[i, j], "conf_B_to_A": C_mat[j, i],
        })
pd.DataFrame(net_rows).sort_values("net_harm_ugm3", ascending=False).to_csv(
    OUT / "attribution_network_v3.csv", index=False
)

# ------------------------------------------------------------------ 6. Print Summary
print(f"\n=== VAAYU TOKEN (VT) SCORES v4 (Fixed-Target, No-COVID Matched, Joint Bootstrap) ===")
print(vt_df[["rank", "state", "archetype", "pm25_curr", "received_dom_ugm3", "exported_dom_ugm3",
             "acct_burden_curr", "effort_multiplier", "vt_score", "vt_ci_low", "vt_ci_high"]].to_string(index=False))

print(f"\n=== LOG-SCALED FINE CLAIMS (C > 0.75, Joint CI_low > 0, harm >= {HARM_FLOOR:.1f} ug/m3) ===")
print(f"Total eligible inter-state claims: {len(claims_df)}")
print(claims_df.to_string(index=False))
print(f"\nSaved all outputs to {OUT}/ in {time.time() - t0:.1f}s")
