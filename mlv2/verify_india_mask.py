import glob
import geopandas as gpd
import pandas as pd
import xarray as xr
import rioxarray  # registers .rio accessor

YEAR = 2022
SPECIES = ["PM2.5", "NOx", "SO2", "NH3", "CO", "BC"]
NEIGHBOURS = ["PAK", "NPL", "BGD", "BTN", "MMR", "LKA"]

# 1. Verify GADM files
india_states = gpd.read_file("gadm/gadm41_IND.gpkg", layer="ADM_ADM_1")
print(f"India ADM_1 loaded: {len(india_states)} states/UTs")

for iso in NEIGHBOURS:
    gdf = gpd.read_file(f"gadm/gadm41_{iso}.gpkg", layer="ADM_ADM_0")
    print(f"Neighbour {iso} ADM_0 loaded: {len(gdf)} feature(s)")

india_geom = [india_states.geometry.union_all()]

# 2. Load India 2022 Excel reference totals
def get_india_xls_total(species):
    patterns = [
        f"edgar_v81/totals/**/EDGAR_{species}_*.xlsx",
        f"edgar_v81/totals/**/EDGAR_{species.replace('.', '')}_*.xlsx",
    ]
    files = next((glob.glob(p, recursive=True) for p in patterns if glob.glob(p, recursive=True)), [])
    xl = pd.ExcelFile(files[0])
    sheet = next((s for s in xl.sheet_names if "TOTAL" in s.upper()), xl.sheet_names[-1])
    raw = pd.read_excel(files[0], sheet_name=sheet, header=None)
    hdr_idx = raw[raw.apply(lambda r: r.astype(str).str.contains("Country_code_A3").any(), axis=1)].index[0]
    df = pd.read_excel(files[0], sheet_name=sheet, header=hdr_idx)
    col = f"Y_{YEAR}" if f"Y_{YEAR}" in df.columns else YEAR
    return pd.to_numeric(df.loc[df["Country_code_A3"] == "IND", col], errors="coerce").sum()

# 3. Clip 2022 NetCDFs to India and compare
print(f"\n{'Species':<8} | {'NC India (kt)':>14} | {'XLS India (kt)':>15} | {'Diff (%)':>9}")
print("-" * 55)

for sp in SPECIES:
    nc_files = sorted(glob.glob(f"edgar_v81/monthly/{sp}/bkl_*/*_{YEAR}_*_emi.nc"))
    total_mg = 0.0

    for f in nc_files:
        with xr.open_dataset(f) as ds:
            var = list(ds.data_vars)[0]
            da = ds[var]
            # Normalize lon to [-180, 180] if needed
            if float(da.lon.max()) > 180:
                da = da.assign_coords(lon=(((da.lon + 180) % 360) - 180)).sortby("lon")
            da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat").rio.write_crs("EPSG:4326")
            clipped = da.rio.clip(india_geom, india_states.crs, drop=True)
            total_mg += float(clipped.sum().values)

    nc_ind_kt = total_mg / 1000.0
    xls_ind_kt = get_india_xls_total(sp)
    diff_pct = ((nc_ind_kt - xls_ind_kt) / xls_ind_kt) * 100.0
    print(f"{sp:<8} | {nc_ind_kt:>14.2f} | {xls_ind_kt:>15.2f} | {diff_pct:>+8.2f}%")
