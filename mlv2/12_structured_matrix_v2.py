"""
12_structured_matrix_v2.py -- CarbonVayu mlv2
Fits the 9-parameter shared-decay non-negative model (agri, other, sia x 3 bins)
on Trajectory v2 (1h substeps, 10m/925hPa blend, wet scavenging), compares directly
against Structured v1 (6 params) with paired block-bootstrap CIs, and saves the v2 matrix.
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

# 1. Load base + v1 + v2 exposures
base = pd.read_parquet("data/features_daily_2021_2022.parquet")
exp1 = pd.read_parquet("data/node_exposure_daily_2021_2022.parquet")
exp2 = pd.read_parquet("data/node_exposure_v2_daily_2021_2022.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()

for d in (base, exp1, exp2):
    d["date"] = pd.to_datetime(d["date"])

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
BINS = ["0_24h", "24_48h", "48_72h"]
SB_V1 = [(s, b) for s in ["agri", "other"] for b in BINS]
SB_V2 = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]

df = base.dropna(subset=COLS_C + ["pm25"]).copy()
df["month"] = df["date"].dt.month
df["year"] = df["date"].dt.year

# Precompute v1 & v2 sector-bin totals
v1_tots = pd.DataFrame({"location_id": exp1["location_id"], "date": exp1["date"]})
for s, b in SB_V1:
    v1_tots[f"v1_tot_{s}_{b}"] = exp1[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).astype(np.float32)

v2_tots = pd.DataFrame({"location_id": exp2["location_id"], "date": exp2["date"]})
for s, b in SB_V2:
    v2_tots[f"v2_tot_{s}_{b}"] = exp2[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).astype(np.float32)

df = df.merge(v1_tots, on=["location_id", "date"], how="inner")
df = df.merge(v2_tots, on=["location_id", "date"], how="inner")
df = df.merge(exp2, on=["location_id", "date"], how="inner").reset_index(drop=True)

tr = df[df["year"] == 2021].copy().reset_index(drop=True)
te = df[df["year"] == 2022].copy().reset_index(drop=True)
print(f"Train 2021: {len(tr):,} | Test 2022: {len(te):,}")

# 2. Cross-fit nuisance model C on 2021
def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )

print("Cross-fitting nuisance model C (5-fold GroupKFold by ISO-week on 2021)...")
groups_21 = tr["date"].dt.isocalendar().week.astype(int).values
oof_c = np.zeros(len(tr), dtype=np.float64)
for tr_i, va_i in GroupKFold(n_splits=5).split(tr, groups=groups_21):
    m = make_lgb(0).fit(tr.loc[tr_i, COLS_C], np.log1p(tr.loc[tr_i, "pm25"].values))
    oof_c[va_i] = np.clip(np.expm1(m.predict(tr.loc[va_i, COLS_C])), 0, None)

pred_c_te = np.mean([
    np.clip(np.expm1(make_lgb(s).fit(tr[COLS_C], np.log1p(tr["pm25"].values)).predict(te[COLS_C])), 0, None)
    for s in [0, 1, 2]
], axis=0)
resid_tr = tr["pm25"].values - oof_c

# 3. Fit Structured v1 (6 params) and Structured v2 (9 params)
def fit_shared_decay(X_tot, y_resid):
    X_aug = np.column_stack([np.ones(len(X_tot)), X_tot])
    lb = np.array([-np.inf] + [0.0] * X_tot.shape[1])
    ub = np.full(X_tot.shape[1] + 1, np.inf)
    sol = lsq_linear(X_aug, y_resid, bounds=(lb, ub))
    return sol.x[0], sol.x[1:]

cols_v1 = [f"v1_tot_{s}_{b}" for s, b in SB_V1]
cols_v2 = [f"v2_tot_{s}_{b}" for s, b in SB_V2]
names_v2 = [f"{s}_{b}" for s, b in SB_V2]

a1, b1 = fit_shared_decay(tr[cols_v1].values.astype(np.float64), resid_tr)
a2, b2 = fit_shared_decay(tr[cols_v2].values.astype(np.float64), resid_tr)

pred_v1 = np.clip(pred_c_te + a1 + te[cols_v1].values @ b1, 0, None)
pred_v2 = np.clip(pred_c_te + a2 + te[cols_v2].values @ b2, 0, None)

# Bootstrap CIs for v2 parameters
print(f"Running {N_BOOT}x station x ISO-week block bootstrap for v2 parameter CIs...")
blk_tr = (tr["location_id"].astype(str) + "_" + tr["date"].dt.isocalendar().week.astype(str)).values
ub, inv = np.unique(blk_tr, return_inverse=True)
blk_idx = [np.where(inv == i)[0] for i in range(len(ub))]

rng = np.random.default_rng(42)
X_tr_v2 = tr[cols_v2].values.astype(np.float64)
boot_b2 = np.zeros((N_BOOT, len(names_v2)), dtype=np.float64)
for i in range(N_BOOT):
    picked = rng.integers(0, len(ub), len(ub))
    idx = np.concatenate([blk_idx[k] for k in picked])
    _, boot_b2[i] = fit_shared_decay(X_tr_v2[idx], resid_tr[idx])

param_df = pd.DataFrame({
    "param": names_v2,
    "beta_ugm3_per_unit": b2,
    "ci_low": np.percentile(boot_b2, 2.5, axis=0),
    "ci_high": np.percentile(boot_b2, 97.5, axis=0),
})
param_df.to_csv(OUT / "structured_v2_decay_params.csv", index=False)
print(f"\n=== STRUCTURED V2 PARAMETERS (intercept = {a2:+.2f} µg/m³) ===")
print(param_df.to_string(index=False))

# 4. Evaluate C vs Structured v1 vs Structured v2 + paired bootstrap
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
                ("Structured v1 (6 params, 3h 925hPa)", pred_v1),
                ("Structured v2 (9 params, 1h blend+wet+SIA)", pred_v2)]:
    for sub, msk in SUBSETS.items():
        eval_rows.append(dict(model=name, subset=sub, **metrics(te.loc[msk, "pm25"], p[msk])))

print("\n=== 2022 TEST PERFORMANCE: C vs STRUCTURED V1 vs STRUCTURED V2 ===")
print(pd.DataFrame(eval_rows).to_string(index=False))

blk_te = (te["location_id"].astype(str) + "_" + te["date"].dt.isocalendar().week.astype(str)).values
def boot_delta(p_hi, p_lo, mask):
    y = te["pm25"].values[mask]
    b = blk_te[mask]
    e_hi, e_lo = (y - p_hi[mask]) ** 2, (y - p_lo[mask]) ** 2
    ub_t, inv_t = np.unique(b, return_inverse=True)
    n = np.bincount(inv_t)
    s_hi, s_lo = np.bincount(inv_t, e_hi), np.bincount(inv_t, e_lo)
    rng_t = np.random.default_rng(42)
    out = []
    for _ in range(N_BOOT):
        idx = rng_t.integers(0, len(ub_t), len(ub_t))
        N = n[idx].sum()
        out.append(np.sqrt(s_lo[idx].sum() / N) - np.sqrt(s_hi[idx].sum() / N))
    pt = np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean())
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5)

print("\n=== PAIRED BOOTSTRAP: Structured v2 vs Structured v1 (positive = v2 better) ===")
bt_rows = []
for sub, msk in SUBSETS.items():
    pt, lo, hi = boot_delta(pred_v2, pred_v1, msk)
    verdict = "better" if lo > 0 else ("worse" if hi < 0 else "not distinguishable")
    bt_rows.append(dict(subset=sub, dRMSE=pt, ci_low=lo, ci_high=hi, verdict=verdict))
print(pd.DataFrame(bt_rows).to_string(index=False))

# 5. Extract & save v2 additive State-to-State Source Attribution Matrix
c_agri, c_other, c_sia, c_tot = {}, {}, {}, {}
for n in nodes:
    ag = sum(b2[i] * te[f"exp_{n}_agri_{b}"].values for i, b in enumerate(BINS))
    ot = sum(b2[3 + i] * te[f"exp_{n}_other_{b}"].values for i, b in enumerate(BINS))
    si = sum(b2[6 + i] * te[f"exp_{n}_sia_{b}"].values for i, b in enumerate(BINS))
    c_agri[n], c_other[n], c_sia[n], c_tot[n] = ag, ot, si, ag + ot + si

c_df = pd.DataFrame(c_tot)
c_df["receptor_state"] = te["state"].values
c_df["month"] = te["month"].values

for tag, sub_df in [("annual_2022", c_df), ("octnov_2022", c_df[c_df["month"].isin([10, 11])])]:
    mat_ug = sub_df.groupby("receptor_state")[nodes].mean()
    mat_pct = mat_ug.div(mat_ug.sum(axis=1).replace(0, np.nan), axis=0) * 100.0
    mat_ug.to_csv(OUT / f"structured_v2_matrix_{tag}_ugm3.csv")
    mat_pct.to_csv(OUT / f"structured_v2_matrix_{tag}_pct.csv")
    if tag == "octnov_2022":
        oct_pct = mat_pct

# Delhi Oct-Nov breakdown with bootstrap CIs
del_mask = SUBSETS["delhi_OctNov"]
del_exp = {n: np.array([te.loc[del_mask, f"exp_{n}_{s}_{b}"].mean() for s, b in SB_V2]) for n in nodes}
del_boot_tot = np.column_stack([boot_b2 @ del_exp[n] for n in nodes])
del_boot_pct = 100.0 * del_boot_tot / np.maximum(del_boot_tot.sum(axis=1, keepdims=True), 1e-9)

del_rows = []
tot_del_sum = max(sum(c_tot[k][del_mask].mean() for k in nodes), 1e-9)
for idx_n, n in enumerate(nodes):
    ag_v, ot_v, si_v = c_agri[n][del_mask].mean(), c_other[n][del_mask].mean(), c_sia[n][del_mask].mean()
    tv = ag_v + ot_v + si_v
    del_rows.append({
        "source_node": n,
        "agri_ugm3": ag_v, "other_ugm3": ot_v, "sia_ugm3": si_v, "total_ugm3": tv,
        "share_pct": 100.0 * tv / tot_del_sum,
        "pct_ci_low": np.percentile(del_boot_pct[:, idx_n], 2.5),
        "pct_ci_high": np.percentile(del_boot_pct[:, idx_n], 97.5),
    })

del_df = pd.DataFrame(del_rows).sort_values("total_ugm3", ascending=False)
del_df.to_csv(OUT / "structured_v2_delhi_octnov_2022_sector_split.csv", index=False)

print("\n=== STRUCTURED V2: NCT OF DELHI (Oct-Nov 2022) — TOP 10 SOURCES ===")
print(del_df.head(10).to_string(index=False))

print("\n=== STRUCTURED V2: KEY NORTH INDIA RECEPTORS (Oct-Nov 2022, Top 5 % Share) ===")
for rec in ["NCT of Delhi", "Haryana", "Uttar Pradesh", "Punjab", "Bihar"]:
    if rec in oct_pct.index:
        top5 = oct_pct.loc[rec].sort_values(ascending=False).head(5)
        print(f"  {rec:<15} -> " + " | ".join([f"{k}: {v:.1f}%" for k, v in top5.items()]))

print(f"\nSaved v2 structured matrices & CIs to {OUT}/")
