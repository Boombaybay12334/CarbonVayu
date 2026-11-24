"""
15_vt_scoring_engine_v3.py -- CarbonVayu mlv3 Vaayu Token (VT) Economy Engine
Connects the validated 5-year (2019-2023) Monotone-Decay transport attribution model
to the full VT scoring, M3 effort multiplier, bootstrap-gated fine-claims, and
emission-normalized transfer-rate pipeline.

Fixes all v1 calibration issues:
  - Uses empirically validated 5-year PM2.5 transport (no 1-centroid 1/d^2 heuristic)
  - Replaces broken Abs<=2E cap with baseline-normalized accountable PM2.5 burden
  - Replaces hardcoded S4/S5 with real CPCB PM2.5 trend & NAAQS (<=60 ug/m3) compliance
  - Replaces hardcoded corridor priors with calendar-week bootstrap confidence gating
  - Propagates 300x calendar-week bootstrap uncertainty into VT score 95% CIs
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
VT_SCALE = 65.0  # Tuned down from v1's 85.0 to prevent top-tail saturation at 700

pd.set_option("display.width", 220)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

if not CACHE.exists():
    raise SystemExit(f"{CACHE} not found -- run 13_diagnostics_and_placebos_v3.py first.")

# ------------------------------------------------------------------ 1. Metadata & Archetypes
TYPE_F = {
    "Arunachal Pradesh", "Meghalaya", "Mizoram", "Nagaland", "Manipur",
    "Tripura", "Sikkim", "Himachal Pradesh", "Uttarakhand", "Assam", "Goa",
}
TYPE_I = {
    "Maharashtra", "Gujarat", "Tamil Nadu", "Telangana", "Haryana",
    "Jharkhand", "Punjab", "West Bengal", "Andhra Pradesh", "Delhi",
}
# MNRE renewable grid share baseline (from v1 Appendix A)
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
    "F": (0.10, 0.15, 0.35, 0.25, 0.15),  # S1, S2, S3, S4, S5
    "I": (0.35, 0.25, 0.10, 0.15, 0.15),
    "M": (0.20, 0.20, 0.20, 0.20, 0.20),
}

def get_archetype(state: str) -> str:
    if state in TYPE_F:
        return "F"
    if state in TYPE_I:
        return "I"
    return "M"

# ------------------------------------------------------------------ 2. Load & Align 5-Year Data
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
df["month"] = df["date"].dt.month
df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)
y_all = df["pm25"].values.astype(np.float64)
resid_full = y_all - cache["pred_c_full"].values

# Map Indian states <-> EDGAR nodes
STATE_TO_NODE = {"Delhi": "ind_delhi", "Jammu & Kashmir": "ind_jk", "Jammu and Kashmir": "ind_jk"}
for st in sorted(df["state"].dropna().unique()):
    if st not in STATE_TO_NODE:
        cand = "ind_" + st.lower().replace(" ", "_").replace("&", "and")
        if cand in nodes:
            STATE_TO_NODE[st] = cand

# Keep states with >= 100 station-days across 2019-2023 and a matching EDGAR node
st_counts = df["state"].value_counts()
STATES = sorted([s for s in st_counts[st_counts >= 100].index if s in STATE_TO_NODE])
NODE_TO_STATE = {STATE_TO_NODE[s]: s for s in STATES}
IND_NODES = [STATE_TO_NODE[s] for s in STATES]
EXT_NODES = [n for n in nodes if n.startswith("ext_")]
N_ST = len(STATES)
print(f"  Modeled Indian states: {N_ST} | External transboundary nodes: {len(EXT_NODES)}")

# ------------------------------------------------------------------ 3. Monotone-Decay Fit + 300x Week Bootstrap
print(f"[2/6] Fitting Monotone-Decay Stage-2 betas + {N_BOOT}x calendar-week block bootstrap...")
X_base = np.column_stack([
    exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).values for s, b in SB
]).astype(np.float64)

def to_monotone_design(Xe):
    Xc = np.zeros_like(Xe)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        Xc[:, c0] = Xe[:, c0]
        Xc[:, c1] = Xe[:, c0] + Xe[:, c1]
        Xc[:, c2] = Xe[:, c0] + Xe[:, c1] + Xe[:, c2]
    return np.hstack([np.ones((len(Xc), 1)), Xc])

def solve_mono_normal(AtA, Aty):
    d = np.sqrt(np.clip(np.diag(AtA), 1e-12, None))
    M = AtA / np.outer(d, d)
    L = np.linalg.cholesky(M + 1e-10 * np.eye(len(M)))
    z = solve_triangular(L, Aty / d, lower=True)
    lb = np.r_[-np.inf, np.zeros(9)]
    sol = lsq_linear(L.T, z, bounds=(lb, np.inf)).x / d
    raw_d = sol[1:]
    betas = np.zeros(9, dtype=np.float64)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        betas[c2] = raw_d[c2]
        betas[c1] = raw_d[c2] + raw_d[c1]
        betas[c0] = raw_d[c2] + raw_d[c1] + raw_d[c0]
    return sol[0], betas

A_mono = to_monotone_design(X_base)
ub_yw, inv_yw = np.unique(df["yw"].values, return_inverse=True)
W = len(ub_yw)
AtA_w = np.zeros((W, 10, 10))
Aty_w = np.zeros((W, 10))
for w in range(W):
    idx = np.where(inv_yw == w)[0]
    Aw = A_mono[idx]
    AtA_w[w] = Aw.T @ Aw
    Aty_w[w] = Aw.T @ resid_full[idx]

_, b_pt = solve_mono_normal(AtA_w.sum(axis=0), Aty_w.sum(axis=0))
rng = np.random.default_rng(42)
boot_b = np.zeros((N_BOOT, 9), dtype=np.float64)
for k in range(N_BOOT):
    cnt = np.bincount(rng.integers(0, W, W), minlength=W).astype(float)
    _, boot_b[k] = solve_mono_normal(np.tensordot(cnt, AtA_w, 1), cnt @ Aty_w)

print("  Monotone-Decay Point Betas (agri/other/sia x 3 bins):", np.round(b_pt, 4))

# ------------------------------------------------------------------ 4. Build State-to-State Transport Tensor (Point + Bootstrap)
print("[3/6] Computing State-to-State Transport Matrix (ug/m3) & Bootstrap Confidence...")
# Precompute mean exposure tensor E_mean[receptor_state, source_node, 9] for scoring period (2022-2023)
# and baseline period (2019-2021)
SCORING_YEARS = [2022, 2023]
BASE_YEARS = [2019, 2020, 2021]

m_score = df["year"].isin(SCORING_YEARS).values
m_base = df["year"].isin(BASE_YEARS).values

def build_exposure_tensor(mask):
    E_tens = np.zeros((N_ST, len(nodes), 9), dtype=np.float64)
    for r_idx, st in enumerate(STATES):
        rm = mask & (df["state"].values == st)
        if not np.any(rm):
            # Fallback to all-5-year mean if a state had no stations in early baseline years
            rm = df["state"].values == st
        for n_idx, n in enumerate(nodes):
            for j, (s, b) in enumerate(SB):
                E_tens[r_idx, n_idx, j] = float(exp.loc[rm, f"exp_{n}_{s}_{b}"].mean())
    return E_tens

E_score = build_exposure_tensor(m_score)
E_base = build_exposure_tensor(m_base)

# T_all_pt[source_node, receptor_state] in ug/m3
T_all_pt = np.einsum("rnj,j->nr", E_score, b_pt)              # (35, N_ST)
T_all_boot = np.einsum("rnj,kj->knr", E_score, boot_b)        # (N_BOOT, 35, N_ST)
T_base_pt = np.einsum("rnj,j->nr", E_base, b_pt)              # (35, N_ST)

# Extract domestic N_ST x N_ST matrix M_dom[src_state, rec_state] (ug/m3)
ind_node_idx = [nodes.index(n) for n in IND_NODES]
ext_node_idx = [nodes.index(n) for n in EXT_NODES]

M_dom_pt = T_all_pt[ind_node_idx, :]                          # (N_ST, N_ST)
M_dom_boot = T_all_boot[:, ind_node_idx, :]                   # (N_BOOT, N_ST, N_ST)
M_dom_base = T_base_pt[ind_node_idx, :]

# External transboundary inflow received by each Indian state (e.g. Pakistan, Nepal, Bangladesh)
ext_rec_pt = T_all_pt[ext_node_idx, :].sum(axis=0)            # (N_ST,)
ext_rec_boot = T_all_boot[:, ext_node_idx, :].sum(axis=1)     # (N_BOOT, N_ST)
ext_rec_base = T_base_pt[ext_node_idx, :].sum(axis=0)

# Bootstrap confidence C[i, j]: probability that M_dom_boot[:, i, j] > 0 & signal-to-noise reliability
boot_mean = M_dom_boot.mean(axis=0)
boot_std = M_dom_boot.std(axis=0) + 1e-12
boot_lo = np.percentile(M_dom_boot, 2.5, axis=0)
boot_hi = np.percentile(M_dom_boot, 97.5, axis=0)
# Smooth empirical confidence in [0, 1] from bootstrap z-ratio (z / (z + 1)), zeroed if CI touches 0
z_snr = np.where(boot_lo > 0, boot_mean / boot_std, 0.0)
C_mat = np.clip(z_snr / (z_snr + 1.5), 0.0, 0.99)
np.fill_diagonal(C_mat, 1.0)

# Save domestic M2 matrix & confidence
pd.DataFrame(M_dom_pt, index=STATES, columns=STATES).to_csv(OUT / "M2_matrix_v3_ugm3.csv")
pd.DataFrame(C_mat, index=STATES, columns=STATES).to_csv(OUT / "M2_confidence_v3_boot.csv")

# Emission-normalized Transfer Rate Matrix K[src, rec] (ug/m3 per unit source EDGAR PM2.5)
src_edgar_mean = np.array([
    float(df.loc[m_score & (df["state"] == s), "edgar_pm25_total"].mean()) for s in STATES
])
K_transfer = M_dom_pt / np.maximum(src_edgar_mean[:, None], 1e-9)
pd.DataFrame(K_transfer, index=STATES, columns=STATES).to_csv(OUT / "transfer_rates_v3_per_edgar.csv")

# ------------------------------------------------------------------ 5. M3 Effort Multiplier (Real CPCB + EDGAR)
print("[4/6] Computing upgraded M3 Effort Multiplier (real CPCB trend & NAAQS compliance)...")
m3_rows = []
for i, st in enumerate(STATES):
    arch = get_archetype(st)
    w1, w2, w3, w4, w5 = ARCH_WEIGHTS[arch]

    sub_all = df[df["state"] == st]
    sub_base = sub_all[sub_all["year"].isin(BASE_YEARS)]
    sub_curr = sub_all[sub_all["year"].isin(SCORING_YEARS)]
    if sub_base.empty:
        sub_base = sub_all

    # S1: Real EDGAR PM2.5 emission trajectory (2019 -> 2022)
    e19 = float(sub_all.loc[sub_all["year"] == 2019, "edgar_pm25_total"].mean())
    e22 = float(sub_all.loc[sub_all["year"] == 2022, "edgar_pm25_total"].mean())
    if np.isfinite(e19) and e19 > 0 and np.isfinite(e22):
        emi_delta = (e22 - e19) / e19
        s1 = float(np.clip(1.0 - (emi_delta / 0.05), 0.0, 1.0))
    else:
        emi_delta, s1 = 0.0, 0.5

    # S2: Renewable energy fraction
    s2 = float(RE_FRACTION.get(st, 0.35))

    # S3: Clean-air / sink standing (inverse of observed PM2.5 relative to 150 ug/m3)
    pm_curr = float(sub_curr["pm25"].mean()) if not sub_curr.empty else float(sub_all["pm25"].mean())
    pm_base = float(sub_base["pm25"].mean())
    s3 = float(np.clip(1.0 - (pm_curr / 150.0), 0.0, 1.0))

    # S4: Real CPCB observed PM2.5 trend (2019-2021 -> 2022-2023)
    pm_pct_change = (pm_curr - pm_base) / max(pm_base, 1.0)
    s4 = float(np.clip(0.5 - (pm_pct_change / 0.40), 0.0, 1.0))

    # S5: Real CPCB NAAQS daily compliance rate (fraction of days with PM2.5 <= 60 ug/m3)
    s5 = float((sub_curr["pm25"] <= 60.0).mean()) if not sub_curr.empty else float((sub_all["pm25"] <= 60.0).mean())

    s_bar = w1 * s1 + w2 * s2 + w3 * s3 + w4 * s4 + w5 * s5
    eff = float(np.clip(0.5 + 1.5 * s_bar, 0.5, 2.0))

    m3_rows.append({
        "state": st, "archetype": arch, "pm25_base": pm_base, "pm25_curr": pm_curr,
        "emi_delta_19_22": emi_delta, "pm_pct_change": pm_pct_change,
        "S1_emi_trend": s1, "S2_renewable": s2, "S3_clean_sink": s3,
        "S4_cpcb_trend": s4, "S5_naaqs_comp": s5, "effort_multiplier": eff,
    })

m3_df = pd.DataFrame(m3_rows)
m3_df.to_csv(OUT / "M3_effort_v3.csv", index=False)

# ------------------------------------------------------------------ 6. VT Scoring Engine (with Bootstrap 95% CIs)
print("[5/6] Computing Baseline-Normalized VT Scores (300-700) + 95% Bootstrap CIs...")
pm_base_vec = m3_df["pm25_base"].values
pm_curr_vec = m3_df["pm25_curr"].values
eff_vec = m3_df["effort_multiplier"].values

def compute_vt_vector(M_dom, ext_rec, M_base_mat, ext_base):
    # Off-diagonal domestic received + external received = total victim protection credit
    off_mask = ~np.eye(N_ST, dtype=bool)
    rec_dom = (M_dom * off_mask).sum(axis=0)
    rec_tot = rec_dom + ext_rec
    exp_dom = (M_dom * off_mask).sum(axis=1)

    rec_base = (M_base_mat * off_mask).sum(axis=0) + ext_base
    exp_base = (M_base_mat * off_mask).sum(axis=1)

    # Accountable PM2.5 burden = victim-protected local PM2.5 + exported harm to other states
    acct_curr = np.maximum(pm_curr_vec - rec_tot, 0.0) + exp_dom
    acct_base = np.maximum(pm_base_vec - rec_base, 0.0) + exp_base

    # Scale-normalized improvement over own 2019-2021 baseline (fixes v1 large-state saturation)
    rel_imp = (acct_base - acct_curr) / np.maximum(acct_base, 1.0)
    # Effort amplification: boosts gains, softens deficits
    adj_imp = np.where(rel_imp >= 0, rel_imp * eff_vec, rel_imp / eff_vec)

    med = np.median(adj_imp)
    iqr = np.percentile(adj_imp, 75) - np.percentile(adj_imp, 25)
    iqr = iqr if iqr > 1e-9 else 1.0
    z = (adj_imp - med) / (iqr / 2.0)
    vt = np.clip(500.0 + VT_SCALE * z, 300.0, 700.0)
    return vt, rec_dom, ext_rec, exp_dom, acct_curr, acct_base, rel_imp, adj_imp

vt_pt, rec_dom_pt, ext_rec_pt, exp_dom_pt, acct_curr_pt, acct_base_pt, rel_imp_pt, adj_imp_pt = compute_vt_vector(
    M_dom_pt, ext_rec_pt, M_dom_base, ext_rec_base
)

vt_boot = np.zeros((N_BOOT, N_ST), dtype=np.float64)
for k in range(N_BOOT):
    vt_boot[k], *_ = compute_vt_vector(M_dom_boot[k], ext_rec_boot[k], M_dom_base, ext_rec_base)

vt_df = m3_df[["state", "archetype", "pm25_base", "pm25_curr", "effort_multiplier"]].copy()
vt_df["received_dom_ugm3"] = rec_dom_pt
vt_df["received_ext_ugm3"] = ext_rec_pt
vt_df["exported_dom_ugm3"] = exp_dom_pt
vt_df["acct_burden_base"] = acct_base_pt
vt_df["acct_burden_curr"] = acct_curr_pt
vt_df["rel_improvement"] = rel_imp_pt
vt_df["adj_improvement"] = adj_imp_pt
vt_df["vt_score"] = vt_pt
vt_df["vt_ci_low"] = np.percentile(vt_boot, 2.5, axis=0)
vt_df["vt_ci_high"] = np.percentile(vt_boot, 97.5, axis=0)
vt_df = vt_df.sort_values("vt_score", ascending=False).reset_index(drop=True)
vt_df["rank"] = np.arange(1, len(vt_df) + 1)
vt_df.to_csv(OUT / "VT_scores_v3_final.csv", index=False)

# ------------------------------------------------------------------ 7. Bootstrap-Gated Fine Claims & Attribution Network
print("[6/6] Generating bootstrap-gated fine claims & state impact summary...")
off_mask = ~np.eye(N_ST, dtype=bool)
sig_mask = (C_mat > 0.75) & (boot_lo > 0.0) & off_mask
sig_harms = M_dom_pt[sig_mask]
harm_thresh = float(max(np.percentile(sig_harms, 75), 0.15)) if len(sig_harms) > 0 else 0.15

claim_rows = []
for i, src in enumerate(STATES):
    for j, dst in enumerate(STATES):
        if i == j:
            continue
        if C_mat[i, j] > 0.75 and boot_lo[i, j] > 0.0 and M_dom_pt[i, j] >= harm_thresh:
            fine_units = M_dom_pt[i, j] * C_mat[i, j]
            fine_pts = float(np.clip(round((fine_units / harm_thresh) * 25.0, 1), 20.0, 150.0))
            claim_rows.append({
                "defendant": src, "claimant": dst,
                "harm_ugm3": M_dom_pt[i, j], "harm_ci_low": boot_lo[i, j], "harm_ci_high": boot_hi[i, j],
                "confidence": C_mat[i, j], "fine_vt_units": fine_units, "fine_vt_points": fine_pts,
            })

claims_df = pd.DataFrame(claim_rows).sort_values("fine_vt_points", ascending=False)
claims_df.to_csv(OUT / "fine_claims_v3.csv", index=False)

# Attribution network (all directed pairs)
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
net_df = pd.DataFrame(net_rows).sort_values("net_harm_ugm3", ascending=False)
net_df.to_csv(OUT / "attribution_network_v3.csv", index=False)

# ------------------------------------------------------------------ Print Summary
print(f"\n=== VAAYU TOKEN (VT) SCORES v3 (2022-2023 vs 2019-2021 Baseline, scale={VT_SCALE}) ===")
print(vt_df[["rank", "state", "archetype", "pm25_curr", "received_dom_ugm3", "exported_dom_ugm3",
             "effort_multiplier", "vt_score", "vt_ci_low", "vt_ci_high"]].to_string(index=False))

print(f"\n=== BOOTSTRAP-GATED FINE CLAIMS (C > 0.75, CI_low > 0, harm >= {harm_thresh:.3f} ug/m3) ===")
print(f"Total eligible inter-state claims: {len(claims_df)}")
print(claims_df.head(15).to_string(index=False))

print(f"\nAll VT Economy v3 outputs saved to {OUT}/ in {time.time() - t0:.1f}s")
