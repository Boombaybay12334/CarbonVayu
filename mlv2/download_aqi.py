import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import pandas as pd

YEARS = [2021, 2022]
NORTH_INDIA_ONLY = False  # Set False to pull all 772 India stations
KEEP_PARAMS = {"pm25", "pm10", "no2", "so2", "co", "o3"}
MAX_WORKERS = 8
BUCKET = "openaq-data-archive"

stations = pd.read_csv("openaq/stations_india.csv")
mask = stations["has_pm25"] == True
if NORTH_INDIA_ONLY:
    mask &= stations["in_north_india_box"] == True

# Keep only stations that could have data in 2021-2022
first_dt = pd.to_datetime(stations["first_utc"], errors="coerce", utc=True)
last_dt = pd.to_datetime(stations["last_utc"], errors="coerce", utc=True)
mask &= (first_dt < "2023-01-01") & (last_dt >= "2021-01-01")

target = stations.loc[mask, ["location_id", "name", "locality"]].drop_duplicates()
print(f"Stations active in 2021-2022 to download: {len(target)}")

for yr in YEARS:
    os.makedirs(f"openaq/raw/{yr}", exist_ok=True)

def download_station_year(loc_id, year):
    out_path = f"openaq/raw/{year}/loc_{loc_id}_{year}.csv.gz"
    if os.path.exists(out_path):
        return f"[SKIP] {loc_id} ({year})"

    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    prefix = f"records/csv.gz/locationid={loc_id}/year={year}/"

    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv.gz"):
                keys.append(obj["Key"])

    if not keys:
        return f"[EMPTY] {loc_id} ({year})"

    dfs = []
    for k in keys:
        body = s3.get_object(Bucket=BUCKET, Key=k)["Body"].read()
        try:
            df = pd.read_csv(io.BytesIO(body), compression="gzip", low_memory=False)
            if "parameter" in df.columns:
                df = df[df["parameter"].isin(KEEP_PARAMS)]
            if not df.empty:
                dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return f"[NO_TARGET_PARAMS] {loc_id} ({year})"

    merged = pd.concat(dfs, ignore_index=True)
    merged.to_csv(out_path, index=False, compression="gzip")
    return f"[OK] {loc_id} ({year}): {len(merged):,} rows from {len(keys)} daily files"

tasks = [(int(row.location_id), yr) for row in target.itertuples() for yr in YEARS]
done = 0
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futures = [ex.submit(download_station_year, loc_id, yr) for loc_id, yr in tasks]
    for fut in as_completed(futures):
        done += 1
        msg = fut.result()
        if msg.startswith("[OK]") or done % 25 == 0 or done == len(tasks):
            print(f"({done}/{len(tasks)}) {msg}")

print("\nDone! Files saved under openaq/raw/2021/ and openaq/raw/2022/")
