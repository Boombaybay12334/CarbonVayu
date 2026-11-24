import glob
import os
import pandas as pd
import xarray as xr

YEAR = 2022
SPECIES = ["PM2.5", "NOx", "SO2", "NH3", "CO", "BC"]

def load_edgar_excel(species):
    # Search recursively inside edgar_v81/totals/ for matching .xlsx or .xls
    patterns = [
        f"edgar_v81/totals/**/EDGAR_{species}_*.xlsx",
        f"edgar_v81/totals/**/EDGAR_{species.replace('.', '')}_*.xlsx",
        f"edgar_v81/totals/**/EDGAR_{species}_*.xls",
    ]
    files = []
    for p in patterns:
        files = glob.glob(p, recursive=True)
        if files:
            break
    if not files:
        raise FileNotFoundError(f"No Excel file found for {species} in edgar_v81/totals/")

    path = files[0]
    xl = pd.ExcelFile(path)
    sheet = next((s for s in xl.sheet_names if "TOTAL" in s.upper()), xl.sheet_names[-1])
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr_idx = raw[raw.apply(lambda r: r.astype(str).str.contains("Country_code_A3").any(), axis=1)].index[0]
    df = pd.read_excel(path, sheet_name=sheet, header=hdr_idx)
    return df

print(f"{'Species':<8} | {'NC Units':<15} | {'NC Global (kt)':>15} | {'XLS Global (kt)':>16} | {'India 2022 (kt)':>16}")
print("-" * 82)

for sp in SPECIES:
    nc_files = sorted(glob.glob(f"edgar_v81/monthly/{sp}/bkl_*/*_{YEAR}_*_emi.nc"))
    total_mg = 0.0
    units = "?"

    for f in nc_files:
        with xr.open_dataset(f) as ds:
            var = list(ds.data_vars)[0]
            units = ds[var].attrs.get("units", "unknown")
            total_mg += float(ds[var].sum().values)

    nc_global_kt = total_mg / 1000.0  # Mg -> kt

    df = load_edgar_excel(sp)
    col = f"Y_{YEAR}" if f"Y_{YEAR}" in df.columns else YEAR
    xls_global_kt = pd.to_numeric(df[col], errors="coerce").sum()
    india_kt = pd.to_numeric(df.loc[df["Country_code_A3"] == "IND", col], errors="coerce").sum()

    print(f"{sp:<8} | {units:<15} | {nc_global_kt:>15.2f} | {xls_global_kt:>16.2f} | {india_kt:>16.2f}")
