import os
import re
import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

os.makedirs("data", exist_ok=True)

# 1. Read exact 0.1° EDGAR lat/lon grid inside India box [0..40N, 60..100E]
sample_edgar = "edgar_v81/monthly/PM2.5/bkl_AGRICULTURE/v8.1_FT2022_AP_PM2.5_2021_bkl_AGRICULTURE_emi.nc"
with xr.open_dataset(sample_edgar) as ds:
    da = ds[list(ds.data_vars)[0]].sortby("lat").sel(lat=slice(0, 40), lon=slice(60, 100))
    lats = da["lat"].values.astype(np.float64)
    lons = da["lon"].values.astype(np.float64)

nlat, nlon = len(lats), len(lons)
print(f"EDGAR grid: {nlat} lat x {nlon} lon = {nlat * nlon:,} cells")

# 2. Load Indian States/UTs (GADM Level 1) & group small NE states
NE_STATES = {
    "arunachal pradesh", "assam", "manipur", "meghalaya",
    "mizoram", "nagaland", "sikkim", "tripura",
}

def make_slug(name: str, prefix: str = "ind_") -> str:
    s = name.strip().lower()
    if s in NE_STATES:
        return "ind_ne_india"
    if s == "nct of delhi":
        return "ind_delhi"
    if s == "jammu and kashmir":
        return "ind_jk"
    if s == "dadra and nagar haveli and daman and diu":
        return "ind_dnh_dd"
    if s == "andaman and nicobar":
        return "ind_andaman"
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return f"{prefix}{s}"

print("Loading GADM India (ADM_ADM_1) and 6 neighbouring countries...")
ind = gpd.read_file("gadm/gadm41_IND.gpkg", layer="ADM_ADM_1")[["NAME_1", "geometry"]].copy()
ind["node"] = ind["NAME_1"].apply(make_slug)
ind = ind.dissolve(by="node", as_index=False)[["node", "geometry"]]

# 3. Load 6 neighbouring countries (GADM Level 0)
NEIGHBOURS = ["BGD", "BTN", "LKA", "MMR", "NPL", "PAK"]
ext_parts = []
for iso in NEIGHBOURS:
    path = f"gadm/gadm41_{iso}.gpkg"
    gdf = gpd.read_file(path, layer="ADM_ADM_0")[["geometry"]].copy()
    gdf["node"] = f"ext_{iso.lower()}"
    gdf = gdf.dissolve(by="node", as_index=False)[["node", "geometry"]]
    ext_parts.append(gdf)

# Put India first so border pixels default to India
polys = pd.concat([ind] + ext_parts, ignore_index=True)
polys = gpd.GeoDataFrame(polys, crs="EPSG:4326")

# 4. Spatial join all EDGAR cell centers to polygons
lon2d, lat2d = np.meshgrid(lons, lats)
pts = gpd.GeoDataFrame(
    {"flat_idx": np.arange(nlat * nlon)},
    geometry=gpd.points_from_xy(lon2d.ravel(), lat2d.ravel()),
    crs="EPSG:4326",
)

print("Running spatial join (160k cells -> nodes)...")
joined = gpd.sjoin(pts, polys, how="left", predicate="within")
joined = joined.drop_duplicates(subset=["flat_idx"], keep="first").sort_values("flat_idx")
node_labels = joined["node"].fillna("other").values

# 5. Encode as compact int16 grid
unique_nodes = sorted([n for n in np.unique(node_labels) if n != "other"]) + ["other"]
node_to_id = {name: i for i, name in enumerate(unique_nodes)}
node_grid = np.array([node_to_id[n] for n in node_labels], dtype=np.int16).reshape(nlat, nlon)

np.savez_compressed(
    "data/edgar_node_grid.npz",
    lats=lats,
    lons=lons,
    node_grid=node_grid,
    node_names=np.array(unique_nodes),
)

summary = pd.DataFrame({
    "node_id": range(len(unique_nodes)),
    "node_name": unique_nodes,
    "n_cells": [(node_grid == i).sum() for i in range(len(unique_nodes))],
})
summary.to_csv("data/node_list.csv", index=False)

print(f"\nSaved -> data/edgar_node_grid.npz & data/node_list.csv")
print(f"Total nodes: {len(unique_nodes)}")
print(summary.to_string(index=False))
