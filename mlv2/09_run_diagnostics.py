"""
09_run_diagnostics.py -- CarbonVayu mlv2
Runs the 5 pre-optimization audits:
  1. Outlier SSE audit (All-India vs North Box)
  2. Unseen-station generalization (48 stations not in 2021 train)
  3. Delhi Oct-Nov agri magnitude vs actual PM2.5
  4. Reverse-year split (Train 2022 -> Test 2021)
  5. Wind-regime vs Emissions tests (residence-time-only, drop 0-24h, drop own node)
"""
import re
import warnings
import lightgbm as lgb
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# ---------------------------------------------------------------- helpers
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

def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    mae = np.mean(np.abs(y - p))
    r2 = 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
    sp = spearmanr(y, p)[0]
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp)

def fit_pred(tr, te, cols, seed=0):
    m = lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )
    m.fit(tr[cols], np.log1p(tr["pm25"].values))
    return np.clip(np.expm1(m.predict(te[cols])), 0, None)

# ========================================================================
# 1. OUTLIER AUDIT (from saved 2022 D2 predictions)
# ========================================================================
print("=" * 75)
print("[1] OUTLIER AUDIT (2022 test, run D2)")
print("=" * 75)
p22 = pd.read_parquet("results/predictions_d2_2022.parquet")
p22["err"] = p22["pm25"] - p22["pred_D2"]
p22["sq_err"] = p22["err"] ** 2

for label, mask in [("North Box", p22["in_north_india_box"] == True),
                    ("Non-North", p22["in_north_india_box"] == False)]:
    m = metrics(p22.loc[mask, "pm25"], p22.loc[mask, "pred_D2"])
    print(f"  {label:<10} (n={m['n']:5,}) -> RMSE: {m['RMSE']:6.2f} | MAE: {m['MAE']:5.2f} | R2: {m['R2']:+.3f} | Spearman: {m['Spearman']:.3f}")

g = p22.groupby("location_id").agg(
    state=("state", "first"),
    north=("in_north_india_box", "first"),
    n=("err", "size"),
    rmse=("err", lambda e: np.sqrt((e ** 2).mean())),
    max_pm25=("pm25", "max"),
    sse=("sq_err", "sum"),
)
g["share_sse_pct"] = 100.0 * g["sse"] / g["sse"].sum()
print("\nTop 10 stations by share of total Squared Error (SSE):")
print(g.sort_values("sse", ascending=False).head(10).to_string())

# ========================================================================
# 2. UNSEEN-STATION GENERALIZATION (48 stations not in 2021 train)
# ========================================================================
print("\n" + "=" * 75)
print("[2] UNSEEN-STATION GENERALIZATION (2022 stations absent from 2021)")
print("=" * 75)
base = pd.read_parquet("data/features_daily_2021_2022.parquet")
base["date"] = pd.to_datetime(base["date"])
base["year"] = base["date"].dt.year
base["month"] = base["date"].dt.month

train_locs = set(base.loc[base["year"] == 2021, "location_id"].unique())
unseen = p22[~p22["location_id"].isin(train_locs)]
print(f"Unseen stations: {unseen['location_id'].nunique()} | Rows: {len(unseen):,}")

rows = []
for sub, msk in [("unseen_all", np.ones(len(unseen), bool)),
                 ("unseen_north", unseen["in_north_india_box"].astype(bool).values)]:
    if msk.sum() > 10:
        for run in ["C", "D", "D2"]:
            rows.append(dict(subset=sub, run=run, **metrics(unseen.loc[msk, "pm25"], unseen.loc[msk, f"pred_{run}"])))
print(pd.DataFrame(rows).to_string(index=False))

# ========================================================================
# 3. DELHI OCT-NOV MAGNITUDE CHECK
# ========================================================================
print("\n" + "=" * 75)
print("[3] DELHI OCT-NOV 2022 MAGNITUDE CHECK (vs 20-40% literature range)")
print("=" * 75)
del_rows = p22[(p22["state"] == "NCT of Delhi") & (p22["month"].isin([10, 11]))]
sec_df = pd.read_csv("results/delhi_octnov_2022_source_sector_split.csv")
mean_act = del_rows["pm25"].mean()
mean_pred = del_rows["pred_D2"].mean()
tot_agri = sec_df["agri_ugm3"].sum()
tot_other = sec_df["other_ugm3"].sum()
print(f"  Delhi Oct-Nov actual mean PM2.5:     {mean_act:.1f} µg/m³")
print(f"  Delhi Oct-Nov D2 pred mean PM2.5:    {mean_pred:.1f} µg/m³")
print(f"  Sum of node zero-out Agri:           {tot_agri:.1f} µg/m³ ({100*tot_agri/mean_act:.1f}% of actual PM2.5)")
print(f"  Sum of node zero-out Other:          {tot_other:.1f} µg/m³ ({100*tot_other/mean_act:.1f}% of actual PM2.5)")
print(f"  Sum of node zero-out Total:          {tot_agri+tot_other:.1f} µg/m³ ({100*(tot_agri+tot_other)/mean_act:.1f}% of actual PM2.5)")

# ========================================================================
# 4. REVERSE-YEAR SPLIT (Train 2022 -> Test 2021, seed 0)
# ========================================================================
print("\n" + "=" * 75)
print("[4] REVERSE-YEAR SPLIT (Train 2022 -> Test 2021, seed 0)")
print("=" * 75)
exp = pd.read_parquet("data/node_exposure_daily_2021_2022.parquet")
exp["date"] = pd.to_datetime(exp["date"])
NODE_EXP = [c for c in exp.columns if c.startswith("exp_")]

df = base.merge(exp, on=["location_id", "date"], how="inner")
df = df.dropna(subset=WEATHER + CALENDAR + LOCAL + UPWIND + ["pm25"]).reset_index(drop=True)

tr_rev = df[df["year"] == 2022].copy()
te_rev = df[df["year"] == 2021].copy().reset_index(drop=True)

rev_subsets = {
    "all": np.ones(len(te_rev), bool),
    "north_box": te_rev["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((te_rev["state"] == "NCT of Delhi") & te_rev["month"].isin([10, 11])).values,
}

rev_rows = []
for run, cols in [("C", WEATHER + CALENDAR + LOCAL),
                  ("D", WEATHER + CALENDAR + LOCAL + UPWIND),
                  ("D2", WEATHER + CALENDAR + LOCAL + NODE_EXP)]:
    pr = fit_pred(tr_rev, te_rev, cols, seed=0)
    for sub, msk in rev_subsets.items():
        rev_rows.append(dict(run=run, subset=sub, **metrics(te_rev.loc[msk, "pm25"], pr[msk])))
print(pd.DataFrame(rev_rows).to_string(index=False))

# ========================================================================
# 5. WIND REGIME VS EMISSIONS TESTS (Train 2021 -> Test 2022, seed 0)
# ========================================================================
print("\n" + "=" * 75)
print("[5] WIND REGIME vs EMISSIONS TESTS (2021 -> 2022, seed 0)")
print("=" * 75)

# 5a. Compute residence-time-only features (no emissions, ~8s)
print("Computing 72h residence-time-only features (hours per node, no emissions)...")
ng = np.load("data/edgar_node_grid.npz", allow_pickle=True)
e_lats, e_lons, node_grid = ng["lats"], ng["lons"], ng["node_grid"]
node_names = list(ng["node_names"])
n_nodes = len(node_names)
e_lat0, e_dlat = e_lats[0], e_lats[1] - e_lats[0]
e_lon0, e_dlon = e_lons[0], e_lons[1] - e_lons[0]
e_nlat, e_nlon = len(e_lats), len(e_lons)

u_list, v_list, t_list = [], [], []
for yr in [2021, 2022]:
    with xr.open_dataset(f"era5/winds_pl/era5_winds_{yr}.nc") as ds:
        tc = "valid_time" if "valid_time" in ds.coords else "time"
        lc = next(c for c in ["pressure_level", "level", "isobaricInhPa"] if c in ds.coords)
        sub = ds[["u", "v"]].sel({lc: 925}, method="nearest").sortby("latitude").sortby("longitude")
        if yr == 2021:
            w_lats, w_lons = sub["latitude"].values.astype(np.float64), sub["longitude"].values.astype(np.float64)
        u_list.append(sub["u"].values.astype(np.float32))
        v_list.append(sub["v"].values.astype(np.float32))
        t_list.append(pd.to_datetime(sub[tc].values))

u_wind, v_wind = np.concatenate(u_list, axis=0), np.concatenate(v_list, axis=0)
w_lat0, w_dlat = w_lats[0], w_lats[1] - w_lats[0]
w_lon0, w_dlon = w_lons[0], w_lons[1] - w_lons[0]
w_nlat, w_nlon, n_tsteps = len(w_lats), len(w_lons), len(u_wind)

def sample_wind(t_idx, lat, lon):
    ti = np.clip(t_idx, 0, n_tsteps - 1)
    li = np.clip(np.rint((lat - w_lat0) / w_dlat).astype(np.int32), 0, w_nlat - 1)
    lo = np.clip(np.rint((lon - w_lon0) / w_dlon).astype(np.int32), 0, w_nlon - 1)
    return u_wind[ti, li, lo], v_wind[ti, li, lo]

n_obs = len(df)
base_tidx = ((df["date"] - pd.Timestamp("2021-01-01")).dt.days.values * 4).astype(np.int32)
obs_idx = np.arange(n_obs, dtype=np.int32)
acc_rt = np.zeros((3, n_obs, n_nodes), dtype=np.float32)

for syn_offset in range(4):
    lat = df["lat"].values.astype(np.float64).copy()
    lon = df["lon"].values.astype(np.float64).copy()
    t_float = (base_tidx + syn_offset).astype(np.float64)
    for s in range(24):
        u1, v1 = sample_wind(np.rint(t_float).astype(np.int32), lat, lon)
        mid_lat = lat - 0.5 * (v1 * 10800.0) / 111320.0
        mid_lon = lon - 0.5 * (u1 * 10800.0) / (111320.0 * np.maximum(np.cos(np.deg2rad(lat)), 0.1))
        u2, v2 = sample_wind(np.rint(t_float - 0.25).astype(np.int32), mid_lat, mid_lon)
        lat = lat - (v2 * 10800.0) / 111320.0
        lon = lon - (u2 * 10800.0) / (111320.0 * np.maximum(np.cos(np.deg2rad(mid_lat)), 0.1))
        t_float -= 0.5
        in_box = (lat >= 0.0) & (lat <= 40.0) & (lon >= 60.0) & (lon <= 100.0)
        if np.any(in_box):
            li = np.clip(np.rint((lat[in_box] - e_lat0) / e_dlat).astype(np.int32), 0, e_nlat - 1)
            lo = np.clip(np.rint((lon[in_box] - e_lon0) / e_dlon).astype(np.int32), 0, e_nlon - 1)
            np.add.at(acc_rt[s // 8], (obs_idx[in_box], node_grid[li, lo]), 0.75)  # 3h / 4 starts = 0.75h

rt_cols = []
rt_dict = {}
for b_idx, b_name in enumerate(["0_24h", "24_48h", "48_72h"]):
    for n_idx, n_name in enumerate(node_names):
        c = f"rt_{n_name}_{b_name}"
        rt_cols.append(c)
        rt_dict[c] = acc_rt[b_idx, :, n_idx]
df_rt = pd.concat([df, pd.DataFrame(rt_dict)], axis=1)

# Helper to zero out receptor's own state node
NE_STATES = {"arunachal pradesh", "assam", "manipur", "meghalaya", "mizoram", "nagaland", "sikkim", "tripura"}
def state_to_node(s):
    s = str(s).strip().lower()
    if s in NE_STATES: return "ind_ne_india"
    if s == "nct of delhi": return "ind_delhi"
    if s == "jammu and kashmir": return "ind_jk"
    if s == "andaman and nicobar": return "ind_andaman"
    return "ind_" + re.sub(r"[^a-z0-9]+", "_", s).strip("_")

df_no_own = df.copy()
own_nodes = df_no_own["state"].apply(state_to_node).values
for node in node_names:
    m_own = own_nodes == node
    if np.any(m_own):
        ncols = [c for c in NODE_EXP if c.startswith(f"exp_{node}_")]
        df_no_own.loc[m_own, ncols] = 0.0

tr21 = df_rt[df_rt["year"] == 2021]
te22 = df_rt[df_rt["year"] == 2022].reset_index(drop=True)
tr21_no = df_no_own[df_no_own["year"] == 2021]
te22_no = df_no_own[df_no_own["year"] == 2022].reset_index(drop=True)

fwd_subsets = {
    "all": np.ones(len(te22), bool),
    "north_box": te22["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((te22["state"] == "NCT of Delhi") & te22["month"].isin([10, 11])).values,
}

EXP_NO_0_24 = [c for c in NODE_EXP if not c.endswith("_0_24h")]
test_runs = [
    ("D2_full (emissions+path)", tr21, te22, WEATHER + CALENDAR + LOCAL + NODE_EXP),
    ("D2_restime_only (path only)", tr21, te22, WEATHER + CALENDAR + LOCAL + rt_cols),
    ("D2_no_0_24h (24-72h only)", tr21, te22, WEATHER + CALENDAR + LOCAL + EXP_NO_0_24),
    ("D2_no_own_node", tr21_no, te22_no, WEATHER + CALENDAR + LOCAL + NODE_EXP),
]

t_rows = []
for name, tr_d, te_d, cols in test_runs:
    pr = fit_pred(tr_d, te_d, cols, seed=0)
    for sub, msk in fwd_subsets.items():
        t_rows.append(dict(variant=name, subset=sub, **metrics(te_d.loc[msk, "pm25"], pr[msk])))
print(pd.DataFrame(t_rows).to_string(index=False))
