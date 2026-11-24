"""
01b_patch_xkdr_nov2022.py -- CarbonVayu mlv2
Patches missing Delhi Nov 2022 station-days into data/openaq_daily_2021_2022.parquet
using xKDR CPCB hourly data, applying identical CPCB QC rules and matching to
existing OpenAQ location_ids by coordinates (<= 2.5 km).
"""
import numpy as np
import pandas as pd

# 1. Load existing daily OpenAQ table & station metadata
daily = pd.read_parquet("data/openaq_daily_2021_2022.parquet")
daily["date"] = pd.to_datetime(daily["date"])

meta_cols = ["location_id", "name", "locality", "state", "lat", "lon", "in_north_india_box"]
oaq_st = daily[daily["state"] == "NCT of Delhi"][meta_cols].drop_duplicates(subset=["location_id"]).reset_index(drop=True)

# 2. Match xKDR Delhi stations to nearest OpenAQ Delhi location_id (<= 2.5 km)
xk_st = pd.read_csv("openaq/xkdr_patch/delhi_stations.csv").dropna(subset=["latitude", "longitude"])

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))

matches = []
for _, row in xk_st.iterrows():
    dists = haversine_km(row["latitude"], row["longitude"], oaq_st["lat"].values, oaq_st["lon"].values)
    best_i = int(np.argmin(dists))
    if dists[best_i] <= 2.5:
        matches.append({"station_id": row["station_id"], "location_id": oaq_st.loc[best_i, "location_id"], "dist_km": dists[best_i]})

match_df = pd.DataFrame(matches).sort_values("dist_km").drop_duplicates(subset=["location_id"])
print(f"Matched {len(match_df)} / {len(xk_st)} xKDR Delhi stations to existing OpenAQ location_ids (median dist: {match_df['dist_km'].median():.2f} km)")

# 3. Apply identical CPCB QC rules to xKDR hourly PM2.5
df = pd.read_parquet("openaq/xkdr_patch/delhi_nov2022_hourly.parquet")
df = df.merge(match_df[["station_id", "location_id"]], on="station_id", how="inner")
df["value"] = pd.to_numeric(df["mean"], errors="coerce")
# Convert IST -> UTC to match OpenAQ/ERA5 calendar days
df["dt"] = pd.to_datetime(df["period_start"], errors="coerce").dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
df = df.dropna(subset=["value", "dt"])

# Rule 1: Physical / CPCB saturation cap (0 < pm25 < 985)
df = df[(df["value"] > 0) & (df["value"] < 985)]

# Rule 2: Stuck-sensor / flat-line filter (drop runs of >= 6 identical consecutive hours)
chunks = []
for loc_id, g in df.groupby("location_id"):
    g = g.sort_values("dt").drop_duplicates(subset=["dt"])
    run_id = (g["value"] != g["value"].shift()).cumsum()
    run_len = g.groupby(run_id)["value"].transform("size")
    g = g[run_len < 6]
    if not g.empty:
        chunks.append(g)

df_qc = pd.concat(chunks, ignore_index=True)

# Rule 3: CPCB NAQI daily coverage (>= 16 valid hours/day)
df_qc["date"] = df_qc["dt"].dt.floor("D").dt.tz_localize(None)
patch_daily = (
    df_qc.groupby(["location_id", "date"], as_index=False)
    .agg(pm25=("value", "mean"), n_hours=("value", "count"))
)
patch_daily = patch_daily[
    (patch_daily["n_hours"] >= 16)
    & (patch_daily["date"] >= "2022-11-01")
    & (patch_daily["date"] <= "2022-11-30")
]
patch_daily = patch_daily.merge(oaq_st, on="location_id", how="left")

# 4. Append only missing (location_id, date) rows and recompute lags
before_n = len(daily)
daily_clean = daily.drop(columns=["pm25_lag1", "pm25_lag2"])
combined = pd.concat([daily_clean, patch_daily], ignore_index=True)
combined = combined.drop_duplicates(subset=["location_id", "date"], keep="first")
combined = combined.sort_values(["location_id", "date"]).reset_index(drop=True)

lag1 = combined[["location_id", "date", "pm25"]].copy()
lag1["date"] = lag1["date"] + pd.Timedelta(days=1)
lag1 = lag1.rename(columns={"pm25": "pm25_lag1"})

lag2 = combined[["location_id", "date", "pm25"]].copy()
lag2["date"] = lag2["date"] + pd.Timedelta(days=2)
lag2 = lag2.rename(columns={"pm25": "pm25_lag2"})

combined = combined.merge(lag1, on=["location_id", "date"], how="left")
combined = combined.merge(lag2, on=["location_id", "date"], how="left")

combined.to_parquet("data/openaq_daily_2021_2022.parquet", index=False)
print(f"Added {len(combined) - before_n:,} patched Delhi Nov 2022 station-days -> total rows: {len(combined):,}")

d = combined[(combined["state"] == "NCT of Delhi") & (combined["date"].dt.year == 2022) & (combined["date"].dt.month.isin([10, 11]))]
print("\nUpdated Delhi Oct-Nov 2022 coverage:")
print(d.groupby(d["date"].dt.month).agg(days=("date", "nunique"), rows=("pm25", "size"), stations=("location_id", "nunique"), mean_pm25=("pm25", "mean")))
