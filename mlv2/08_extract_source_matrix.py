"""
08_extract_source_matrix.py -- CarbonVayu mlv2
Extracts the State-to-State PM2.5 Source Attribution Matrix from the D2 ensemble
via zero-out counterfactual perturbation on 2022 test data.
"""
import warnings
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
OUT = Path("results")
OUT.mkdir(exist_ok=True)
SEEDS = [0, 1, 2]

# 1. Load & merge D2 dataset
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
NODE_EXP = [c for c in exp.columns if c.startswith("exp_")]
COLS_D2 = WEATHER + CALENDAR + LOCAL + NODE_EXP

df = df.dropna(subset=WEATHER + CALENDAR + LOCAL + ["pm25"]).reset_index(drop=True)
tr = df[df.year == 2021].copy()
te = df[df.year == 2022].copy().reset_index(drop=True)

# 2. Train 3-seed D2 ensemble
print(f"Training D2 ensemble ({len(SEEDS)} seeds, {len(COLS_D2)} features)...")
ytr = np.log1p(tr.pm25.values)
models = []
for s in SEEDS:
    m = lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=s, n_jobs=-1, verbose=-1,
    )
    m.fit(tr[COLS_D2], ytr)
    models.append(m)

def predict_ensemble(X):
    return np.mean([np.clip(np.expm1(m.predict(X)), 0, None) for m in models], axis=0)

X_te = te[COLS_D2].copy()
base_pred = predict_ensemble(X_te)

# 3. Zero-out counterfactual per source node (all 6 cols: agri+other x 3 bins)
print(f"Computing zero-out counterfactuals for {len(nodes)} source nodes...")
deltas = {}
for node in nodes:
    n_cols = [c for c in NODE_EXP if c.startswith(f"exp_{node}_")]
    if not n_cols:
        continue
    saved = X_te[n_cols].copy()
    X_te[n_cols] = 0.0
    cf_pred = predict_ensemble(X_te)
    X_te[n_cols] = saved
    # Positive delta = µg/m³ attributable to this source node
    deltas[node] = np.clip(base_pred - cf_pred, 0.0, None)

delta_df = pd.DataFrame(deltas)
delta_df["receptor_state"] = te["state"].values
delta_df["month"] = te["month"].values

def build_and_save_matrix(sub_df, tag):
    mat_ug = sub_df.groupby("receptor_state")[nodes].mean()
    row_sums = mat_ug.sum(axis=1).replace(0, np.nan)
    mat_pct = mat_ug.div(row_sums, axis=0) * 100.0
    mat_ug.to_csv(OUT / f"source_matrix_{tag}_ugm3.csv")
    mat_pct.to_csv(OUT / f"source_matrix_{tag}_pct.csv")
    return mat_ug, mat_pct

ann_ug, ann_pct = build_and_save_matrix(delta_df, "annual_2022")
octnov_ug, octnov_pct = build_and_save_matrix(delta_df[delta_df["month"].isin([10, 11])], "octnov_2022")

# 4. Sectoral split (agri vs other) specifically for NCT of Delhi Oct-Nov
print("\nComputing Agri vs Other sectoral split for NCT of Delhi (Oct-Nov 2022)...")
delhi_mask = ((te["state"] == "NCT of Delhi") & te["month"].isin([10, 11])).values
X_del = te.loc[delhi_mask, COLS_D2].copy()
del_base = predict_ensemble(X_del)

sec_rows = []
for node in nodes:
    row = {"source_node": node}
    for sec in ["agri", "other"]:
        scols = [c for c in NODE_EXP if c.startswith(f"exp_{node}_{sec}_")]
        saved = X_del[scols].copy()
        X_del[scols] = 0.0
        cf = predict_ensemble(X_del)
        X_del[scols] = saved
        row[f"{sec}_ugm3"] = np.clip(del_base - cf, 0.0, None).mean()
    row["total_ugm3"] = row["agri_ugm3"] + row["other_ugm3"]
    sec_rows.append(row)

sec_df = pd.DataFrame(sec_rows).sort_values("total_ugm3", ascending=False)
sec_df["share_pct"] = 100.0 * sec_df["total_ugm3"] / max(sec_df["total_ugm3"].sum(), 1e-6)
sec_df.to_csv(OUT / "delhi_octnov_2022_source_sector_split.csv", index=False)

pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

print("\n=== NCT OF DELHI (Oct-Nov 2022) — TOP 10 UPWIND SOURCE NODES ===")
print(sec_df.head(10).to_string(index=False))

print("\n=== KEY NORTH INDIA RECEPTORS (Oct-Nov 2022, Top 5 Sources % Share) ===")
for rec in ["NCT of Delhi", "Haryana", "Uttar Pradesh", "Punjab", "Bihar"]:
    if rec in octnov_pct.index:
        top5 = octnov_pct.loc[rec].sort_values(ascending=False).head(5)
        top_str = " | ".join([f"{k}: {v:.1f}%" for k, v in top5.items()])
        print(f"  {rec:<15} -> {top_str}")

print(f"\nSaved all matrices to {OUT}/")
