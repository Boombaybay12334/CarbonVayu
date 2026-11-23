import glob
import os
import pandas as pd
import xarray as xr

print("=" * 60)
print("CARBONVAYU MLv2 — DATA AUDIT")
print("=" * 60)

# 1. EDGAR v8.1 Emissions
edgar_files = glob.glob("edgar/**/*.nc", recursive=True)
print(f"\n[1] EDGAR NetCDF files: {len(edgar_files)}")
if edgar_files:
    names = [os.path.basename(f) for f in edgar_files]
    sectors = sorted({n.split("_")[2] for n in names if len(n.split("_")) > 3})
    print(f"    Sample file: {names[0]}")
    print(f"    Detected tokens/sectors (check for AWB): {sectors[:20]}")
    with xr.open_dataset(edgar_files[0]) as ds:
        print(f"    Vars: {list(ds.data_vars)} | Dims: {dict(ds.sizes)}")

# 2. GADM Boundaries
gadm_files = sorted(glob.glob("gadm/*.gpkg"))
print(f"\n[2] GADM GeoPackages: {len(gadm_files)}")
for f in gadm_files:
    print(f"    - {os.path.basename(f)} ({os.path.getsize(f)/1e6:.1f} MB)")

# 3. FSI Forest Carbon Stock
fsi_path = "fsi_isfr/state_carbon_stock_2017_2023.csv"
print(f"\n[3] FSI Carbon Stock CSV:")
if os.path.exists(fsi_path):
    fsi = pd.read_csv(fsi_path)
    print(f"    Rows: {len(fsi)} | Years: {sorted(fsi['year'].unique().tolist())}")
    print(f"    National totals (Mt C):")
    for yr, tot in (fsi.groupby("year")["total_carbon_kt"].sum() / 1000).items():
        print(f"      {yr}: {tot:,.2f} Mt")
else:
    print(f"    MISSING -> {fsi_path}")

# 4. ERA5 Winds & Weather
print(f"\n[4] ERA5 NetCDF files:")
for sub in ["era5/winds_pl", "era5/weather_sl"]:
    files = sorted(glob.glob(f"{sub}/*.nc"))
    print(f"    {sub}/ ({len(files)} files):")
    for f in files:
        with xr.open_dataset(f) as ds:
            t_col = "valid_time" if "valid_time" in ds.coords else "time"
            t_vals = pd.to_datetime(ds[t_col].values)
            print(
                f"      - {os.path.basename(f)} ({os.path.getsize(f)/1e6:.1f} MB) | "
                f"steps={len(t_vals)} ({t_vals.min().date()} -> {t_vals.max().date()}) | "
                f"vars={list(ds.data_vars)}"
            )

# 5. OpenAQ / CPCB Ground Stations
print(f"\n[5] OpenAQ Ground Stations:")
st_path = "openaq/stations_india.csv"
if os.path.exists(st_path):
    st = pd.read_csv(st_path)
    print(f"    Metadata: {len(st)} stations ({st['has_pm25'].sum()} with PM2.5)")
for yr in [2021, 2022]:
    raw_files = glob.glob(f"openaq/raw/{yr}/*.csv.gz")
    total_mb = sum(os.path.getsize(f) for f in raw_files) / 1e6
    print(f"    openaq/raw/{yr}/: {len(raw_files)} station files ({total_mb:.1f} MB)")
    if raw_files:
        sample = pd.read_csv(raw_files[0], compression="gzip", nrows=5)
        print(f"      Sample cols: {list(sample.columns)}")

print("\n" + "=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
