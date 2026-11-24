import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENAQ_API_KEY")
if not API_KEY or API_KEY == "YOUR_OPENAQ_KEY":
    raise SystemExit("ERROR: Set OPENAQ_API_KEY in .env first.")

os.makedirs("openaq", exist_ok=True)

url = "https://api.openaq.org/v3/locations"
headers = {"X-API-Key": API_KEY}
rows = []
page = 1

print("Fetching Indian monitoring stations from OpenAQ v3...")
while True:
    resp = requests.get(
        url,
        headers=headers,
        params={"iso": "IN", "limit": 1000, "page": page},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        break

    for loc in results:
        coords = loc.get("coordinates") or {}
        dt_first = (loc.get("datetimeFirst") or {}).get("utc")
        dt_last = (loc.get("datetimeLast") or {}).get("utc")
        params = [s["parameter"]["name"] for s in loc.get("sensors", [])]

        rows.append({
            "location_id": loc["id"],
            "name": loc.get("name"),
            "locality": loc.get("locality"),
            "provider": (loc.get("provider") or {}).get("name"),
            "lat": coords.get("latitude"),
            "lon": coords.get("longitude"),
            "first_utc": dt_first,
            "last_utc": dt_last,
            "has_pm25": "pm25" in params,
            "parameters": ",".join(sorted(set(params))),
        })

    if len(results) < 1000:
        break
    page += 1

df = pd.DataFrame(rows)
# Flag stations in the North India focus box (Delhi-NCR, Punjab, Haryana, UP)
df["in_north_india_box"] = (
    df["lat"].between(23.5, 32.6) & df["lon"].between(73.8, 84.8)
)
df.to_csv("openaq/stations_india.csv", index=False)

print(f"Total India stations: {len(df)}")
print(f"With PM2.5:           {df['has_pm25'].sum()}")
print(f"In North India box:   {(df['in_north_india_box'] & df['has_pm25']).sum()} (with PM2.5)")
print("Saved -> openaq/stations_india.csv")
