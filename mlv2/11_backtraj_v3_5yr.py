"""
11_backtraj_v3_5yr.py -- CarbonVayu mlv3
5-year (2019-2023) Trajectory v2:
  - 1-hour substeps (72 steps) with linear time interpolation on 6h ERA5
  - Shallow-layer wind blend: 0.3 * 10m + 0.7 * 925 hPa
  - HYSPLIT wet scavenging along path using ERA5 tp
  - 3 sectors: agri (PM2.5), other (PM2.5), sia (SO2/64 + NOx/46 + NH3/17)
  - EDGAR 2023 mapped to 2022 (min(year, 2022))
"""
import time
import numpy as np
import pandas as pd
import xarray as xr

t0_wall = time.time()
YEARS = [2019, 2020, 2021, 2022, 2023]

# 1. Load node grid
print("Loading EDGAR node lookup...")
ng = np.load("data/edgar_node_grid.npz", allow_pickle=True)
e_lats, e_lons = ng["lats"], ng["lons"]
node_grid = ng["node_grid"]
node_names = list(ng["node_names"])
n_nodes = len(node_names)
e_lat0, e_dlat = e_lats[0], e_lats[1] - e_lats[0]
e_lon0, e_dlon = e_lons[0], e_lons[1] - e_lons[0]
e_nlat, e_nlon = len(e_lats), len(e_lons)

# 2. Load cleaned 5-year station-days
df = pd.read_parquet("data/features_daily_2019_2023.parquet", columns=["location_id", "date", "lat", "lon"])
df["date"] = pd.to_datetime(df["date"])
n_obs = len(df)
print(f"Station-days to process: {n_obs:,} ({df['location_id'].nunique()} stations)")

# 3. Load 6-hourly ERA5 925 hPa winds + 10m winds + tp (2019-2023)
print("Loading 6-hourly ERA5 925 hPa + 10m winds + precipitation (2019-2023)...")
u_list, v_list, tp_list, t_list = [], [], [], []
for yr in YEARS:
    with xr.open_dataset(f"era5/winds_pl/era5_winds_{yr}.nc") as ds_pl:
        tc = "valid_time" if "valid_time" in ds_pl.coords else "time"
        lc = next(c for c in ["pressure_level", "level", "isobaricInhPa"] if c in ds_pl.coords)
        sub_pl = ds_pl[["u", "v"]].sel({lc: 925}, method="nearest").sortby("latitude").sortby("longitude")
        if yr == YEARS[0]:
            w_lats = sub_pl["latitude"].values.astype(np.float64)
            w_lons = sub_pl["longitude"].values.astype(np.float64)
        u925 = sub_pl["u"].values.astype(np.float32)
        v925 = sub_pl["v"].values.astype(np.float32)
        t_list.append(pd.to_datetime(sub_pl[tc].values))

    with xr.open_dataset(f"era5/weather_sl/{yr}/data_stream-oper_stepType-instant.nc") as ds_sl:
        sub_sl = ds_sl[["u10", "v10"]].sortby("latitude").sortby("longitude")
        u10 = sub_sl["u10"].values.astype(np.float32)
        v10 = sub_sl["v10"].values.astype(np.float32)

    with xr.open_dataset(f"era5/weather_sl/{yr}/data_stream-oper_stepType-accum.nc") as ds_tp:
        sub_tp = ds_tp["tp"].sortby("latitude").sortby("longitude")
        tp_mm_hr = np.clip(sub_tp.values.astype(np.float32) * 1000.0, 0.0, None)

    u_list.append(0.3 * u10 + 0.7 * u925)
    v_list.append(0.3 * v10 + 0.7 * v925)
    tp_list.append(tp_mm_hr)

u_wind = np.concatenate(u_list, axis=0)
v_wind = np.concatenate(v_list, axis=0)
tp_grid = np.concatenate(tp_list, axis=0)
w_times = pd.DatetimeIndex(np.concatenate(t_list))

expected_steps = (pd.Timestamp("2024-01-01") - pd.Timestamp("2019-01-01")).days * 4
assert len(w_times) == expected_steps, f"Expected {expected_steps} 6h steps, got {len(w_times)}"

w_lat0, w_dlat = w_lats[0], w_lats[1] - w_lats[0]
w_lon0, w_dlon = w_lons[0], w_lons[1] - w_lons[0]
w_nlat, w_nlon, n_tsteps = len(w_lats), len(w_lons), len(w_times)


def sample_met_linear(t_float, lat, lon):
    """Linear time interpolation between 6-hourly ERA5 steps + nearest spatial cell."""
    t_clamped = np.clip(t_float, 0.0, n_tsteps - 1.0001)
    t0 = np.floor(t_clamped).astype(np.int32)
    t1 = np.minimum(t0 + 1, n_tsteps - 1)
    w = (t_clamped - t0).astype(np.float32)

    li = np.clip(np.rint((lat - w_lat0) / w_dlat).astype(np.int32), 0, w_nlat - 1)
    lo = np.clip(np.rint((lon - w_lon0) / w_dlon).astype(np.int32), 0, w_nlon - 1)

    u = (1.0 - w) * u_wind[t0, li, lo] + w * u_wind[t1, li, lo]
    v = (1.0 - w) * v_wind[t0, li, lo] + w * v_wind[t1, li, lo]
    p = (1.0 - w) * tp_grid[t0, li, lo] + w * tp_grid[t1, li, lo]
    return u, v, p


# 4. Load EDGAR monthly grids (2019-2022, 48 months; 2023 mapped to 2022)
print("Loading EDGAR v8.1 monthly grids (2019-2022; PM2.5 + SO2/NOx/NH3 precursors)...")
ALL_SECTORS = [
    "bkl_AGRICULTURE", "bkl_BUILDINGS", "bkl_FUEL_EXPLOITATION", "bkl_IND_COMBUSTION",
    "bkl_IND_PROCESSES", "bkl_POWER_INDUSTRY", "bkl_TRANSPORT", "bkl_WASTE",
]
OTHER_SECTORS = [s for s in ALL_SECTORS if s != "bkl_AGRICULTURE"]


def load_edgar_sum(species, sectors):
    yr_arrays = []
    for yr in [2019, 2020, 2021, 2022]:
        acc = None
        for sec in sectors:
            path = f"edgar_v81/monthly/{species}/{sec}/v8.1_FT2022_AP_{species}_{yr}_{sec}_emi.nc"
            with xr.open_dataset(path) as ds:
                da = ds[list(ds.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100)).values
                da = np.nan_to_num(da, nan=0.0).astype(np.float32)
                acc = da if acc is None else (acc + da)
        yr_arrays.append(acc)
    return np.concatenate(yr_arrays, axis=0)  # (48, nlat, nlon)


edgar_agri = load_edgar_sum("PM2.5", ["bkl_AGRICULTURE"])
edgar_other = load_edgar_sum("PM2.5", OTHER_SECTORS)
edgar_sia = (
    load_edgar_sum("SO2", ALL_SECTORS) / 64.0
    + load_edgar_sum("NOx", ALL_SECTORS) / 46.0
    + load_edgar_sum("NH3", ALL_SECTORS) / 17.0
).astype(np.float32)

step_to_m48 = ((np.minimum(w_times.year, 2022) - 2019) * 12 + (w_times.month - 1)).values.astype(np.int32)

# 5. Integrate 72h back-trajectories (72 x 1-hour RK2 substeps, 4 synoptic starts/day)
print("Integrating 72h back-trajectories (1h substeps, RK2, wet scavenging)...")
DT_SEC = 3600.0
M_PER_DEG = 111320.0
N_SUBSTEPS = 72
BINS = ["0_24h", "24_48h", "48_72h"]

base_tidx = ((df["date"] - pd.Timestamp("2019-01-01")).dt.days.values * 4).astype(np.int32)
obs_idx = np.arange(n_obs, dtype=np.int32)

acc_agri = np.zeros((3, n_obs, n_nodes), dtype=np.float32)
acc_other = np.zeros((3, n_obs, n_nodes), dtype=np.float32)
acc_sia = np.zeros((3, n_obs, n_nodes), dtype=np.float32)

for syn_offset in range(4):
    lat = df["lat"].values.astype(np.float64).copy()
    lon = df["lon"].values.astype(np.float64).copy()
    t_float = (base_tidx + syn_offset).astype(np.float64)
    surv = np.ones(n_obs, dtype=np.float32)

    for s in range(N_SUBSTEPS):
        u1, v1, p1 = sample_met_linear(t_float, lat, lon)
        cos_lat1 = np.maximum(np.cos(np.deg2rad(lat)), 0.1)
        mid_lat = lat - 0.5 * (v1 * DT_SEC) / M_PER_DEG
        mid_lon = lon - 0.5 * (u1 * DT_SEC) / (M_PER_DEG * cos_lat1)

        u2, v2, p2 = sample_met_linear(t_float - (0.5 / 6.0), mid_lat, mid_lon)
        cos_lat2 = np.maximum(np.cos(np.deg2rad(mid_lat)), 0.1)
        lat = lat - (v2 * DT_SEC) / M_PER_DEG
        lon = lon - (u2 * DT_SEC) / (M_PER_DEG * cos_lat2)
        t_float -= 1.0 / 6.0

        p_hr = 0.5 * (p1 + p2)
        wet = p_hr > 0.05
        if np.any(wet):
            surv[wet] *= np.exp(-0.288 * np.power(p_hr[wet], 0.79))

        in_box = (lat >= 0.0) & (lat <= 40.0) & (lon >= 60.0) & (lon <= 100.0)
        if not np.any(in_box):
            continue

        b_idx = s // 24
        oi = obs_idx[in_box]
        sv = surv[in_box]
        li = np.clip(np.rint((lat[in_box] - e_lat0) / e_dlat).astype(np.int32), 0, e_nlat - 1)
        lo = np.clip(np.rint((lon[in_box] - e_lon0) / e_dlon).astype(np.int32), 0, e_nlon - 1)
        m48 = step_to_m48[np.clip(np.rint(t_float[in_box]).astype(np.int32), 0, n_tsteps - 1)]
        nid = node_grid[li, lo]

        np.add.at(acc_agri[b_idx], (oi, nid), edgar_agri[m48, li, lo] * sv)
        np.add.at(acc_other[b_idx], (oi, nid), edgar_other[m48, li, lo] * sv)
        np.add.at(acc_sia[b_idx], (oi, nid), edgar_sia[m48, li, lo] * sv)

    print(f"    Finished synoptic hour {syn_offset * 6:02d}:00 UTC ({time.time() - t0_wall:.1f}s)")

acc_agri /= 96.0
acc_other /= 96.0
acc_sia /= 96.0

# 6. Assemble and save
print("Assembling Parquet output...")
cols = {"location_id": df["location_id"].values, "date": df["date"].values}
for b_idx, b_name in enumerate(BINS):
    for n_idx, n_name in enumerate(node_names):
        cols[f"exp_{n_name}_agri_{b_name}"] = acc_agri[b_idx, :, n_idx]
        cols[f"exp_{n_name}_other_{b_name}"] = acc_other[b_idx, :, n_idx]
        cols[f"exp_{n_name}_sia_{b_name}"] = acc_sia[b_idx, :, n_idx]

out_df = pd.DataFrame(cols)
out_path = "data/node_exposure_v3_daily_2019_2023.parquet"
out_df.to_parquet(out_path, index=False)

print(f"\nSaved -> {out_path}")
print(f"Shape: {out_df.shape} | Total time: {time.time() - t0_wall:.1f}s")

delhi_mask = (
    pd.read_parquet("data/features_daily_2019_2023.parquet", columns=["state", "month"])
    .eval("state == 'NCT of Delhi' and month in [10, 11]")
    .values
)
for sec in ["agri", "sia"]:
    scols = [c for c in out_df.columns if f"_{sec}_0_24h" in c]
    print(f"\nSanity check — Top 5 0-24h {sec.upper()} Exposure nodes for NCT of Delhi (Oct-Nov, 2019-2023):")
    print(out_df.loc[delhi_mask, scols].mean().sort_values(ascending=False).head(5).to_string())
