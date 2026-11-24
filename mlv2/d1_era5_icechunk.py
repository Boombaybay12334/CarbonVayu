"""
dl_era5_icechunk.py -- Finish missing ERA5 2019/2020/2023 files via Earthmover Icechunk.
Skips any files already downloaded by CDS, promotes 2019 single-level from era5_mirror_test/,
and downloads only the remaining files with zlib compression.
"""
from pathlib import Path
import shutil
import time
import icechunk as ic
import xarray as xr

YEARS_TO_CHECK = [2019, 2020, 2023]
ERA5_BASE = Path("era5")
MIRROR_TEST = Path("era5_mirror_test")


def compressed_encoding(ds):
    return {v: {"zlib": True, "complevel": 4, "dtype": "float32"} for v in ds.data_vars}


def promote_2019_sl():
    sl_src = MIRROR_TEST / "weather_sl" / "2019"
    sl_dst = ERA5_BASE / "weather_sl" / "2019"
    sl_dst.mkdir(parents=True, exist_ok=True)
    for fname in ["data_stream-oper_stepType-instant.nc", "data_stream-oper_stepType-accum.nc"]:
        src, dst = sl_src / fname, sl_dst / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"[2019] Copied {dst} ({dst.stat().st_size / 1e6:.1f} MB)")


def open_session():
    storage = ic.s3_storage(
        bucket="earthmover-icechunk-era5",
        prefix="icechunkV2",
        region="us-east-1",
        anonymous=True,
    )
    return ic.Repository.open(storage=storage).readonly_session("main")


def slice_india_6h(ds, year: int):
    lat_vals = ds["latitude"].values
    lat_slice = slice(40.0, 0.0) if lat_vals[0] > lat_vals[-1] else slice(0.0, 40.0)
    sub = ds.sel(
        valid_time=slice(f"{year}-01-01", f"{year}-12-31T23:59:59"),
        latitude=lat_slice,
        longitude=slice(60.0, 100.0),
    )
    return sub.sel(valid_time=sub["valid_time"].dt.hour.isin([0, 6, 12, 18]))


def main():
    t_all = time.time()
    promote_2019_sl()

    session = open_session()
    ds_pl = xr.open_dataset(session.store, group="pressure/temporal", engine="zarr", consolidated=False)
    ds_sl = xr.open_dataset(session.store, group="single/temporal", engine="zarr", consolidated=False)

    for year in YEARS_TO_CHECK:
        print(f"\n=== Year {year} ===")

        # 1. Pressure-level winds ([925.0, 850.0] to match CDS)
        w_path = ERA5_BASE / "winds_pl" / f"era5_winds_{year}.nc"
        w_path.parent.mkdir(parents=True, exist_ok=True)
        if not w_path.exists():
            t1 = time.time()
            print(f"  [dl] {w_path}...")
            winds = slice_india_6h(ds_pl[["u", "v"]].sel(pressure_level=[925.0, 850.0]), year).load()
            winds.to_netcdf(w_path, encoding=compressed_encoding(winds))
            print(f"  [done] {w_path} ({w_path.stat().st_size / 1e6:.1f} MB) in {time.time() - t1:.1f}s")
        else:
            print(f"  [skip] {w_path} already exists")

        # 2. Single-level weather (instant + accum)
        sl_dir = ERA5_BASE / "weather_sl" / str(year)
        sl_dir.mkdir(parents=True, exist_ok=True)
        inst_path = sl_dir / "data_stream-oper_stepType-instant.nc"
        acc_path = sl_dir / "data_stream-oper_stepType-accum.nc"

        if not inst_path.exists():
            t2 = time.time()
            print(f"  [dl] {inst_path}...")
            sl_inst = slice_india_6h(ds_sl[["u10", "v10", "t2m", "d2m", "blh"]], year).load()
            sl_inst.to_netcdf(inst_path, encoding=compressed_encoding(sl_inst))
            print(f"  [done] {inst_path} ({inst_path.stat().st_size / 1e6:.1f} MB) in {time.time() - t2:.1f}s")
        else:
            print(f"  [skip] {inst_path} already exists")

        if not acc_path.exists():
            t3 = time.time()
            print(f"  [dl] {acc_path}...")
            sl_acc = slice_india_6h(ds_sl[["tp"]], year).load()
            sl_acc.to_netcdf(acc_path, encoding=compressed_encoding(sl_acc))
            print(f"  [done] {acc_path} ({acc_path.stat().st_size / 1e6:.1f} MB) in {time.time() - t3:.1f}s")
        else:
            print(f"  [skip] {acc_path} already exists")

    print(f"\nAll done in {time.time() - t_all:.1f}s! Final 5-year inventory check:")
    for y in range(2019, 2024):
        w = (ERA5_BASE / "winds_pl" / f"era5_winds_{y}.nc").exists()
        i = (ERA5_BASE / "weather_sl" / str(y) / "data_stream-oper_stepType-instant.nc").exists()
        a = (ERA5_BASE / "weather_sl" / str(y) / "data_stream-oper_stepType-accum.nc").exists()
        print(f"  {y}: winds={w} | instant={i} | accum={a}")


if __name__ == "__main__":
    main()
