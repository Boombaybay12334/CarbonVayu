"""
16_save_production_models_v3.py -- CarbonVayu mlv3 Production Model Bundle
Trains the final full 5-year (2019-2023) models and saves them to models/v3_production/:
  - stage1_lgb_seed{0,1,2}.joblib  (3-seed LightGBM nuisance ensemble)
  - stage2_monotone_v3.json        (intercept + 9 monotone-decay betas)
  - manifest.json                  (exact feature order, nodes, metadata)
"""
import json
import time
import warnings
from pathlib import Path
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
t0 = time.time()

MODEL_DIR = Path("models/v3_production")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# 1. Load aligned 5-year data
print("[1/4] Loading 5-year features & exposures...")
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
COLS_C = WEATHER + CALENDAR + LOCAL
BINS = ["0_24h", "24_48h", "48_72h"]
SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES = [f"{s}_{b}" for s, b in SB]

df = base.dropna(subset=COLS_C + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)

y_all = df["pm25"].values.astype(np.float64)
yw_all = (df["date"].dt.year * 100 + df["date"].dt.isocalendar().week.astype(int)).values
X_c = df[COLS_C]
X_exp = np.column_stack([
    exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).values for s, b in SB
]).astype(np.float64)

def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )

# 2. Cross-fit OOF residuals across all 5 years (for unbiased Stage-2 fit)
print("[2/4] Cross-fitting 5-fold GroupKFold OOF residuals on 2019-2023...")
oof_c = np.zeros(len(df), dtype=np.float64)
for tr_i, va_i in GroupKFold(n_splits=5).split(X_c, groups=yw_all):
    m = make_lgb(0).fit(X_c.iloc[tr_i], np.log1p(y_all[tr_i]))
    oof_c[va_i] = np.clip(np.expm1(m.predict(X_c.iloc[va_i])), 0, None)
resid_all = y_all - oof_c

# 3. Train & save final 3-seed Stage-1 LightGBM ensemble on full 2019-2023 data
print("[3/4] Training & saving final 3-seed Stage-1 LightGBM ensemble...")
for seed in [0, 1, 2]:
    model = make_lgb(seed).fit(X_c, np.log1p(y_all))
    out_file = MODEL_DIR / f"stage1_lgb_seed{seed}.joblib"
    joblib.dump(model, out_file, compress=3)
    print(f"  Saved {out_file} ({out_file.stat().st_size / 1e6:.2f} MB)")

# 4. Fit & save final Stage-2 Monotone-Decay NNLS weights
print("[4/4] Fitting & saving Stage-2 Monotone-Decay weights...")
X_cum = np.zeros_like(X_exp)
for k in range(3):
    c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
    X_cum[:, c0] = X_exp[:, c0]
    X_cum[:, c1] = X_exp[:, c0] + X_exp[:, c1]
    X_cum[:, c2] = X_exp[:, c0] + X_exp[:, c1] + X_exp[:, c2]

A = np.hstack([np.ones((len(X_cum), 1)), X_cum])
sol = lsq_linear(A, resid_all, bounds=(np.r_[-np.inf, np.zeros(9)], np.inf)).x
alpha, raw_d = float(sol[0]), sol[1:]
betas = np.zeros(9, dtype=np.float64)
for k in range(3):
    c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
    betas[c2] = raw_d[c2]
    betas[c1] = raw_d[c2] + raw_d[c1]
    betas[c0] = raw_d[c2] + raw_d[c1] + raw_d[c0]

stage2_payload = {
    "intercept": alpha,
    "betas": {name: float(val) for name, val in zip(NAMES, betas)},
    "constraint": "monotone_decay_per_sector (b0 >= b1 >= b2 >= 0)",
    "train_years": [2019, 2020, 2021, 2022, 2023],
    "n_rows": int(len(df)),
    "n_stations": int(df["location_id"].nunique()),
}
(MODEL_DIR / "stage2_monotone_v3.json").write_text(json.dumps(stage2_payload, indent=2))

manifest = {
    "version": "carbonvayu_mlv3_production",
    "stage1_models": [f"stage1_lgb_seed{s}.joblib" for s in [0, 1, 2]],
    "stage1_features": COLS_C,
    "stage2_file": "stage2_monotone_v3.json",
    "stage2_param_order": NAMES,
    "nodes": nodes,
}
(MODEL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

print(f"\nDone in {time.time() - t0:.1f}s! Production bundle saved to {MODEL_DIR}/")
print("Stage-2 Monotone Betas:", json.dumps(stage2_payload["betas"], indent=2))
