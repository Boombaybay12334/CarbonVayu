import glob
import os
import geopandas as gpd
import pandas as pd

os.makedirs("data", exist_ok=True)

# 1. Load station metadata & spatial-join to Indian States (GADM Level 1)
print("Loading stations and joining GADM state boundaries...")
st = pd.read_csv("openaq/stations_india.csv")
st = st.dropna(subset=["lat", "lon"]).drop_duplicates(subset=["location_id"])

gadm = gpd.read_file("gadm/gadm41_IND.gpkg", layer="ADM_ADM_1")[["NAME_1", "geometry"]]
st_gdf = gpd.GeoDataFrame(
    st, geometry=gpd.points_from_xy(st["lon"], st["lat"]), crs="EPSG:4326"
)
joined = gpd.sjoin(st_gdf, gadm, how="left", predicate="within")
joined = joined.drop(columns=["geometry", "index_right"]).rename(columns={"NAME_1": "state"})
joined["state"] = joined["state"].fillna("Unknown")

# 2. Read and QC all 2021-2022 raw OpenAQ files
files = sorted(glob.glob("openaq/raw/2021/*.csv.gz") + glob.glob("openaq/raw/2022/*.csv.gz"))
print(f"Processing {len(files)} station-year files with CPCB QC rules...")

stats = {"raw_pm25": 0, "dropped_range": 0, "dropped_flatline": 0, "kept_hourly": 0}
daily_chunks = []

for f in files:
    try:
        df = pd.read_csv(f, compression="gzip", usecols=["location_id", "datetime", "parameter", "value"])
    except ValueError:
        continue

    df = df[df["parameter"] == "pm25"]
    if df.empty:
        continue

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["dt"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["value", "dt"])
    n0 = len(df)
    stats["raw_pm25"] += n0

    # Rule 1: Physical / CPCB saturation cap (0 < pm25 < 985 µg/m³)
    df = df[(df["value"] > 0) & (df["value"] < 985)]
    stats["dropped_range"] += n0 - len(df)
    if df.empty:
        continue

    # Rule 2: Stuck-sensor / flat-line filter (drop runs of >= 6 identical consecutive hourly readings)
    df = df.sort_values("dt").drop_duplicates(subset=["dt"])
    run_id = (df["value"] != df["value"].shift()).cumsum()
    run_len = df.groupby(run_id)["value"].transform("size")
    n1 = len(df)
    df = df[run_len < 6]
    stats["dropped_flatline"] += n1 - len(df)
    stats["kept_hourly"] += len(df)
    if df.empty:
        continue

    # Rule 3: CPCB NAQI daily coverage (>= 16 valid hours/day)
    df["date"] = df["dt"].dt.floor("D").dt.tz_localize(None)
    agg = (
        df.groupby(["location_id", "date"], as_index=False)
        .agg(pm25=("value", "mean"), n_hours=("value", "count"))
    )
    agg = agg[agg["n_hours"] >= 16]
    if not agg.empty:
        daily_chunks.append(agg)

daily = pd.concat(daily_chunks, ignore_index=True)
daily = daily.drop_duplicates(subset=["location_id", "date"]).sort_values(["location_id", "date"])

# 3. Compute exact calendar-day lags
lag1 = daily[["location_id", "date", "pm25"]].copy()
lag1["date"] = lag1["date"] + pd.Timedelta(days=1)
lag1 = lag1.rename(columns={"pm25": "pm25_lag1"})

lag2 = daily[["location_id", "date", "pm25"]].copy()
lag2["date"] = lag2["date"] + pd.Timedelta(days=2)
lag2 = lag2.rename(columns={"pm25": "pm25_lag2"})

daily = daily.merge(lag1, on=["location_id", "date"], how="left")
daily = daily.merge(lag2, on=["location_id", "date"], how="left")

# 4. Attach station metadata & state
meta_cols = ["location_id", "name", "locality", "state", "lat", "lon", "in_north_india_box"]
daily = daily.merge(joined[meta_cols], on="location_id", how="left")

out_path = "data/openaq_daily_2021_2022.parquet"
daily.to_parquet(out_path, index=False)

print("\n=== QC SUMMARY ===")
print(f"Raw hourly PM2.5 rows:      {stats['raw_pm25']:,}")
print(f"Dropped range (<=0, >=985): {stats['dropped_range']:,} ({100*stats['dropped_range']/stats['raw_pm25']:.2f}%)")
print(f"Dropped flat-line (>=6h):   {stats['dropped_flatline']:,} ({100*stats['dropped_flatline']/stats['raw_pm25']:.2f}%)")
print(f"Kept hourly rows:           {stats['kept_hourly']:,}")
print(f"\nSaved -> {out_path}")
print(f"Total station-days (>=16h): {len(daily):,}")
print(f"Unique stations:            {daily['location_id'].nunique()}")
print(f"Overall mean PM2.5:         {daily['pm25'].mean():.1f} µg/m³")
