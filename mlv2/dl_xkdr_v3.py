"""
dl_xkdr_v3.py -- CarbonVayu mlv3
Downloads 2019-2023 bulk monthly Parquet files from xKDR (airquality.xkdr.org)
using unique filenames (xkdr_YYYY_MM.parquet) because every remote key ends in 'data.parquet'.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

API_KEY = os.getenv("XKDR_KEY")
if not API_KEY:
    raise RuntimeError("XKDR_KEY not found in environment or .env.")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
BASE = "https://airquality.xkdr.org/v1"
OUT = Path("xkdr/raw")
OUT.mkdir(parents=True, exist_ok=True)
YEARS = {2019, 2020, 2021, 2022, 2023}

# Remove collided single data.parquet if present
collided = OUT / "data.parquet"
if collided.exists():
    collided.unlink()


def download_file(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name}")
        return
    with requests.get(url, headers=HEADERS, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
    print(f"  [saved] {dest.name} ({dest.stat().st_size / 1e6:.2f} MB)")


print("[1/2] Downloading All-India station metadata...")
download_file(f"{BASE}/stations?format=csv", Path("xkdr/stations_all.csv"))

print("[2/2] Fetching /v1/files index...")
resp = requests.get(f"{BASE}/files", headers=HEADERS, timeout=60)
resp.raise_for_status()
payload = resp.json()
items = payload if isinstance(payload, list) else payload.get("files", payload.get("data", []))

tasks = []
for item in items:
    key = item.get("key") or item.get("filename") or item.get("name") or ""
    yr = item.get("year")
    mo = item.get("month")
    if yr in YEARS and mo is not None:
        fname = f"xkdr_{int(yr)}_{int(mo):02d}.parquet"
        url = item.get("url") or item.get("download_url") or f"{BASE}/files/{key}"
        tasks.append((fname, url))

tasks.sort(key=lambda t: t[0])
print(f"Downloading {len(tasks)} monthly Parquet files for 2019-2023...")

with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(download_file, url, OUT / fname) for fname, url in tasks]
    for f in futs:
        f.result()

print(f"\nDone! Files in {OUT}: {len(list(OUT.glob('xkdr_*.parquet')))} / {len(tasks)}")
