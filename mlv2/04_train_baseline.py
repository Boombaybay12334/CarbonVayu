"""
04_train_baseline.py  --  CarbonVayu mlv2, Gate C ablation ladder (exogenous mode)

Runs (all trained on 2021, tested on 2022):
  A  station-month climatology (no ML)           <- baseline to beat
  B  weather + calendar
  C  B + local EDGAR emissions
  D  C + upwind EDGAR features                   <- D vs C is the Gate C number
  E  D + PM2.5 lags                              <- forecasting ceiling (side run)
  F  D + identity cols (lat, lon, forest carbon) <- shows how much is memorisation
"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
DATA = Path("data/features_daily_2021_2022.parquet")
OUT = Path("results"); OUT.mkdir(exist_ok=True)
SEEDS = [0, 1, 2]
N_BOOT = 300

# ---------------------------------------------------------------- model backend
try:
    import lightgbm as lgb
    BACKEND = "lightgbm"
    def make_model(seed):
        return lgb.LGBMRegressor(n_estimators=800, learning_rate=0.03, num_leaves=31,
                                 min_child_samples=50, subsample=0.8, subsample_freq=1,
                                 colsample_bytree=0.8, reg_lambda=1.0,
                                 random_state=seed, n_jobs=-1, verbose=-1)
except Exception:
    from sklearn.ensemble import HistGradientBoostingRegressor
    BACKEND = "sklearn-HistGB (deterministic: seeds give identical results)"
    def make_model(seed):
        return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_leaf_nodes=31,
                                             min_samples_leaf=50, l2_regularization=1.0,
                                             early_stopping=False, random_state=seed)

# ---------------------------------------------------------------- feature blocks
WEATHER = ["blh_mean","blh_min","t2m_c","rh_pct","u10","v10","wspd10","precip_mm",
           "u925","v925","wspd925","u850","v850","wspd850"]
CALENDAR = ["doy_sin","doy_cos","day_of_week","is_weekend"]
LOCAL = ["edgar_pm25_agriculture","edgar_pm25_buildings","edgar_pm25_ind_combustion",
         "edgar_pm25_power_industry","edgar_pm25_transport","edgar_pm25_waste","edgar_pm25_total",
         "edgar_bc_total","edgar_co_total","edgar_nh3_total","edgar_nox_total","edgar_so2_total"]
UPWIND = ["edgar_pm25_agri_up100km","edgar_pm25_agri_up250km","edgar_pm25_up100km",
          "edgar_pm25_up250km","edgar_bc_up100km","edgar_bc_up250km"]
LAGS = ["pm25_lag1","pm25_lag2"]
IDENT = ["lat","lon","forest_cover_area_sq_km","agb_kt","bgb_kt","dead_wood_kt",
         "litter_kt","soc_kt","total_carbon_kt"]
RUNS = {"B": WEATHER+CALENDAR,
        "C": WEATHER+CALENDAR+LOCAL,
        "D": WEATHER+CALENDAR+LOCAL+UPWIND,
        "E": WEATHER+CALENDAR+LOCAL+UPWIND+LAGS,
        "F": WEATHER+CALENDAR+LOCAL+UPWIND+IDENT}

# ---------------------------------------------------------------- data
df = pd.read_parquet(DATA)
df["date"] = pd.to_datetime(df["date"]); df["month"] = df["date"].dt.month
df["year"] = df["date"].dt.year
need = sorted(set(sum(RUNS.values(), [])) - set(LAGS))
df = df.dropna(subset=need + ["pm25"]).reset_index(drop=True)
tr = df[df.year == 2021].copy(); te = df[df.year == 2022].copy().reset_index(drop=True)
print(f"backend: {BACKEND}\ntrain rows {len(tr):,} | test rows {len(te):,} | "
      f"test stations {te.location_id.nunique()} (of which unseen in train: "
      f"{len(set(te.location_id) - set(tr.location_id))})")

# ---------------------------------------------------------------- baseline A
c_sm = tr.groupby(["location_id","month"]).pm25.mean().rename("c_sm")
c_s = tr.groupby("location_id").pm25.mean().rename("c_s")
c_stm = tr.groupby(["state","month"]).pm25.mean().rename("c_stm")
te = te.join(c_sm, on=["location_id","month"]).join(c_s, on="location_id").join(c_stm, on=["state","month"])
te["base"] = te.c_sm.fillna(te.c_s).fillna(te.c_stm).fillna(tr.pm25.mean())
lvl = np.where(te.c_sm.notna(), "station-month", np.where(te.c_s.notna(), "station",
        np.where(te.c_stm.notna(), "state-month", "global")))
print("baseline A fallback levels:", pd.Series(lvl).value_counts(normalize=True).round(3).to_dict())

# ---------------------------------------------------------------- metrics
def metrics(y, p, base):
    y, p, base = map(np.asarray, (y, p, base))
    rmse = np.sqrt(np.mean((y-p)**2)); mae = np.mean(np.abs(y-p))
    r2 = 1 - np.sum((y-p)**2) / np.sum((y-y.mean())**2)
    ay, ap = y-base, p-base
    ar2 = 1 - np.sum((ay-ap)**2) / np.sum((ay-ay.mean())**2)
    sp = spearmanr(y, p)[0]; asp = spearmanr(ay, ap)[0] if np.std(ap) > 0 else np.nan
    rl = np.sqrt(np.mean((np.log1p(y)-np.log1p(np.clip(p,0,None)))**2))
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp, anomR2=ar2, anomSpearman=asp, RMSE_log=rl)

SUBSETS = {"all": np.ones(len(te), bool),
           "north_box": te.in_north_india_box.astype(bool).values,
           "delhi_OctNov": ((te.state == "NCT of Delhi") & te.month.isin([10,11])).values}

# ---------------------------------------------------------------- train & predict
preds = {"A": te.base.values.copy()}
models = {}
ytr = np.log1p(tr.pm25.values)
for run, cols in RUNS.items():
    ps = []
    for s in SEEDS:
        m = make_model(s).fit(tr[cols], ytr)
        ps.append(np.clip(np.expm1(m.predict(te[cols])), 0, None))
        if s == SEEDS[0]: models[run] = m
    preds[run] = np.mean(ps, axis=0)
    print(f"trained {run} ({len(cols)} features, {len(SEEDS)} seeds)")

rows = []
for run, p in preds.items():
    for sub, mask in SUBSETS.items():
        if mask.sum() > 10:
            rows.append(dict(run=run, subset=sub, **metrics(te.pm25.values[mask], p[mask], te.base.values[mask])))
res = pd.DataFrame(rows)
pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
print("\n=== RESULTS (2022 test) ==="); print(res.to_string(index=False))

# ---------------------------------------------------------------- paired block bootstrap (station x ISO-week blocks)
blk = (te.location_id.astype(str) + "_" + te.date.dt.isocalendar().week.astype(str)).values
def boot_delta(run_hi, run_lo, mask, n_boot=N_BOOT, seed=42):
    """RMSE(run_lo) - RMSE(run_hi); positive => run_hi is better."""
    y = te.pm25.values[mask]; b = blk[mask]
    e_hi = (y - preds[run_hi][mask])**2; e_lo = (y - preds[run_lo][mask])**2
    ub, inv = np.unique(b, return_inverse=True)
    n = np.bincount(inv); s_hi = np.bincount(inv, e_hi); s_lo = np.bincount(inv, e_lo)
    rng = np.random.default_rng(seed); out = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(ub), len(ub))
        N = n[idx].sum(); out.append(np.sqrt(s_lo[idx].sum()/N) - np.sqrt(s_hi[idx].sum()/N))
    pt = np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean())
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5)

print("\n=== PAIRED BOOTSTRAP: RMSE improvement (positive = first-named run is better) ===")
boot_rows = []
for hi, lo, label in [("D","C","D vs C  (GATE C: does upwind help?)"), ("C","B","C vs B  (local emissions)"),
                      ("B","A","B vs A  (ML-without-identity vs climatology)"), ("D","A","D vs A")]:
    for sub in ["all", "north_box", "delhi_OctNov"]:
        mask = SUBSETS[sub]
        if mask.sum() > 30:
            pt, lo_ci, hi_ci = boot_delta(hi, lo, mask)
            boot_rows.append(dict(comparison=label, subset=sub, dRMSE=pt, ci_low=lo_ci, ci_high=hi_ci,
                                  verdict="better" if lo_ci > 0 else ("worse" if hi_ci < 0 else "not distinguishable")))
bt = pd.DataFrame(boot_rows); print(bt.to_string(index=False))

# ---------------------------------------------------------------- grouped permutation importance (run D, seed 0)
print("\n=== GROUPED PERMUTATION IMPORTANCE (run D, test 2022, dRMSE when block shuffled) ===")
mD = models["D"]; colsD = RUNS["D"]
yt = te.pm25.values; rng = np.random.default_rng(7)
base_rmse = np.sqrt(np.mean((yt - np.clip(np.expm1(mD.predict(te[colsD])), 0, None))**2))
imp = []
for g, gcols in {"weather": WEATHER, "calendar": CALENDAR, "local_emissions": LOCAL, "upwind": UPWIND}.items():
    d = []
    for _ in range(3):
        Xp = te[colsD].copy(); perm = rng.permutation(len(Xp))
        Xp[gcols] = Xp[gcols].values[perm]
        d.append(np.sqrt(np.mean((yt - np.clip(np.expm1(mD.predict(Xp)), 0, None))**2)) - base_rmse)
    imp.append(dict(block=g, dRMSE=np.mean(d), sd=np.std(d)))
imp = pd.DataFrame(imp).sort_values("dRMSE", ascending=False); print(imp.to_string(index=False))

# ---------------------------------------------------------------- save
res.to_csv(OUT/"baseline_metrics.csv", index=False); bt.to_csv(OUT/"baseline_bootstrap.csv", index=False)
imp.to_csv(OUT/"baseline_perm_importance.csv", index=False)
pr = te[["location_id","date","state","month","pm25","in_north_india_box","base"]].copy()
for r, p in preds.items(): pr[f"pred_{r}"] = p
pr.to_parquet(OUT/"predictions_2022.parquet", index=False)
json.dump({"backend": BACKEND, "seeds": SEEDS, "n_train": len(tr), "n_test": len(te)}, open(OUT/"run_info.json","w"))
print(f"\nsaved to {OUT}/  (predictions_2022.parquet feeds the Delhi Oct-Nov residual check)")
