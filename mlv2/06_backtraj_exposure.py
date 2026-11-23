import time
import numpy as np
import pandas as pd
import xarray as xr

t0_wall = time.time()

# 1. Load node grid
print("Loading EDGAR node lookup...")
ng = np.load("data/edgar_node_grid.npz", allow_pickle=True)
e_lats = ng["lats"]
e_lons = ng["lons"]
node_grid = ng["node_grid"]          # (nlat, nlon) int16
node_names = list(ng["node_names"])
n_nodes = len(node_names)
e_lat0, e_dlat = e_lats[0], e_lats[1] - e_lats[0]
e_lon0, e_dlon = e_lons[0], e_lons[1] - e_lons[0]
e_nlat, e_nlon = len(e_lats), len(e_lons)

# 2. Load target station-days from features table
df = pd.read_parquet("data/features_daily_2021_2022.parquet", columns=["location_id", "date", "lat", "lon"])
df["date"] = pd.to_datetime(df["date"])
n_obs = len(df)
print(f"Station-days to process: {n_obs:,} ({df['location_id'].nunique()} stations)")

# 3. Load 2021-2022 6-hourly ERA5 925 hPa winds into contiguous NumPy arrays
print("Loading 6-hourly ERA5 925 hPa winds (2021-2022)...")
u_list, v_list, t_list = [], [], []
for yr in [2021, 2022]:
    with xr.open_dataset(f"era5/winds_pl/era5_winds_{yr}.nc") as ds:
        tc = "valid_time" if "valid_time" in ds.coords else "time"
        lc = next(c for c in ["pressure_level", "level", "isobaricInhPa"] if c in ds.coords)
        sub = ds[["u", "v"]].sel({lc: 925}, method="nearest").sortby("latitude").sortby("longitude")
        if yr == 2021:
            w_lats = sub["latitude"].values.astype(np.float64)
            w_lons = sub["longitude"].values.astype(np.float64)
        u_list.append(sub["u"].values.astype(np.float32))
        v_list.append(sub["v"].values.astype(np.float32))
        t_list.append(pd.to_datetime(sub[tc].values))

u_wind = np.concatenate(u_list, axis=0)   # (2920, 161, 161)
v_wind = np.concatenate(v_list, axis=0)
w_times = pd.DatetimeIndex(np.concatenate(t_list))
w_lat0, w_dlat = w_lats[0], w_lats[1] - w_lats[0]
w_lon0, w_dlon = w_lons[0], w_lons[1] - w_lons[0]
w_nlat, w_nlon = len(w_lats), len(w_lons)
n_tsteps = len(w_times)

# Fast nearest-grid wind lookup (vectorized)
def sample_wind(t_idx, lat, lon):
    ti = np.clip(t_idx, 0, n_tsteps - 1)
    li = np.clip(np.rint((lat - w_lat0) / w_dlat).astype(np.int32), 0, w_nlat - 1)
    lo = np.clip(np.rint((lon - w_lon0) / w_dlon).astype(np.int32), 0, w_nlon - 1)
    return u_wind[ti, li, lo], v_wind[ti, li, lo]

# 4. Load EDGAR PM2.5 monthly grids (24 months: 0..11 = 2021, 12..23 = 2022)
print("Loading EDGAR PM2.5 (agri vs other) for 2021-2022...")
OTHER_SECTORS = [
    "bkl_BUILDINGS", "bkl_FUEL_EXPLOITATION", "bkl_IND_COMBUSTION",
    "bkl_IND_PROCESSES", "bkl_POWER_INDUSTRY", "bkl_TRANSPORT", "bkl_WASTE",
]
agri_months, other_months = [], []
for yr in [2021, 2022]:
    p_ag = f"edgar_v81/monthly/PM2.5/bkl_AGRICULTURE/v8.1_FT2022_AP_PM2.5_{yr}_bkl_AGRICULTURE_emi.nc"
    with xr.open_dataset(p_ag) as ds:
        da = ds[list(ds.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100)).values
        agri_months.append(np.nan_to_num(da, nan=0.0).astype(np.float32))

    oth_sum = None
    for sec in OTHER_SECTORS:
        p = f"edgar_v81/monthly/PM2.5/{sec}/v8.1_FT2022_AP_PM2.5_{yr}_{sec}_emi.nc"
        with xr.open_dataset(p) as ds:
            da = ds[list(ds.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100)).values
            da = np.nan_to_num(da, nan=0.0).astype(np.float32)
            oth_sum = da if oth_sum is None else (oth_sum + da)
    other_months.append(oth_sum)

edgar_agri = np.concatenate(agri_months, axis=0)    # (24, nlat, nlon)
edgar_other = np.concatenate(other_months, axis=0)  # (24, nlat, nlon)

# Map each ERA5 6-hourly step to its EDGAR month index (0..23)
step_to_m24 = ((w_times.year - 2021) * 12 + (w_times.month - 1)).values.astype(np.int32)

# 5. Run 72-hour back-trajectories (24 substeps of 3 hours, RK2 midpoint)
# 4 synoptic arrival times per day: 00, 06, 12, 18 UTC
print("Integrating 72h back-trajectories (4 synoptic starts/day, 3h substeps)...")
DT_SEC = 3.0 * 3600.0          # 3-hour substep
M_PER_DEG = 111320.0
N_SUBSTEPS = 24                # 24 * 3h = 72h
BINS = ["0_24h", "24_48h", "48_72h"]

# Base 00:00 UTC index in w_times for each observation's date
base_tidx = ((df["date"] - pd.Timestamp("2021-01-01")).dt.days.values * 4).astype(np.int32)
obs_idx = np.arange(n_obs, dtype=np.int32)

# Accumulators: shape (3 bins, n_obs, n_nodes)
acc_agri = np.zeros((3, n_obs, n_nodes), dtype=np.float32)
acc_other = np.zeros((3, n_obs, n_nodes), dtype=np.float32)

for syn_offset in range(4):  # 00, 06, 12, 18 UTC
    lat = df["lat"].values.astype(np.float64).copy()
    lon = df["lon"].values.astype(np.float64).copy()
    t_float = (base_tidx + syn_offset).astype(np.float64)

    for s in range(N_SUBSTEPS):
        # RK2 midpoint step backward in time (-u, -v)
        t_i = np.rint(t_float).astype(np.int32)
        u1, v1 = sample_wind(t_i, lat, lon)
        cos_lat1 = np.maximum(np.cos(np.deg2rad(lat)), 0.1)
        mid_lat = lat - 0.5 * (v1 * DT_SEC) / M_PER_DEG
        mid_lon = lon - 0.5 * (u1 * DT_SEC) / (M_PER_DEG * cos_lat1)

        t_mid = np.rint(t_float - 0.25).astype(np.int32)
        u2, v2 = sample_wind(t_mid, mid_lat, mid_lon)
        cos_lat2 = np.maximum(np.cos(np.deg2rad(mid_lat)), 0.1)
        lat = lat - (v2 * DT_SEC) / M_PER_DEG
        lon = lon - (u2 * DT_SEC) / (M_PER_DEG * cos_lat2)
        t_float -= 0.5  # 3 hours = 0.5 of a 6-hour ERA5 step

        # Accumulate emissions for parcels still inside the India bounding box
        in_box = (lat >= 0.0) & (lat <= 40.0) & (lon >= 60.0) & (lon <= 100.0)
        if not np.any(in_box):
            continue

        b_idx = s // 8  # 0 (0-24h), 1 (24-48h), 2 (48-72h)
        oi = obs_idx[in_box]
        li = np.clip(np.rint((lat[in_box] - e_lat0) / e_dlat).astype(np.int32), 0, e_nlat - 1)
        lo = np.clip(np.rint((lon[in_box] - e_lon0) / e_dlon).astype(np.int32), 0, e_nlon - 1)
        m24 = step_to_m24[np.clip(np.rint(t_float[in_box]).astype(np.int32), 0, n_tsteps - 1)]
        nid = node_grid[li, lo]

        np.add.at(acc_agri[b_idx], (oi, nid), edgar_agri[m24, li, lo])
        np.add.at(acc_other[b_idx], (oi, nid), edgar_other[m24, li, lo])

    print(f"    Finished synoptic hour {syn_offset * 6:02d}:00 UTC ({time.time() - t0_wall:.1f}s)")

# Average over 4 synoptic starts x 8 substeps per 24h bin = 32 samples per bin
acc_agri /= 32.0
acc_other /= 32.0

# 6. Assemble wide DataFrame and save
print("Assembling Parquet output...")
cols = {"location_id": df["location_id"].values, "date": df["date"].values}
for b_idx, b_name in enumerate(BINS):
    for n_idx, n_name in enumerate(node_names):
        cols[f"exp_{n_name}_agri_{b_name}"] = acc_agri[b_idx, :, n_idx]
        cols[f"exp_{n_name}_other_{b_name}"] = acc_other[b_idx, :, n_idx]

out_df = pd.DataFrame(cols)
out_path = "data/node_exposure_daily_2021_2022.parquet"
out_df.to_parquet(out_path, index=False)

print(f"\nSaved -> {out_path}")
print(f"Shape: {out_df.shape} | Total time: {time.time() - t0_wall:.1f}s")

# Quick sanity check: top 5 upwind agri nodes for Delhi in Oct-Nov
delhi_mask = (
    pd.read_parquet("data/features_daily_2021_2022.parquet", columns=["state", "month"])
    .eval("state == 'NCT of Delhi' and month in [10, 11]")
    .values
)
agri_cols = [c for c in out_df.columns if "_agri_0_24h" in c]
print("\nSanity check — Top 5 0–24h Agri Exposure nodes for NCT of Delhi (Oct–Nov):")
print(out_df.loc[delhi_mask, agri_cols].mean().sort_values(ascending=False).head(5).to_string())
