import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  # activates the .rio accessor
import xarray as xr


START_YEAR = 2015
END_YEAR = 2022

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

EDGAR_SPLIT_DIR = os.path.join("data", "edgar", "split")
SHAPEFILE_PATH = os.path.join("data", "gadm", "gadm41_IND_1.shp")
OUTPUT_DIR = os.path.join("data", "output")


def resolve_shapefile_path():
    candidates = [
        os.path.join(SCRIPT_DIR, SHAPEFILE_PATH),
        os.path.join(SCRIPT_DIR, "gadm41_IND_1.shp"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Shapefile not found. Checked: " + ", ".join(candidates)
    )


def validate_shapefile_components(shp_path):
    base, _ = os.path.splitext(shp_path)
    required = [shp_path, base + ".shx", base + ".dbf"]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            "Incomplete shapefile. Missing: "
            + ", ".join(missing)
            + ". Keep .shp/.shx/.dbf together with the same basename."
        )


def list_nc_candidates_for_year(year):
    candidate_dirs = [
        os.path.join(SCRIPT_DIR, EDGAR_SPLIT_DIR),
        SCRIPT_DIR,
    ]

    candidates = []
    for folder in candidate_dirs:
        if not os.path.isdir(folder):
            continue

        direct_name = os.path.join(folder, f"ghg_{year}.nc")
        if os.path.exists(direct_name):
            candidates.append(direct_name)

        for fname in os.listdir(folder):
            lower = fname.lower()
            if not lower.endswith(".nc"):
                continue

            year_key_1 = f"ghg_{year}.nc"
            year_key_2 = f"ghg_{year}_"
            if (lower != year_key_1) and (year_key_2 not in lower):
                continue

            full_path = os.path.join(folder, fname)
            if full_path not in candidates:
                candidates.append(full_path)

    return candidates


def choose_nc_file_for_year(year):
    candidates = list_nc_candidates_for_year(year)
    if not candidates:
        return None

    for path in candidates:
        if os.path.basename(path).lower() == f"ghg_{year}.nc":
            return path

    for path in candidates:
        if "totals" in os.path.basename(path).lower() and "emi" in os.path.basename(path).lower():
            return path

    return candidates[0]


def detect_main_variable(ds):
    if not ds.data_vars:
        raise ValueError("No data variables found in NetCDF dataset.")

    token_pref = ["emi", "emission", "ghg", "total", "tot", "co2"]
    scored = []

    for var_name, da in ds.data_vars.items():
        if not np.issubdtype(da.dtype, np.number):
            continue

        dims_lower = [d.lower() for d in da.dims]
        has_lat = any(("lat" in d) or (d == "y") for d in dims_lower)
        has_lon = any(("lon" in d) or (d == "x") for d in dims_lower)
        has_space = has_lat and has_lon

        token_score = 0
        lname = var_name.lower()
        for token in token_pref:
            if token in lname:
                token_score += 1

        score = (
            int(has_space) * 100
            + token_score * 10
            + len(da.dims)
            + int(da.size > 0)
        )
        scored.append((score, int(da.size), var_name))

    if not scored:
        raise ValueError("No numeric variable available for emissions processing.")

    scored.sort(reverse=True)
    return scored[0][2]


def detect_lat_lon_dims(da):
    lat_dim = None
    lon_dim = None

    for d in da.dims:
        ld = d.lower()
        if lat_dim is None and (("lat" in ld) or ld == "y"):
            lat_dim = d
        if lon_dim is None and (("lon" in ld) or ld == "x"):
            lon_dim = d

    if lat_dim is None or lon_dim is None:
        raise ValueError(f"Could not detect lat/lon dimensions in {list(da.dims)}")

    return lat_dim, lon_dim


def prepare_grid_for_clip(da):
    lat_dim, lon_dim = detect_lat_lon_dims(da)

    non_spatial = [d for d in da.dims if d not in [lat_dim, lon_dim]]
    if non_spatial:
        da = da.sum(dim=non_spatial, skipna=True)

    da = da.rio.set_spatial_dims(x_dim=lon_dim, y_dim=lat_dim, inplace=False)

    if da.rio.crs is None:
        da = da.rio.write_crs("EPSG:4326", inplace=False)
    elif str(da.rio.crs).upper() != "EPSG:4326":
        da = da.rio.reproject("EPSG:4326")

    return da


def detect_state_column(gdf):
    exact = [
        "NAME_1",
        "NAME1",
        "STATE",
        "state",
        "ST_NM",
        "ADM1_NAME",
        "NAME",
    ]
    for c in exact:
        if c in gdf.columns:
            return c

    object_cols = [c for c in gdf.columns if c != "geometry" and gdf[c].dtype == object]

    for c in object_cols:
        u = c.upper()
        if ("STATE" in u) or ("NAME_1" in u) or ("ADM1" in u):
            return c

    if object_cols:
        ranked = sorted(
            object_cols,
            key=lambda c: int(gdf[c].nunique(dropna=True)),
            reverse=True,
        )
        return ranked[0]

    raise ValueError(
        "No state-name column found in shapefile attributes. "
        "Confirm the .dbf file is correct."
    )


def normalize_state_name(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def is_excluded_state(state_name):
    s = normalize_state_name(state_name).lower().replace("&", "and")
    return (("andaman" in s) and ("nicobar" in s)) or ("lakshadweep" in s)


def load_states_geodataframe():
    shp_path = resolve_shapefile_path()
    validate_shapefile_components(shp_path)

    print(f"Using shapefile: {shp_path}")

    os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")
    gdf = gpd.read_file(shp_path)

    if gdf.crs is None:
        print("Shapefile CRS missing. Assuming EPSG:4326.")
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    else:
        gdf = gdf.to_crs("EPSG:4326")

    state_col = detect_state_column(gdf)
    gdf[state_col] = gdf[state_col].apply(normalize_state_name)

    gdf = gdf[~gdf[state_col].apply(is_excluded_state)].copy()

    # One geometry per state to avoid duplicate state rows.
    gdf = gdf[[state_col, "geometry"]].dissolve(by=state_col, as_index=False)
    gdf = gdf.rename(columns={state_col: "state"})
    gdf = gdf.sort_values("state").reset_index(drop=True)

    return gdf


def process_year(year, states_gdf, output_dir_abs):
    in_file = choose_nc_file_for_year(year)
    out_file = os.path.join(output_dir_abs, f"state_emissions_{year}.csv")

    if in_file is None:
        print(f"Processing year {year}: file not found, skipping.")
        return None

    print(f"Processing year {year}: {in_file}")

    ds = xr.open_dataset(in_file)
    try:
        var_name = detect_main_variable(ds)
        print(f"Detected variable for {year}: {var_name}")

        da = prepare_grid_for_clip(ds[var_name])

        records = []
        for row in states_gdf.itertuples(index=False):
            state_name = row.state
            try:
                clipped = da.rio.clip([row.geometry], states_gdf.crs, drop=True)
                total = float(clipped.sum(skipna=True).values)
                if np.isnan(total):
                    total = 0.0
            except Exception as exc:
                print(f"Clip failed for {state_name} in {year}: {exc}. Assigning 0.")
                total = 0.0

            records.append(
                {
                    "state": state_name,
                    "total_emission_mt": total / 1e9,
                }
            )

        year_df = pd.DataFrame(records)
        year_df = (
            year_df.groupby("state", as_index=False, dropna=False)["total_emission_mt"]
            .sum()
        )
        year_df.to_csv(out_file, index=False)
        print(f"Saved: {out_file}")

        return year_df
    finally:
        ds.close()


def main():
    output_dir_abs = os.path.join(SCRIPT_DIR, OUTPUT_DIR)
    os.makedirs(output_dir_abs, exist_ok=True)

    states_gdf = load_states_geodataframe()

    panel_parts = []
    for year in range(START_YEAR, END_YEAR + 1):
        year_df = process_year(year, states_gdf, output_dir_abs)
        if year_df is not None:
            year_df["year"] = year
            panel_parts.append(year_df[["state", "year", "total_emission_mt"]])

    panel_path = os.path.join(output_dir_abs, "state_emissions_panel_2015_2022.csv")

    if not panel_parts:
        print("No yearly outputs were generated. Panel CSV not created.")
        return

    panel_df = pd.concat(panel_parts, ignore_index=True)
    panel_df = panel_df.sort_values(["state", "year"]).reset_index(drop=True)
    panel_df.to_csv(panel_path, index=False)
    print(f"Saved: {panel_path}")


if __name__ == "__main__":
    main()
