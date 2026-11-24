"""
10_structured_matrix.py -- CarbonVayu mlv2
Fits a structured, shared-decay non-negative attribution model on
cross-fitted weather/local-adjusted residuals (Train 2021 -> Test 2022),
with station x ISO-week block-bootstrap 95% CIs.
"""
import warnings
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
OUT = Path("results")
OUT.mkdir(exist_ok=True)
N_BOOT = 300

pd.set_option("display.width", 180)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# 1. Load & merge cleaned features + 72h node exposures
base = pd.read_parquet("data/features_daily_2021_2022.parquet")
exp = pd.read_parquet("data/node_exposure_daily_2021_2022.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()

base["date"] = pd.to_datetime(base["date"])
exp["date"] = pd.to_datetime(exp["date"])
df = base.merge(exp, on=["location_id", "date"], how="inner")
df["month"] = df["date"].dt.month
df["year"] = df["date"].dt.year

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
COLS_C = WEATHER + CALENDAR + LOCAL
SECTORS = ["agri", "other"]
BINS = ["0_24h", "24_48h", "48_72h"]
SB_KEYS = [(s, b) for s in SECTORS for b in BINS]
SB_NAMES = [f"{s}_{b}" for s, b in SB_KEYS]

df = df.dropna(subset=COLS_C + ["pm25"]).reset_index(drop=True)

# Precompute total exposure across all 35 nodes for each (sector, bin)
for s, b in SB_KEYS:
    cols = [f"exp_{n}_{s}_{b}" for n in nodes]
    df[f"tot_{s}_{b}"] = df[cols].sum(axis=1).astype(np.float32)

TOT_COLS = [f"tot_{s}_{b}" for s, b in SB_KEYS]

tr = df[df["year"] == 2021].copy().reset_index(drop=True)
te = df[df["year"] == 2022].copy().reset_index(drop=True)
print(f"Train 2021: {len(tr):,} | Test 2022: {len(te):,}")

# 2. Cross-fit nuisance model C (Weather + Calendar + Local EDGAR) on 2021
def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )

print("Cross-fitting nuisance model C (5-fold GroupKFold by ISO-week on 2021)...")
groups_21 = tr["date"].dt.isocalendar().week.astype(int).values
gkf = GroupKFold(n_splits=5)
oof_c = np.zeros(len(tr), dtype=np.float64)
for tr_i, va_i in gkf.split(tr, groups=groups_21):
    m = make_lgb(0).fit(tr.loc[tr_i, COLS_C], np.log1p(tr.loc[tr_i, "pm25"].values))
    oof_c[va_i] = np.clip(np.expm1(m.predict(tr.loc[va_i, COLS_C])), 0, None)

# Full 2021 nuisance model (3-seed average) for 2022 test predictions
pred_c_te = np.mean([
    np.clip(np.expm1(make_lgb(s).fit(tr[COLS_C], np.log1p(tr["pm25"].values)).predict(te[COLS_C])), 0, None)
    for s in [0, 1, 2]
], axis=0)

resid_tr = tr["pm25"].values - oof_c

# 3. Fit shared-decay non-negative model: resid ~ intercept + sum(beta_{s,b} * tot_{s,b}), beta >= 0
def fit_shared_decay(X_tot, y_resid):
    X_aug = np.column_stack([np.ones(len(X_tot)), X_tot])
    lb = np.array([-np.inf] + [0.0] * X_tot.shape[1])
    ub = np.full(X_tot.shape[1] + 1, np.inf)
    sol = lsq_linear(X_aug, y_resid, bounds=(lb, ub))
    return sol.x[0], sol.x[1:]  # intercept, betas (len 6)

X_tr_tot = tr[TOT_COLS].values.astype(np.float64)
X_te_tot = te[TOT_COLS].values.astype(np.float64)

alpha, betas = fit_shared_decay(X_tr_tot, resid_tr)

# Block-bootstrap 95% CIs on 2021 training blocks (station x ISO-week)
print(f"Running {N_BOOT}x station x ISO-week block bootstrap for parameter CIs...")
blk_tr = (tr["location_id"].astype(str) + "_" + tr["date"].dt.isocalendar().week.astype(str)).values
ub, inv = np.unique(blk_tr, return_inverse=True)
block_indices = [np.where(inv == i)[0] for i in range(len(ub))]

rng = np.random.default_rng(42)
boot_betas = np.zeros((N_BOOT, len(SB_NAMES)), dtype=np.float64)
for b in range(N_BOOT):
    picked = rng.integers(0, len(ub), len(ub))
    idx = np.concatenate([block_indices[i] for i in picked])
    _, boot_betas[b] = fit_shared_decay(X_tr_tot[idx], resid_tr[idx])

param_df = pd.DataFrame({
    "param": SB_NAMES,
    "beta_ugm3_per_unit": betas,
    "ci_low": np.percentile(boot_betas, 2.5, axis=0),
    "ci_high": np.percentile(boot_betas, 97.5, axis=0),
})
param_df.to_csv(OUT / "structured_decay_params.csv", index=False)

print(f"\n=== SHARED-DECAY PARAMETERS (intercept = {alpha:+.2f} µg/m³) ===")
print(param_df.to_string(index=False))

# 4. Evaluate C vs Structured (6 params) vs D2 on 2022 test
pred_struct_te = np.clip(pred_c_te + alpha + X_te_tot @ betas, 0, None)
d2_saved = pd.read_parquet(OUT / "predictions_d2_2022.parquet")

def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    mae = np.mean(np.abs(y - p))
    r2 = 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
    sp = spearmanr(y, p)[0]
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp)

SUBSETS = {
    "all": np.ones(len(te), bool),
    "north_box": te["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((te["state"] == "NCT of Delhi") & te["month"].isin([10, 11])).values,
}

eval_rows = []
for name, p in [("C (local only)", pred_c_te),
                ("Structured (C + 6 shared params)", pred_struct_te),
                ("D2 (240-feat GBM)", d2_saved["pred_D2"].values)]:
    for sub, msk in SUBSETS.items():
        eval_rows.append(dict(model=name, subset=sub, **metrics(te.loc[msk, "pm25"], p[msk])))

print("\n=== 2022 TEST PERFORMANCE: C vs STRUCTURED vs D2 ===")
print(pd.DataFrame(eval_rows).to_string(index=False))

# 5. Compute exact additive State-to-State Source Attribution Matrix on 2022 test
contrib_total = {}
contrib_agri = {}
contrib_other = {}
for n in nodes:
    ag = np.zeros(len(te), dtype=np.float64)
    ot = np.zeros(len(te), dtype=np.float64)
    for b_idx, b in enumerate(BINS):
        ag += betas[b_idx] * te[f"exp_{n}_agri_{b}"].values
        ot += betas[3 + b_idx] * te[f"exp_{n}_other_{b}"].values
    contrib_agri[n] = ag
    contrib_other[n] = ot
    contrib_total[n] = ag + ot

c_df = pd.DataFrame(contrib_total)
c_df["receptor_state"] = te["state"].values
c_df["month"] = te["month"].values

def save_matrix(sub_df, tag):
    mat_ug = sub_df.groupby("receptor_state")[nodes].mean()
    mat_pct = mat_ug.div(mat_ug.sum(axis=1).replace(0, np.nan), axis=0) * 100.0
    mat_ug.to_csv(OUT / f"structured_matrix_{tag}_ugm3.csv")
    mat_pct.to_csv(OUT / f"structured_matrix_{tag}_pct.csv")
    return mat_ug, mat_pct

ann_ug, ann_pct = save_matrix(c_df, "annual_2022")
oct_ug, oct_pct = save_matrix(c_df[c_df["month"].isin([10, 11])], "octnov_2022")

# 6. Delhi Oct-Nov sector breakdown with bootstrap 95% CIs
del_mask = SUBSETS["delhi_OctNov"]
del_rows = []
# Precompute Delhi mean exposures per node x (sector, bin) for fast bootstrap CIs
del_exp = {
    n: np.array([te.loc[del_mask, f"exp_{n}_{s}_{b}"].mean() for s, b in SB_KEYS])
    for n in nodes
}
del_boot_tot = np.column_stack([boot_betas @ del_exp[n] for n in nodes])  # (N_BOOT, n_nodes)
del_boot_pct = 100.0 * del_boot_tot / np.maximum(del_boot_tot.sum(axis=1, keepdims=True), 1e-9)

for idx_n, n in enumerate(nodes):
    ag_val = contrib_agri[n][del_mask].mean()
    ot_val = contrib_other[n][del_mask].mean()
    tot_val = ag_val + ot_val
    del_rows.append({
        "source_node": n,
        "agri_ugm3": ag_val,
        "other_ugm3": ot_val,
        "total_ugm3": tot_val,
        "share_pct": 100.0 * tot_val / max(sum(contrib_total[k][del_mask].mean() for k in nodes), 1e-9),
        "pct_ci_low": np.percentile(del_boot_pct[:, idx_n], 2.5),
        "pct_ci_high": np.percentile(del_boot_pct[:, idx_n], 97.5),
    })

del_df = pd.DataFrame(del_rows).sort_values("total_ugm3", ascending=False)
del_df.to_csv(OUT / "structured_delhi_octnov_2022_sector_split.csv", index=False)

print("\n=== STRUCTURED MATRIX: NCT OF DELHI (Oct-Nov 2022) — TOP 10 SOURCES ===")
print(del_df.head(10).to_string(index=False))

print("\n=== STRUCTURED MATRIX: KEY NORTH INDIA RECEPTORS (Oct-Nov 2022, Top 5 % Share) ===")
for rec in ["NCT of Delhi", "Haryana", "Uttar Pradesh", "Punjab", "Bihar"]:
    if rec in oct_pct.index:
        top5 = oct_pct.loc[rec].sort_values(ascending=False).head(5)
        top_str = " | ".join([f"{k}: {v:.1f}%" for k, v in top5.items()])
        print(f"  {rec:<15} -> {top_str}")

print(f"\nSaved structured matrices & CIs to {OUT}/")
