"""
02_build_features_5yr.py -- CarbonVayu mlv3
Builds data/features_daily_2019_2023.parquet by combining:
  1. data/xkdr_daily_2019_2023.parquet (497 stations, 2019-2023)
  2. Daily ERA5 single-level + pressure-level weather (2019-2023)
  3. Calendar features (doy_sin, doy_cos, day_of_week, is_weekend)
  4. Local EDGAR v8.1 monthly emissions (2019-2022 native, 2023 mapped to 2022)
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd
import xarray as xr

t0 = time.time()
OUT_PATH = Path("data/features_daily_2019_2023.parquet")

# 1. Load 5-year xKDR daily PM2.5 table
print("[1/4] Loading xKDR daily PM2.5 (2019-2023)...")
df = pd.read_parquet("data/xkdr_daily_2019_2023.parquet")
df["date"] = pd.to_datetime(df["date"])
df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month

stations = df[["location_id", "lat", "lon"]].drop_duplicates("location_id").reset_index(drop=True)
st_ids = stations["location_id"].values
st_lats = stations["lat"].values.astype(np.float64)
st_lons = stations["lon"].values.astype(np.float64)
print(f"  Rows: {len(df):,} | Unique stations: {len(stations)}")

# 2. Extract daily ERA5 weather at station coordinates (2019-2023)
print("[2/4] Extracting daily ERA5 weather (2019-2023)...")
era5_parts = []
for yr in range(2019, 2024):
    t_yr = time.time()
    with xr.open_dataset(f"era5/weather_sl/{yr}/data_stream-oper_stepType-instant.nc") as ds_inst:
        tc = "valid_time" if "valid_time" in ds_inst.coords else "time"
        ds_inst = ds_inst.sortby("latitude").sortby("longitude")
        lats = ds_inst["latitude"].values.astype(np.float64)
        lons = ds_inst["longitude"].values.astype(np.float64)
        li = np.clip(np.rint((st_lats - lats[0]) / (lats[1] - lats[0])).astype(int), 0, len(lats) - 1)
        lo = np.clip(np.rint((st_lons - lons[0]) / (lons[1] - lons[0])).astype(int), 0, len(lons) - 1)

        times = pd.to_datetime(ds_inst[tc].values)
        days = times.floor("D")
        u10 = ds_inst["u10"].values[:, li, lo].astype(np.float32)
        v10 = ds_inst["v10"].values[:, li, lo].astype(np.float32)
        t2m = ds_inst["t2m"].values[:, li, lo].astype(np.float32) - 273.15
        d2m = ds_inst["d2m"].values[:, li, lo].astype(np.float32) - 273.15
        blh = ds_inst["blh"].values[:, li, lo].astype(np.float32)

    with xr.open_dataset(f"era5/weather_sl/{yr}/data_stream-oper_stepType-accum.nc") as ds_acc:
        ds_acc = ds_acc.sortby("latitude").sortby("longitude")
        tp = np.clip(ds_acc["tp"].values[:, li, lo].astype(np.float32), 0.0, None)

    with xr.open_dataset(f"era5/winds_pl/era5_winds_{yr}.nc") as ds_pl:
        lc = next(c for c in ["pressure_level", "level", "isobaricInhPa"] if c in ds_pl.coords)
        ds_pl = ds_pl.sortby("latitude").sortby("longitude")
        u925 = ds_pl["u"].sel({lc: 925}, method="nearest").values[:, li, lo].astype(np.float32)
        v925 = ds_pl["v"].sel({lc: 925}, method="nearest").values[:, li, lo].astype(np.float32)
        u850 = ds_pl["u"].sel({lc: 850}, method="nearest").values[:, li, lo].astype(np.float32)
        v850 = ds_pl["v"].sel({lc: 850}, method="nearest").values[:, li, lo].astype(np.float32)

    # Magnus-Tetens RH (%) and wind speeds
    rh = 100.0 * np.exp((17.625 * d2m) / (243.04 + d2m)) / np.exp((17.625 * t2m) / (243.04 + t2m))
    rh = np.clip(rh, 0.0, 100.0)
    wspd10 = np.hypot(u10, v10)
    wspd925 = np.hypot(u925, v925)
    wspd850 = np.hypot(u850, v850)

    # Group 4 synoptic steps -> daily aggregates
    uniq_days, inv = np.unique(days, return_inverse=True)
    n_days = len(uniq_days)
    n_st = len(stations)

    def daily_mean(arr):
        out = np.zeros((n_days, n_st), dtype=np.float32)
        cnt = np.bincount(inv).astype(np.float32)[:, None]
        np.add.at(out, inv, arr)
        return out / cnt

    def daily_min(arr):
        out = np.full((n_days, n_st), np.inf, dtype=np.float32)
        np.minimum.at(out, inv, arr)
        return out

    yr_df = pd.DataFrame({
        "date": np.repeat(uniq_days, n_st),
        "location_id": np.tile(st_ids, n_days),
        "blh_mean": daily_mean(blh).ravel(),
        "blh_min": daily_min(blh).ravel(),
        "t2m_c": daily_mean(t2m).ravel(),
        "rh_pct": daily_mean(rh).ravel(),
        "u10": daily_mean(u10).ravel(),
        "v10": daily_mean(v10).ravel(),
        "wspd10": daily_mean(wspd10).ravel(),
        "precip_mm": (daily_mean(tp) * 24.0 * 1000.0).ravel(),
        "u925": daily_mean(u925).ravel(),
        "v925": daily_mean(v925).ravel(),
        "wspd925": daily_mean(wspd925).ravel(),
        "u850": daily_mean(u850).ravel(),
        "v850": daily_mean(v850).ravel(),
        "wspd850": daily_mean(wspd850).ravel(),
    })
    era5_parts.append(yr_df)
    print(f"  {yr}: {len(yr_df):,} station-days ({time.time() - t_yr:.1f}s)")

era5_daily = pd.concat(era5_parts, ignore_index=True)
df = df.merge(era5_daily, on=["location_id", "date"], how="inner")

# 3. Calendar features
print("[3/4] Adding calendar features...")
doy = df["date"].dt.dayofyear.values
df["doy_sin"] = np.sin(2.0 * np.pi * doy / 365.25).astype(np.float32)
df["doy_cos"] = np.cos(2.0 * np.pi * doy / 365.25).astype(np.float32)
df["day_of_week"] = df["date"].dt.dayofweek.astype(np.int8)
df["is_weekend"] = (df["day_of_week"] >= 5).astype(np.int8)

# 4. Local EDGAR v8.1 monthly emissions (2023 mapped to 2022)
print("[4/4] Extracting local EDGAR v8.1 monthly emissions...")
ALL_SECTORS = [
    "bkl_AGRICULTURE", "bkl_BUILDINGS", "bkl_FUEL_EXPLOITATION", "bkl_IND_COMBUSTION",
    "bkl_IND_PROCESSES", "bkl_POWER_INDUSTRY", "bkl_TRANSPORT", "bkl_WASTE",
]
KEY_PM25 = {
    "bkl_AGRICULTURE": "edgar_pm25_agriculture",
    "bkl_BUILDINGS": "edgar_pm25_buildings",
    "bkl_IND_COMBUSTION": "edgar_pm25_ind_combustion",
    "bkl_POWER_INDUSTRY": "edgar_pm25_power_industry",
    "bkl_TRANSPORT": "edgar_pm25_transport",
    "bkl_WASTE": "edgar_pm25_waste",
}
SPECIES_TOTALS = {
    "PM2.5": "edgar_pm25_total",
    "BC": "edgar_bc_total",
    "CO": "edgar_co_total",
    "NH3": "edgar_nh3_total",
    "NOx": "edgar_nox_total",
    "SO2": "edgar_so2_total",
}

df["edgar_year"] = np.minimum(df["year"].values, 2022)

# Read grid coordinates once
sample_nc = "edgar_v81/monthly/PM2.5/bkl_AGRICULTURE/v8.1_FT2022_AP_PM2.5_2022_bkl_AGRICULTURE_emi.nc"
with xr.open_dataset(sample_nc) as ds0:
    sub0 = ds0[list(ds0.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100))
    e_lats = sub0["lat"].values.astype(np.float64)
    e_lons = sub0["lon"].values.astype(np.float64)

st_eli = np.clip(np.rint((st_lats - e_lats[0]) / (e_lats[1] - e_lats[0])).astype(int), 0, len(e_lats) - 1)
st_elo = np.clip(np.rint((st_lons - e_lons[0]) / (e_lons[1] - e_lons[0])).astype(int), 0, len(e_lons) - 1)

edgar_rows = []
for eyr in [2019, 2020, 2021, 2022]:
    yr_cols = {
        "edgar_year": np.full(12 * len(stations), eyr, dtype=np.int16),
        "month": np.repeat(np.arange(1, 13, dtype=np.int8), len(stations)),
        "location_id": np.tile(st_ids, 12),
    }
    for sp, tot_col in SPECIES_TOTALS.items():
        tot_acc = np.zeros((12, len(stations)), dtype=np.float32)
        for sec in ALL_SECTORS:
            path = f"edgar_v81/monthly/{sp}/{sec}/v8.1_FT2022_AP_{sp}_{eyr}_{sec}_emi.nc"
            with xr.open_dataset(path) as ds:
                da = ds[list(ds.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100)).values
                vals = np.nan_to_num(da[:, st_eli, st_elo], nan=0.0).astype(np.float32)
            tot_acc += vals
            if sp == "PM2.5" and sec in KEY_PM25:
                yr_cols[KEY_PM25[sec]] = vals.ravel()
        yr_cols[tot_col] = tot_acc.ravel()
    edgar_rows.append(pd.DataFrame(yr_cols))
    print(f"  EDGAR {eyr} extracted")

edgar_df = pd.concat(edgar_rows, ignore_index=True)
df = df.merge(edgar_df, on=["location_id", "edgar_year", "month"], how="left").drop(columns=["edgar_year"])

df.to_parquet(OUT_PATH, index=False)
print(f"\nSaved -> {OUT_PATH}")
print(f"Shape: {df.shape} | Stations: {df['location_id'].nunique()} | Elapsed: {time.time() - t0:.1f}s")
print("Null check on feature columns:", int(df.drop(columns=["pm25_lag1", "pm25_lag2"]).isna().sum().sum()))
