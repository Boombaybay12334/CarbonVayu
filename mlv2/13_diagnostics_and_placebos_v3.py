"""
13_diagnostics_and_placebos_v3.py -- CarbonVayu mlv3 (2019-2023)
Comprehensive validation & placebo suite:
  1. 3 Placebos: Trajectory shift (+1yr same DOY), Emission shuffle, Residence-time-only
  2. 3 Variants: Monotone decay (b0 >= b1 >= b2 >= 0), Weather-only Stage 1, Excl. own node
  3. Regional heterogeneity: Separate betas for north_box vs rest_of_india
  4. Calendar-week block bootstrap (all stations per week) refitting betas inside bootstrap
  5. Delhi Oct-Nov table reporting: ug/m3, % of observed PM2.5, and % of increment (with 95% CIs)
"""
import time
import warnings
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
t0_all = time.time()

OUT = Path("results/v3_5yr/diagnostics")
OUT.mkdir(parents=True, exist_ok=True)
CACHE_PATH = OUT / "stage1_loyo_cache.parquet"

YEARS = [2019, 2020, 2021, 2022, 2023]
N_BOOT = 300

pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# ------------------------------------------------------------------ 1. Load & align data
print("[1/6] Loading 5-year features & Trajectory v3 exposures...")
base = pd.read_parquet("data/features_daily_2019_2023.parquet")
exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()

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
COLS_FULL = WEATHER + CALENDAR + LOCAL
COLS_WONLY = WEATHER + CALENDAR

BINS = ["0_24h", "24_48h", "48_72h"]
SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES = [f"{s}_{b}" for s, b in SB]

df = base.dropna(subset=COLS_FULL + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)

df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month
df["day"] = df["date"].dt.day
df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)
y_all = df["pm25"].values.astype(np.float64)

SUBSETS = {
    "all": np.ones(len(df), bool),
    "north_box": df["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((df["state"] == "Delhi") & df["month"].isin([10, 11])).values,
}
print(f"  Aligned rows: {len(df):,} | Stations: {df['location_id'].nunique()} | Unique calendar weeks: {df['yw'].nunique()}")

# Map xKDR state names -> EDGAR node names for "exclude own node" variant
STATE_TO_NODE = {
    "Delhi": "ind_delhi", "Jammu & Kashmir": "ind_jk", "Jammu and Kashmir": "ind_jk",
}
for st_name in df["state"].dropna().unique():
    if st_name not in STATE_TO_NODE:
        cand = "ind_" + st_name.lower().replace(" ", "_").replace("&", "and")
        if cand in nodes:
            STATE_TO_NODE[st_name] = cand

# ------------------------------------------------------------------ 2. Stage-1 LOYO (Full C & Weather-Only C)
def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )


def run_stage1_loyo(feat_cols, tag):
    oof_by_holdout = {}
    pred_te_all = np.zeros(len(df), dtype=np.float64)
    for hold_yr in YEARS:
        t_y = time.time()
        tr_m = (df["year"] != hold_yr).values
        te_m = (df["year"] == hold_yr).values
        X_tr, y_tr = df.loc[tr_m, feat_cols], np.log1p(y_all[tr_m])
        X_te = df.loc[te_m, feat_cols]
        yw_tr = df.loc[tr_m, "yw"].values

        oof = np.zeros(tr_m.sum(), dtype=np.float64)
        for tr_i, va_i in GroupKFold(n_splits=5).split(X_tr, groups=yw_tr):
            m = make_lgb(0).fit(X_tr.iloc[tr_i], y_tr[tr_i])
            oof[va_i] = np.clip(np.expm1(m.predict(X_tr.iloc[va_i])), 0, None)

        pred_te = np.mean([
            np.clip(np.expm1(make_lgb(s).fit(X_tr, y_tr).predict(X_te)), 0, None)
            for s in [0, 1, 2]
        ], axis=0)
        oof_by_holdout[hold_yr] = oof
        pred_te_all[te_m] = pred_te
        print(f"  [Stage 1 {tag} | holdout {hold_yr}] {time.time() - t_y:.1f}s")
    return pred_te_all, oof_by_holdout


print("[2/6] Loading or computing Stage-1 LOYO predictions (Full C & Weather-only C)...")
if CACHE_PATH.exists():
    cache = pd.read_parquet(CACHE_PATH)
    pred_c_full = cache["pred_c_full"].values
    pred_c_wonly = cache["pred_c_wonly"].values
    oof_full = {yr: cache.loc[df["year"] != yr, f"oof_full_{yr}"].values for yr in YEARS}
    oof_wonly = {yr: cache.loc[df["year"] != yr, f"oof_wonly_{yr}"].values for yr in YEARS}
    print(f"  Loaded cached Stage-1 predictions from {CACHE_PATH}")
else:
    pred_c_full, oof_full = run_stage1_loyo(COLS_FULL, "Full_C")
    pred_c_wonly, oof_wonly = run_stage1_loyo(COLS_WONLY, "WeatherOnly_C")
    cache_dict = {"pred_c_full": pred_c_full, "pred_c_wonly": pred_c_wonly}
    for yr in YEARS:
        arr_f = np.full(len(df), np.nan)
        arr_w = np.full(len(df), np.nan)
        arr_f[df["year"] != yr] = oof_full[yr]
        arr_w[df["year"] != yr] = oof_wonly[yr]
        cache_dict[f"oof_full_{yr}"] = arr_f
        cache_dict[f"oof_wonly_{yr}"] = arr_w
    pd.DataFrame(cache_dict).to_parquet(CACHE_PATH, index=False)
    print(f"  Cached Stage-1 predictions -> {CACHE_PATH}")

# ------------------------------------------------------------------ 3. Build Exposure Matrices
print("[3/6] Building exposure matrices (Base, Excl-Own-Node, 3 Placebos)...")
# Base 9-column summed exposure
X_base = np.column_stack([
    exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).values for s, b in SB
]).astype(np.float64)

# Variant C: Exclude receptor's own state node
X_excl_self = X_base.copy()
own_nodes = df["state"].map(STATE_TO_NODE).values
for n in nodes:
    rmask = own_nodes == n
    if np.any(rmask):
        for j, (s, b) in enumerate(SB):
            X_excl_self[rmask, j] -= exp.loc[rmask, f"exp_{n}_{s}_{b}"].values

# Placebo 1: Trajectory Shift (+1 year cyclic on same station & month/day)
shift_df = pd.DataFrame(X_base, columns=NAMES)
shift_df["location_id"] = df["location_id"].values
shift_df["year"] = df["year"].values
shift_df["month"] = df["month"].values
shift_df["day"] = df["day"].values
shift_df["shift_year"] = shift_df["year"].map({2019: 2020, 2020: 2021, 2021: 2022, 2022: 2023, 2023: 2019})
merged_shift = df[["location_id", "year", "month", "day"]].merge(
    shift_df.drop(columns=["year"]).rename(columns={"shift_year": "year"}),
    on=["location_id", "year", "month", "day"], how="left",
)
# Fallback to station-month mean for Feb 29 or stations not active in shifted year
X_placebo_shift = merged_shift[NAMES].fillna(merged_shift[NAMES].mean()).values.astype(np.float64)

# Placebo 2: Emission Shuffle (permute node-level emission scales across the 35 nodes, 5 seeds)
rng_p = np.random.default_rng(123)
node_scales = np.zeros((len(nodes), len(SB)), dtype=np.float64)
for i_n, n in enumerate(nodes):
    for j, (s, b) in enumerate(SB):
        vals = exp[f"exp_{n}_{s}_{b}"].values
        nz = vals[vals > 0]
        node_scales[i_n, j] = float(nz.mean()) if len(nz) > 0 else 0.0

X_placebo_shuf_list = []
for seed_i in range(5):
    perm = rng_p.permutation(len(nodes))
    X_shuf = np.zeros_like(X_base)
    for i_n, n in enumerate(nodes):
        for j, (s, b) in enumerate(SB):
            if node_scales[i_n, j] > 0:
                ratio = node_scales[perm[i_n], j] / node_scales[i_n, j]
                X_shuf[:, j] += exp[f"exp_{n}_{s}_{b}"].values * ratio
    X_placebo_shuf_list.append(X_shuf)

# Placebo 3: Residence-Time-Only (unit emission per node: divide each node by its non-zero mean)
X_placebo_restime = np.zeros_like(X_base)
for i_n, n in enumerate(nodes):
    for j, (s, b) in enumerate(SB):
        if node_scales[i_n, j] > 0:
            X_placebo_restime[:, j] += exp[f"exp_{n}_{s}_{b}"].values / node_scales[i_n, j]

# ------------------------------------------------------------------ 4. Stage-2 Fitters & LOYO Runner
def fit_nnls(X_tr, y_resid, monotone=False):
    if not monotone:
        X_aug = np.column_stack([np.ones(len(X_tr)), X_tr])
        lb = np.array([-np.inf] + [0.0] * X_tr.shape[1])
        sol = lsq_linear(X_aug, y_resid, bounds=(lb, np.inf))
        return sol.x[0], sol.x[1:]
    # Exact monotone decay per sector: b0 >= b1 >= b2 >= 0
    # b2 = d2, b1 = d2 + d1, b0 = d2 + d1 + d0  =>  d0*x0 + d1*(x0+x1) + d2*(x0+x1+x2)
    X_cum = np.zeros_like(X_tr)
    for sec_i in range(3):
        c0, c1, c2 = 3 * sec_i, 3 * sec_i + 1, 3 * sec_i + 2
        X_cum[:, c0] = X_tr[:, c0]
        X_cum[:, c1] = X_tr[:, c0] + X_tr[:, c1]
        X_cum[:, c2] = X_tr[:, c0] + X_tr[:, c1] + X_tr[:, c2]
    X_aug = np.column_stack([np.ones(len(X_cum)), X_cum])
    lb = np.array([-np.inf] + [0.0] * X_cum.shape[1])
    sol = lsq_linear(X_aug, y_resid, bounds=(lb, np.inf))
    d = sol.x[1:]
    betas = np.zeros(9, dtype=np.float64)
    for sec_i in range(3):
        c0, c1, c2 = 3 * sec_i, 3 * sec_i + 1, 3 * sec_i + 2
        betas[c2] = d[c2]
        betas[c1] = d[c2] + d[c1]
        betas[c0] = d[c2] + d[c1] + d[c0]
    return sol.x[0], betas


def run_loyo_variant(X_mat, pred_c, oof_dict, monotone=False, split_region=False):
    pred_out = np.zeros(len(df), dtype=np.float64)
    betas_by_yr = {}
    for hold_yr in YEARS:
        tr_m = (df["year"] != hold_yr).values
        te_m = (df["year"] == hold_yr).values
        resid_tr = y_all[tr_m] - oof_dict[hold_yr]

        if not split_region:
            a, b = fit_nnls(X_mat[tr_m], resid_tr, monotone=monotone)
            pred_out[te_m] = np.clip(pred_c[te_m] + a + X_mat[te_m] @ b, 0, None)
            betas_by_yr[hold_yr] = b
        else:
            nb_tr = df.loc[tr_m, "in_north_india_box"].astype(bool).values
            nb_te = df.loc[te_m, "in_north_india_box"].astype(bool).values
            a_n, b_n = fit_nnls(X_mat[tr_m][nb_tr], resid_tr[nb_tr], monotone=monotone)
            a_r, b_r = fit_nnls(X_mat[tr_m][~nb_tr], resid_tr[~nb_tr], monotone=monotone)
            p_te = np.zeros(te_m.sum(), dtype=np.float64)
            p_te[nb_te] = np.clip(pred_c[te_m][nb_te] + a_n + X_mat[te_m][nb_te] @ b_n, 0, None)
            p_te[~nb_te] = np.clip(pred_c[te_m][~nb_te] + a_r + X_mat[te_m][~nb_te] @ b_r, 0, None)
            pred_out[te_m] = p_te
            betas_by_yr[hold_yr] = (b_n, b_r)
    return pred_out, betas_by_yr


def week_boot_drmse(y, p_hi, p_lo, yw_arr):
    """Calendar-week block bootstrap across ALL stations simultaneously."""
    e_hi, e_lo = (y - p_hi) ** 2, (y - p_lo) ** 2
    ub, inv = np.unique(yw_arr, return_inverse=True)
    n = np.bincount(inv)
    s_hi, s_lo = np.bincount(inv, e_hi), np.bincount(inv, e_lo)
    rng = np.random.default_rng(42)
    out = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(ub), len(ub))
        N = n[idx].sum()
        out.append(np.sqrt(s_lo[idx].sum() / N) - np.sqrt(s_hi[idx].sum() / N))
    pt = np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean())
    return pt, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


print("[4/6] Running all variants & placebos (5-fold LOYO)...")
variants = {}
p_base, b_base = run_loyo_variant(X_base, pred_c_full, oof_full, monotone=False)
variants["1_Baseline_v3 (Unconstrained)"] = (p_base, pred_c_full, b_base)

p_mono, b_mono = run_loyo_variant(X_base, pred_c_full, oof_full, monotone=True)
variants["2_Monotone_Decay (b0>=b1>=b2)"] = (p_mono, pred_c_full, b_mono)

p_noself, b_noself = run_loyo_variant(X_excl_self, pred_c_full, oof_full, monotone=False)
variants["3_Excl_Own_Node"] = (p_noself, pred_c_full, b_noself)

p_wonly, b_wonly = run_loyo_variant(X_base, pred_c_wonly, oof_wonly, monotone=False)
variants["4_WeatherOnly_Stage1 (Total)"] = (p_wonly, pred_c_wonly, b_wonly)

p_reg, b_reg = run_loyo_variant(X_base, pred_c_full, oof_full, monotone=False, split_region=True)
variants["5_Regional_Betas (North vs Rest)"] = (p_reg, pred_c_full, b_reg)

p_shft, _ = run_loyo_variant(X_placebo_shift, pred_c_full, oof_full, monotone=False)
variants["P1_Placebo_TrajShift (+1yr)"] = (p_shft, pred_c_full, None)

p_shuf_avg = np.mean([run_loyo_variant(Xs, pred_c_full, oof_full)[0] for Xs in X_placebo_shuf_list], axis=0)
variants["P2_Placebo_EmissionShuffle (5x)"] = (p_shuf_avg, pred_c_full, None)

p_rest, _ = run_loyo_variant(X_placebo_restime, pred_c_full, oof_full, monotone=False)
variants["P3_Placebo_ResidenceTimeOnly"] = (p_rest, pred_c_full, None)

# Evaluate all variants with CALENDAR-WEEK block bootstrap
summary_rows = []
yw_all = df["yw"].values
for vname, (p_mod, p_ref, _) in variants.items():
    for sub, msk in SUBSETS.items():
        y_s, pm_s, pr_s = y_all[msk], p_mod[msk], p_ref[msk]
        rmse_c = float(np.sqrt(np.mean((y_s - pr_s) ** 2)))
        rmse_m = float(np.sqrt(np.mean((y_s - pm_s) ** 2)))
        r2_m = float(1.0 - np.sum((y_s - pm_s) ** 2) / np.sum((y_s - y_s.mean()) ** 2))
        pt, lo, hi = week_boot_drmse(y_s, pm_s, pr_s, yw_all[msk])
        summary_rows.append({
            "variant": vname, "subset": sub, "RMSE_C": rmse_c, "RMSE_mod": rmse_m,
            "dRMSE": pt, "wk_ci_low": lo, "wk_ci_high": hi, "R2_mod": r2_m,
        })

sum_df = pd.DataFrame(summary_rows)
sum_df.to_csv(OUT / "variants_and_placebos_loyo.csv", index=False)

print("\n=== ALL VARIANTS & PLACEBOS (5-YR LOYO, CALENDAR-WEEK BLOCK BOOTSTRAP 95% CI) ===")
print(sum_df.to_string(index=False))

# Compare mean betas across key structural variants
beta_comp = pd.DataFrame({"param": NAMES})
beta_comp["Baseline_v3"] = np.mean([b_base[y] for y in YEARS], axis=0)
beta_comp["Monotone"] = np.mean([b_mono[y] for y in YEARS], axis=0)
beta_comp["Excl_Own_Node"] = np.mean([b_noself[y] for y in YEARS], axis=0)
beta_comp["WeatherOnly_S1"] = np.mean([b_wonly[y] for y in YEARS], axis=0)
beta_comp["Region_NorthBox"] = np.mean([b_reg[y][0] for y in YEARS], axis=0)
beta_comp["Region_RestIndia"] = np.mean([b_reg[y][1] for y in YEARS], axis=0)
beta_comp.to_csv(OUT / "beta_comparison_variants.csv", index=False)

print("\n=== MEAN SHARED-DECAY BETAS ACROSS VARIANTS ===")
print(beta_comp.to_string(index=False))

# ------------------------------------------------------------------ 5. Calendar-Week Bootstrap Refitting Betas for Delhi Shares
print(f"\n[5/6] Running {N_BOOT}x calendar-week block bootstrap (refitting betas inside bootstrap)...")
del_mask = SUBSETS["delhi_OctNov"]
del_obs_pm25 = float(y_all[del_mask].mean())

# Precompute Delhi Oct-Nov mean exposure per node x 9 params
del_exp_mat = np.array([
    [exp.loc[del_mask, f"exp_{n}_{s}_{b}"].mean() for s, b in SB] for n in nodes
], dtype=np.float64)  # (35, 9)

# Use pooled LOYO residuals (y - pred_c_full) grouped by calendar week
resid_pooled_full = y_all - pred_c_full
resid_pooled_wonly = y_all - pred_c_wonly
ub_yw, inv_yw = np.unique(yw_all, return_inverse=True)
yw_idx = [np.where(inv_yw == i)[0] for i in range(len(ub_yw))]


def delhi_boot_table(X_mat, resid_vec, monotone=False, tag="baseline"):
    _, b_pt = fit_nnls(X_mat, resid_vec, monotone=monotone)
    rng = np.random.default_rng(42)
    boot_b = np.zeros((N_BOOT, 9), dtype=np.float64)
    for k in range(N_BOOT):
        picked = rng.integers(0, len(ub_yw), len(ub_yw))
        idx = np.concatenate([yw_idx[i] for i in picked])
        _, boot_b[k] = fit_nnls(X_mat[idx], resid_vec[idx], monotone=monotone)

    # Node totals: (N_BOOT, 35)
    boot_ug = boot_b @ del_exp_mat.T
    boot_tot = np.maximum(boot_ug.sum(axis=1, keepdims=True), 1e-9)
    boot_pct_inc = 100.0 * boot_ug / boot_tot
    boot_pct_obs = 100.0 * boot_ug / del_obs_pm25

    pt_ug = del_exp_mat @ b_pt
    pt_tot = max(float(pt_ug.sum()), 1e-9)
    rows = []
    for i_n, n in enumerate(nodes):
        rows.append({
            "source_node": n,
            "ugm3": pt_ug[i_n],
            "ugm3_lo": np.percentile(boot_ug[:, i_n], 2.5),
            "ugm3_hi": np.percentile(boot_ug[:, i_n], 97.5),
            "pct_of_obs_pm25": 100.0 * pt_ug[i_n] / del_obs_pm25,
            "obs_lo": np.percentile(boot_pct_obs[:, i_n], 2.5),
            "obs_hi": np.percentile(boot_pct_obs[:, i_n], 97.5),
            "pct_of_increment": 100.0 * pt_ug[i_n] / pt_tot,
            "inc_lo": np.percentile(boot_pct_inc[:, i_n], 2.5),
            "inc_hi": np.percentile(boot_pct_inc[:, i_n], 97.5),
        })
    res_df = pd.DataFrame(rows).sort_values("ugm3", ascending=False)
    res_df.to_csv(OUT / f"delhi_octnov_weekboot_{tag}.csv", index=False)
    return res_df, pt_tot


del_base, tot_base = delhi_boot_table(X_base, resid_pooled_full, monotone=False, tag="baseline_v3")
del_mono, tot_mono = delhi_boot_table(X_base, resid_pooled_full, monotone=True, tag="monotone_v3")
del_wonly, tot_wonly = delhi_boot_table(X_base, resid_pooled_wonly, monotone=False, tag="weather_only_s1")

print(f"\n[6/6] DELHI OCT-NOV (2019-2023) | Observed Mean PM2.5 = {del_obs_pm25:.1f} µg/m³")
print(f"\n--- A. Baseline v3 (Incremental over Local C; Total Attributable = {tot_base:.1f} µg/m³, {100*tot_base/del_obs_pm25:.1f}% of obs) ---")
print(del_base.head(8).to_string(index=False))

print(f"\n--- B. Monotone Decay v3 (Total Attributable = {tot_mono:.1f} µg/m³, {100*tot_mono/del_obs_pm25:.1f}% of obs) ---")
print(del_mono.head(8).to_string(index=False))

print(f"\n--- C. Weather-Only Stage 1 (Total Transport; Total Attributable = {tot_wonly:.1f} µg/m³, {100*tot_wonly/del_obs_pm25:.1f}% of obs) ---")
print(del_wonly.head(8).to_string(index=False))

print(f"\nAll diagnostics finished in {time.time() - t0_all:.1f}s! Saved to {OUT}/")
