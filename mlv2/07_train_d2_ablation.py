"""
07_train_d2_ablation.py -- CarbonVayu mlv2, Gate C2 (D2 node-exposure vs D vs C)

Compares (all trained on 2021, tested on 2022, 3 seeds):
  C   weather + calendar + local EDGAR
  D   C + crude 100/250 km upwind EDGAR
  D2  C + 72h 6-hourly node-exposure features (210 cols)
"""
import warnings
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
OUT = Path("results")
OUT.mkdir(exist_ok=True)
SEEDS = [0, 1, 2]
N_BOOT = 300

# 1. Load & merge base features + 72h node exposures
base = pd.read_parquet("data/features_daily_2021_2022.parquet")
exp = pd.read_parquet("data/node_exposure_daily_2021_2022.parquet")
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
UPWIND = [
    "edgar_pm25_agri_up100km", "edgar_pm25_agri_up250km",
    "edgar_pm25_up100km", "edgar_pm25_up250km",
    "edgar_bc_up100km", "edgar_bc_up250km",
]
NODE_EXP = [c for c in exp.columns if c.startswith("exp_")]

RUNS = {
    "C": WEATHER + CALENDAR + LOCAL,
    "D": WEATHER + CALENDAR + LOCAL + UPWIND,
    "D2": WEATHER + CALENDAR + LOCAL + NODE_EXP,
}

df = df.dropna(subset=WEATHER + CALENDAR + LOCAL + UPWIND + ["pm25"]).reset_index(drop=True)
tr = df[df.year == 2021].copy()
te = df[df.year == 2022].copy().reset_index(drop=True)
print(f"train: {len(tr):,} | test: {len(te):,} | node-exposure cols: {len(NODE_EXP)}")

def make_model(seed):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )

def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    mae = np.mean(np.abs(y - p))
    r2 = 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
    sp = spearmanr(y, p)[0]
    rl = np.sqrt(np.mean((np.log1p(y) - np.log1p(np.clip(p, 0, None))) ** 2))
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp, RMSE_log=rl)

SUBSETS = {
    "all": np.ones(len(te), bool),
    "north_box": te.in_north_india_box.astype(bool).values,
    "delhi_OctNov": ((te.state == "NCT of Delhi") & te.month.isin([10, 11])).values,
}

# 2. Train & predict
preds, models = {}, {}
ytr = np.log1p(tr.pm25.values)
for run, cols in RUNS.items():
    ps = []
    for s in SEEDS:
        m = make_model(s).fit(tr[cols], ytr)
        ps.append(np.clip(np.expm1(m.predict(te[cols])), 0, None))
        if s == SEEDS[0]:
            models[run] = m
    preds[run] = np.mean(ps, axis=0)
    print(f"trained {run} ({len(cols)} features, {len(SEEDS)} seeds)")

rows = []
for run, p in preds.items():
    for sub, mask in SUBSETS.items():
        rows.append(dict(run=run, subset=sub, **metrics(te.pm25.values[mask], p[mask])))
res = pd.DataFrame(rows)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
print("\n=== RESULTS (2022 test) ===")
print(res.to_string(index=False))

# 3. Paired station x ISO-week block bootstrap
blk = (te.location_id.astype(str) + "_" + te.date.dt.isocalendar().week.astype(str)).values

def boot_delta(run_hi, run_lo, mask, n_boot=N_BOOT, seed=42):
    y = te.pm25.values[mask]
    b = blk[mask]
    e_hi = (y - preds[run_hi][mask]) ** 2
    e_lo = (y - preds[run_lo][mask]) ** 2
    ub, inv = np.unique(b, return_inverse=True)
    n = np.bincount(inv)
    s_hi = np.bincount(inv, e_hi)
    s_lo = np.bincount(inv, e_lo)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(ub), len(ub))
        N = n[idx].sum()
        out.append(np.sqrt(s_lo[idx].sum() / N) - np.sqrt(s_hi[idx].sum() / N))
    pt = np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean())
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5)

print("\n=== PAIRED BOOTSTRAP: RMSE improvement (positive = first-named run is better) ===")
boot_rows = []
for hi, lo, label in [
    ("D2", "D", "D2 vs D  (GATE C2: 72h nodes vs crude upwind)"),
    ("D2", "C", "D2 vs C  (72h nodes vs local only)"),
]:
    for sub in ["all", "north_box", "delhi_OctNov"]:
        pt, lo_ci, hi_ci = boot_delta(hi, lo, SUBSETS[sub])
        verdict = "better" if lo_ci > 0 else ("worse" if hi_ci < 0 else "not distinguishable")
        boot_rows.append(dict(comparison=label, subset=sub, dRMSE=pt, ci_low=lo_ci, ci_high=hi_ci, verdict=verdict))
bt = pd.DataFrame(boot_rows)
print(bt.to_string(index=False))

# 4. Grouped permutation importance (D2, seed 0)
print("\n=== GROUPED PERMUTATION IMPORTANCE (run D2, test 2022) ===")
mD2 = models["D2"]
colsD2 = RUNS["D2"]
yt = te.pm25.values
rng = np.random.default_rng(7)
base_rmse = np.sqrt(np.mean((yt - np.clip(np.expm1(mD2.predict(te[colsD2])), 0, None)) ** 2))
imp = []
for g, gcols in {
    "weather": WEATHER,
    "local_emissions": LOCAL,
    "calendar": CALENDAR,
    "node_exposure_72h": NODE_EXP,
}.items():
    d = []
    for _ in range(3):
        Xp = te[colsD2].copy()
        perm = rng.permutation(len(Xp))
        Xp[gcols] = Xp[gcols].values[perm]
        d.append(np.sqrt(np.mean((yt - np.clip(np.expm1(mD2.predict(Xp)), 0, None)) ** 2)) - base_rmse)
    imp.append(dict(block=g, dRMSE=np.mean(d), sd=np.std(d)))
imp = pd.DataFrame(imp).sort_values("dRMSE", ascending=False)
print(imp.to_string(index=False))

# 5. Save
res.to_csv(OUT / "d2_metrics.csv", index=False)
bt.to_csv(OUT / "d2_bootstrap.csv", index=False)
pr = te[["location_id", "date", "state", "month", "pm25", "in_north_india_box"]].copy()
for r, p in preds.items():
    pr[f"pred_{r}"] = p
pr.to_parquet(OUT / "predictions_d2_2022.parquet", index=False)
print(f"\nSaved -> {OUT}/d2_metrics.csv, d2_bootstrap.csv, predictions_d2_2022.parquet")
