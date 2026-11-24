"""
dl_era5_mirror_test.py -- Benchmark pulling 1 full year (2019) from Earthmover Icechunk ERA5
Writes ONLY to era5_mirror_test/ in the same layout as CDS NetCDFs.
"""
from pathlib import Path
import time
import icechunk as ic
import xarray as xr

YEAR = 2019
OUT_BASE = Path("era5_mirror_test")
WINDS_DIR = OUT_BASE / "winds_pl"
SL_DIR = OUT_BASE / "weather_sl" / str(YEAR)
WINDS_DIR.mkdir(parents=True, exist_ok=True)
SL_DIR.mkdir(parents=True, exist_ok=True)


def open_session():
    storage = ic.s3_storage(
        bucket="earthmover-icechunk-era5",
        prefix="icechunkV2",
        region="us-east-1",
        anonymous=True,
    )
    return ic.Repository.open(storage=storage).readonly_session("main")


def slice_india_6h(ds, year: int):
    # Handle descending (90..-90) or ascending (-90..90) latitude
    lat_vals = ds["latitude"].values
    lat_slice = slice(40.0, 0.0) if lat_vals[0] > lat_vals[-1] else slice(0.0, 40.0)
    sub = ds.sel(
        valid_time=slice(f"{year}-01-01", f"{year}-12-31T23:59:59"),
        latitude=lat_slice,
        longitude=slice(60.0, 100.0),
    )
    # Match CDS 6-hourly steps: 00:00, 06:00, 12:00, 18:00
    sub = sub.sel(valid_time=sub["valid_time"].dt.hour.isin([0, 6, 12, 18]))
    return sub


def main():
    t0 = time.time()
    session = open_session()

    # 1. Pressure-level winds (850 & 925 hPa)
    print(f"[1/2] Downloading pressure-level winds ({YEAR}, 850 & 925 hPa)...")
    t1 = time.time()
    ds_pl = xr.open_dataset(session.store, group="pressure/temporal", engine="zarr", consolidated=False)
    winds = slice_india_6h(ds_pl[["u", "v"]].sel(pressure_level=[850.0, 925.0]), YEAR).load()
    winds_path = WINDS_DIR / f"era5_winds_{YEAR}.nc"
    winds.to_netcdf(winds_path)
    print(f"  [done] {winds_path} ({winds_path.stat().st_size / 1e6:.1f} MB) in {time.time() - t1:.1f}s")

    # 2. Single-level weather (split into instant + accum to match CDS zip layout)
    print(f"[2/2] Downloading single-level weather ({YEAR})...")
    t2 = time.time()
    ds_sl = xr.open_dataset(session.store, group="single/temporal", engine="zarr", consolidated=False)
    sl_inst = slice_india_6h(ds_sl[["u10", "v10", "t2m", "d2m", "blh"]], YEAR).load()
    sl_acc = slice_india_6h(ds_sl[["tp"]], YEAR).load()

    inst_path = SL_DIR / "data_stream-oper_stepType-instant.nc"
    acc_path = SL_DIR / "data_stream-oper_stepType-accum.nc"
    sl_inst.to_netcdf(inst_path)
    sl_acc.to_netcdf(acc_path)
    print(
        f"  [done] instant ({inst_path.stat().st_size / 1e6:.1f} MB) + "
        f"accum ({acc_path.stat().st_size / 1e6:.1f} MB) in {time.time() - t2:.1f}s"
    )
    print(f"\nTotal elapsed for {YEAR}: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
