"""
era5_mirror_test.py -- Quick sandbox probe for Earthmover Icechunk ERA5
Writes only to era5_mirror_test/ without touching era5/ or data/.
"""
from pathlib import Path
import icechunk as ic
import xarray as xr

OUT_DIR = Path("era5_mirror_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def inspect_store(store):
    for grp in [None, "single_level", "pressure_levels", "hourly"]:
        try:
            ds = xr.open_dataset(store, group=grp, engine="zarr", consolidated=False)
            if len(ds.data_vars) > 0 or len(ds.coords) > 0:
                print(f"\n[group={grp}] dims={dict(ds.sizes)} coords={list(ds.coords)}")
                print(f"  vars={list(ds.data_vars)}")
                for c in ds.coords:
                    if "level" in c.lower() or "pressure" in c.lower():
                        print(f"  {c}: {ds[c].values[:30]}")
                return grp, ds
        except Exception as e:
            print(f"[group={grp}] {type(e).__name__}: {e}")
    return None, None


def main():
    print("Opening bucket='earthmover-icechunk-era5', prefix='icechunkV2'...")
    storage = ic.s3_storage(
        bucket="earthmover-icechunk-era5",
        prefix="icechunkV2",
        region="us-east-1",
        anonymous=True,
    )
    repo = ic.Repository.open(storage=storage)
    session = repo.readonly_session("main")

    grp, ds = inspect_store(session.store)
    if ds is None:
        print("Could not find variables under root or common groups.")
        return

    lat_col = "latitude" if "latitude" in ds.coords else "lat"
    lon_col = "longitude" if "longitude" in ds.coords else "lon"
    t_col = "valid_time" if "valid_time" in ds.coords else "time"

    lat_vals = ds[lat_col].values
    lat_slice = slice(40, 0) if lat_vals[0] > lat_vals[-1] else slice(0, 40)

    sub = ds.sel({lat_col: lat_slice, lon_col: slice(60, 100), t_col: slice("2023-01-01", "2023-01-02")})
    first_var = list(sub.data_vars)[0]
    probe_path = OUT_DIR / f"probe_{first_var}_2023_01_01.nc"
    sub[[first_var]].to_netcdf(probe_path)
    print(f"\nSaved 1-day probe ({first_var}) -> {probe_path} ({probe_path.stat().st_size / 1e3:.1f} KB)")


if __name__ == "__main__":
    main()
