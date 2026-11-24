"""
01_prep_xkdr_5yr.py -- CarbonVayu mlv3
Builds a clean All-India daily PM2.5 dataset (2019-2023) from xKDR's 60 monthly
Parquet files in xkdr/raw/ using xkdr/stations_all.csv and standard CPCB QC:
  1. Keep parameter_name == 'PM2.5' and 0 < value < 985 ug/m3
  2. Drop stuck-sensor flat-lines (>= 6 identical consecutive hourly values)
  3. Require >= 16 valid hours/day to form a daily mean
  4. Recompute per-station pm25_lag1 and pm25_lag2
"""
from pathlib import Path
import pandas as pd

RAW_DIR = Path("xkdr/raw")
STATIONS_PATH = Path("xkdr/stations_all.csv")
OUT_PATH = Path("data/xkdr_daily_2019_2023.parquet")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# 1. Load station metadata
st = pd.read_csv(STATIONS_PATH).dropna(subset=["latitude", "longitude"]).copy()
st = st.rename(
    columns={
        "station_name": "name",
        "state_name": "state",
        "city_name": "locality",
        "latitude": "lat",
        "longitude": "lon",
    }
)
st["lat"] = pd.to_numeric(st["lat"], errors="coerce")
st["lon"] = pd.to_numeric(st["lon"], errors="coerce")
st = st.dropna(subset=["lat", "lon"]).drop_duplicates(subset=["station_id"])
st["in_north_india_box"] = (
    (st["lat"] >= 23.0) & (st["lat"] <= 35.0) & (st["lon"] >= 73.0) & (st["lon"] <= 89.0)
)
meta_cols = ["station_id", "name", "locality", "state", "lat", "lon", "in_north_india_box"]
st_meta = st[meta_cols].copy()

# 2. Load all 60 monthly Parquet files (PM2.5 only) and apply QC
files = (
    sorted(RAW_DIR.glob("xkdr_2019_*.parquet"))
    + sorted(RAW_DIR.glob("xkdr_2020_*.parquet"))
    + sorted(RAW_DIR.glob("xkdr_2021_*.parquet"))
    + sorted(RAW_DIR.glob("xkdr_2022_*.parquet"))
    + sorted(RAW_DIR.glob("xkdr_2023_*.parquet"))
)

if len(files) != 60:
    raise RuntimeError(f"Expected 60 xKDR monthly files in {RAW_DIR}, found {len(files)}")

print(f"Processing {len(files)} xKDR monthly Parquet files (2019-2023)...")
hourly_parts = []
raw_rows = 0
qc_cap_rows = 0

for f in files:
    df = pd.read_parquet(f, columns=["station_id", "parameter_name", "collected_at", "value"])
    df = df[df["parameter_name"] == "PM2.5"].copy()
    raw_rows += len(df)

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["dt"] = pd.to_datetime(df["collected_at"], errors="coerce")
    if getattr(df["dt"].dt, "tz", None) is not None:
        df["dt"] = df["dt"].dt.tz_convert("UTC").dt.tz_localize(None)
    df = df.dropna(subset=["station_id", "value", "dt"])

    # Rule 1: 0 < PM2.5 < 985 ug/m3 (removes negative/zero artifacts & >=985 CPCB saturation)
    df = df[(df["value"] > 0.0) & (df["value"] < 985.0)]
    qc_cap_rows += len(df)
    hourly_parts.append(df[["station_id", "dt", "value"]])

hourly = pd.concat(hourly_parts, ignore_index=True)
print(f"PM2.5 hourly rows: raw={raw_rows:,} -> after (0, 985) filter={qc_cap_rows:,}")

# Rule 2: Drop stuck-sensor flat-lines (>= 6 identical consecutive hours per station)
print("Applying flat-line filter (>= 6 identical consecutive hours)...")
clean_chunks = []
flat_dropped = 0
for sid, g in hourly.groupby("station_id", sort=False):
    g = g.sort_values("dt").drop_duplicates(subset=["dt"])
    run_id = (g["value"] != g["value"].shift()).cumsum()
    run_len = g.groupby(run_id)["value"].transform("size")
    keep = run_len < 6
    flat_dropped += int((~keep).sum())
    g = g[keep]
    if not g.empty:
        clean_chunks.append(g)

hourly_qc = pd.concat(clean_chunks, ignore_index=True)
print(f"Dropped {flat_dropped:,} flat-line hourly rows -> {len(hourly_qc):,} clean hourly rows")

# Rule 3: Daily aggregation requiring >= 16 valid hours/day
hourly_qc["date"] = hourly_qc["dt"].dt.floor("D")
daily = (
    hourly_qc.groupby(["station_id", "date"], as_index=False)
    .agg(pm25=("value", "mean"), n_hours=("value", "count"))
)
daily = daily[
    (daily["n_hours"] >= 16)
    & (daily["date"] >= "2019-01-01")
    & (daily["date"] <= "2023-12-31")
].copy()

# Rename station_id -> location_id for downstream pipeline compatibility
daily = daily.rename(columns={"station_id": "location_id"})
st_meta_ren = st_meta.rename(columns={"station_id": "location_id"})
daily = daily.merge(st_meta_ren, on="location_id", how="inner")
daily = daily.sort_values(["location_id", "date"]).reset_index(drop=True)

# 4. Recompute lag-1 and lag-2 PM2.5 (only when consecutive calendar days exist)
lag1 = daily[["location_id", "date", "pm25"]].copy()
lag1["date"] = lag1["date"] + pd.Timedelta(days=1)
lag1 = lag1.rename(columns={"pm25": "pm25_lag1"})

lag2 = daily[["location_id", "date", "pm25"]].copy()
lag2["date"] = lag2["date"] + pd.Timedelta(days=2)
lag2 = lag2.rename(columns={"pm25": "pm25_lag2"})

daily = daily.merge(lag1, on=["location_id", "date"], how="left")
daily = daily.merge(lag2, on=["location_id", "date"], how="left")

col_order = [
    "location_id", "date", "pm25", "n_hours", "name", "locality", "state",
    "lat", "lon", "in_north_india_box", "pm25_lag1", "pm25_lag2",
]
daily = daily[col_order].sort_values(["date", "location_id"]).reset_index(drop=True)
daily.to_parquet(OUT_PATH, index=False)

print(f"\nSaved -> {OUT_PATH}")
print(f"Shape: {daily.shape} | Stations: {daily['location_id'].nunique()}")
print("Rows by year:")
print(
    daily.groupby(daily["date"].dt.year).agg(
        days=("date", "nunique"),
        rows=("pm25", "size"),
        stations=("location_id", "nunique"),
        mean_pm25=("pm25", "mean"),
    )
)
