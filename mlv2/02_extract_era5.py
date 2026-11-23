import os
import numpy as np
import pandas as pd
import xarray as xr

# 1. Load unique station coordinates from Step 1
openaq = pd.read_parquet("data/openaq_daily_2021_2022.parquet")
stations = openaq[["location_id", "lat", "lon"]].dropna().drop_duplicates().reset_index(drop=True)
print(f"Extracting ERA5 for {len(stations)} unique stations (2021-2022)...")

loc_ids = stations["location_id"].values
st_lats = xr.DataArray(stations["lat"].values, dims="location_id", coords={"location_id": loc_ids})
st_lons = xr.DataArray(stations["lon"].values, dims="location_id", coords={"location_id": loc_ids})

def time_coord(ds):
    return "valid_time" if "valid_time" in ds.coords else "time"

def level_coord(ds):
    for c in ["pressure_level", "level", "isobaricInhPa"]:
        if c in ds.coords:
            return c
    raise KeyError(f"No pressure level coord found in {list(ds.coords)}")

def extract_year(year):
    print(f"\n>>> Processing ERA5 {year}...")
    inst_path = f"era5/weather_sl/{year}/data_stream-oper_stepType-instant.nc"
    acc_path = f"era5/weather_sl/{year}/data_stream-oper_stepType-accum.nc"
    pl_path = f"era5/winds_pl/era5_winds_{year}.nc"

    # A. Single-level instantaneous (blh, t2m, d2m, u10, v10)
    with xr.open_dataset(inst_path) as ds:
        tc = time_coord(ds)
        sub = ds[["blh", "t2m", "d2m", "u10", "v10"]].sel(
            latitude=st_lats, longitude=st_lons, method="nearest"
        )
        df_inst = sub.to_dataframe().reset_index()
        df_inst["date"] = pd.to_datetime(df_inst[tc]).dt.floor("D")

    df_inst["t2m_c"] = df_inst["t2m"] - 273.15
    df_inst["d2m_c"] = df_inst["d2m"] - 273.15
    # Magnus formula for relative humidity (%)
    df_inst["rh_pct"] = (
        100.0
        * np.exp((17.625 * df_inst["d2m_c"]) / (243.04 + df_inst["d2m_c"]))
        / np.exp((17.625 * df_inst["t2m_c"]) / (243.04 + df_inst["t2m_c"]))
    ).clip(0, 100)
    df_inst["wspd10"] = np.hypot(df_inst["u10"], df_inst["v10"])

    daily_inst = df_inst.groupby(["location_id", "date"], as_index=False).agg(
        blh_mean=("blh", "mean"),
        blh_min=("blh", "min"),
        t2m_c=("t2m_c", "mean"),
        rh_pct=("rh_pct", "mean"),
        u10=("u10", "mean"),
        v10=("v10", "mean"),
        wspd10=("wspd10", "mean"),
    )

    # B. Single-level accumulated (tp -> mm)
    with xr.open_dataset(acc_path) as ds:
        tc = time_coord(ds)
        sub = ds[["tp"]].sel(latitude=st_lats, longitude=st_lons, method="nearest")
        df_acc = sub.to_dataframe().reset_index()
        df_acc["date"] = pd.to_datetime(df_acc[tc]).dt.floor("D")

    df_acc["precip_mm"] = df_acc["tp"] * 1000.0
    daily_acc = df_acc.groupby(["location_id", "date"], as_index=False).agg(
        precip_mm=("precip_mm", "sum")
    )

    # C. Pressure-level winds (925 & 850 hPa)
    with xr.open_dataset(pl_path) as ds:
        tc = time_coord(ds)
        lc = level_coord(ds)
        sub = ds[["u", "v"]].sel(latitude=st_lats, longitude=st_lons, method="nearest")
        df_pl = sub.to_dataframe().reset_index()
        df_pl["date"] = pd.to_datetime(df_pl[tc]).dt.floor("D")
        df_pl["lvl"] = df_pl[lc].round().astype(int)

    pl_parts = []
    for lvl in [925, 850]:
        part = df_pl[df_pl["lvl"] == lvl].copy()
        part[f"wspd{lvl}"] = np.hypot(part["u"], part["v"])
        agg = part.groupby(["location_id", "date"], as_index=False).agg(
            **{
                f"u{lvl}": ("u", "mean"),
                f"v{lvl}": ("v", "mean"),
                f"wspd{lvl}": (f"wspd{lvl}", "mean"),
            }
        )
        pl_parts.append(agg)

    merged = (
        daily_inst
        .merge(daily_acc, on=["location_id", "date"], how="left")
        .merge(pl_parts[0], on=["location_id", "date"], how="left")
        .merge(pl_parts[1], on=["location_id", "date"], how="left")
    )
    print(f"    {year} rows: {len(merged):,}")
    return merged

era5_all = pd.concat([extract_year(2021), extract_year(2022)], ignore_index=True)

out_path = "data/era5_daily_2021_2022.parquet"
era5_all.to_parquet(out_path, index=False)

print(f"\nSaved -> {out_path}")
print(f"Shape: {era5_all.shape}")
print("Null counts:", era5_all.isna().sum().to_dict())
