import glob
import os
import numpy as np
import pandas as pd
import xarray as xr

# 1. Merge OpenAQ + ERA5 (inner join drops the 44 stations without coordinates)
print("Loading OpenAQ and ERA5 daily tables...")
openaq = pd.read_parquet("data/openaq_daily_2021_2022.parquet")
era5 = pd.read_parquet("data/era5_daily_2021_2022.parquet")

df = openaq.merge(era5, on=["location_id", "date"], how="inner")
df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month
print(f"Merged OpenAQ + ERA5 rows: {len(df):,} ({df['location_id'].nunique()} stations)")

# 2. Helper to load EDGAR v8.1 monthly grid cropped to India box [0..40N, 60..100E]
SPECIES = ["PM2.5", "BC", "CO", "NH3", "NOx", "SO2"]
SECTORS = [
    "bkl_AGRICULTURE", "bkl_BUILDINGS", "bkl_FUEL_EXPLOITATION",
    "bkl_IND_COMBUSTION", "bkl_IND_PROCESSES", "bkl_POWER_INDUSTRY",
    "bkl_TRANSPORT", "bkl_WASTE",
]
KEY_PM25_SECTORS = [
    "bkl_AGRICULTURE", "bkl_BUILDINGS", "bkl_TRANSPORT",
    "bkl_POWER_INDUSTRY", "bkl_IND_COMBUSTION", "bkl_WASTE",
]

def load_edgar_array(species, sector, year):
    path = f"edgar_v81/monthly/{species}/{sector}/v8.1_FT2022_AP_{species}_{year}_{sector}_emi.nc"
    with xr.open_dataset(path) as ds:
        var = list(ds.data_vars)[0]
        da = ds[var].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100)).load()
        # Ensure time axis is integer month 1..12
        da = da.assign_coords(time=np.arange(1, da.sizes["time"] + 1))
        return da

def sample_grid(da, months, lats, lons):
    # Vectorized nearest-neighbor lookup on (month, lat, lon)
    m_da = xr.DataArray(months, dims="obs")
    lat_da = xr.DataArray(np.clip(lats, 0.05, 39.95), dims="obs")
    lon_da = xr.DataArray(np.clip(lons, 60.05, 99.95), dims="obs")
    return da.sel(time=m_da, lat=lat_da, lon=lon_da, method="nearest").values

# Precompute upwind coordinates (100 km and 250 km upwind along 925 hPa wind)
spd = np.hypot(df["u925"].values, df["v925"].values)
ux = np.where(spd > 0.5, -df["u925"].values / np.maximum(spd, 1e-6), 0.0)
uy = np.where(spd > 0.5, -df["v925"].values / np.maximum(spd, 1e-6), 0.0)
cos_lat = np.cos(np.deg2rad(df["lat"].values))

upwind_coords = {}
for dist_km in [100, 250]:
    up_lat = df["lat"].values + (dist_km / 111.0) * uy
    up_lon = df["lon"].values + (dist_km / (111.0 * np.maximum(cos_lat, 0.1))) * ux
    upwind_coords[dist_km] = (up_lat, up_lon)

# 3. Extract EDGAR features year-by-year
print("\nExtracting EDGAR v8.1 local + upwind emissions...")
for yr in [2021, 2022]:
    mask = (df["year"] == yr).values
    m_vals = df.loc[mask, "month"].values
    lat_vals = df.loc[mask, "lat"].values
    lon_vals = df.loc[mask, "lon"].values

    for sp in SPECIES:
        total_da = None
        for sec in SECTORS:
            da = load_edgar_array(sp, sec, yr)
            total_da = da if total_da is None else (total_da + da)

            # Keep sectoral breakdown for PM2.5
            if sp == "PM2.5" and sec in KEY_PM25_SECTORS:
                short_sec = sec.replace("bkl_", "").lower()
                df.loc[mask, f"edgar_pm25_{short_sec}"] = sample_grid(da, m_vals, lat_vals, lon_vals)
                if sec == "bkl_AGRICULTURE":
                    for dist_km in [100, 250]:
                        ulat, ulon = upwind_coords[dist_km]
                        df.loc[mask, f"edgar_pm25_agri_up{dist_km}km"] = sample_grid(
                            da, m_vals, ulat[mask], ulon[mask]
                        )

        sp_clean = sp.lower().replace(".", "")
        df.loc[mask, f"edgar_{sp_clean}_total"] = sample_grid(total_da, m_vals, lat_vals, lon_vals)

        # Upwind totals for PM2.5 and BC
        if sp in ["PM2.5", "BC"]:
            for dist_km in [100, 250]:
                ulat, ulon = upwind_coords[dist_km]
                df.loc[mask, f"edgar_{sp_clean}_up{dist_km}km"] = sample_grid(
                    total_da, m_vals, ulat[mask], ulon[mask]
                )
    print(f"    Finished EDGAR {yr}")

# 4. Merge FSI Forest Carbon Stock (interpolate 2022 between 2021 & 2023)
print("\nMerging FSI forest carbon stock...")
fsi = pd.read_csv("fsi_isfr/state_carbon_stock_2017_2023.csv")

# Normalize state names to match GADM NAME_1
STATE_MAP = {
    "delhi": "nct of delhi",
    "odisha": "odisha",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "jammu & kashmir": "jammu and kashmir",
    "andaman & nicobar islands": "andaman and nicobar",
    "dadra & nagar haveli": "dadra and nagar haveli and daman and diu",
    "daman & diu": "dadra and nagar haveli and daman and diu",
}

def norm_state(s):
    s = str(s).strip().lower()
    return STATE_MAP.get(s, s)

fsi["state_key"] = fsi["state"].apply(norm_state)
fsi_num_cols = [c for c in fsi.columns if c not in ["state", "state_key", "year"]]
fsi_agg = fsi.groupby(["state_key", "year"], as_index=False)[fsi_num_cols].sum()

# Build 2021 and interpolated 2022 table
f21 = fsi_agg[fsi_agg["year"] == 2021].set_index("state_key")[fsi_num_cols]
f23 = fsi_agg[fsi_agg["year"] == 2023].set_index("state_key")[fsi_num_cols]
f22 = ((f21 + f23) / 2.0).reset_index()
f22["year"] = 2022
f21 = f21.reset_index()
f21["year"] = 2021
fsi_21_22 = pd.concat([f21, f22], ignore_index=True)

df["state_key"] = df["state"].apply(norm_state)
df = df.merge(fsi_21_22, on=["state_key", "year"], how="left").drop(columns=["state_key"])

# 5. Calendar seasonality features
doy = df["date"].dt.dayofyear
df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
df["day_of_week"] = df["date"].dt.dayofweek
df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

out_path = "data/features_daily_2021_2022.parquet"
df.to_parquet(out_path, index=False)

print(f"\nSaved -> {out_path}")
print(f"Final shape: {df.shape}")
print(f"Columns ({len(df.columns)}):\n  {list(df.columns)}")
print("\nTop 5 columns with most NaNs:")
print(df.isna().sum().sort_values(ascending=False).head(5).to_string())
