import os
import cdsapi
from dotenv import load_dotenv

load_dotenv()

CDS_URL = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")
CDS_KEY = os.getenv("CDS_API_KEY")

if not CDS_KEY or CDS_KEY == "YOUR_API_KEY":
    raise SystemExit("ERROR: Set your real CDS_API_KEY in .env first.")

YEARS = [2021, 2022]  # Add 2023 here if you want 3 years
MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS = [f"{d:02d}" for d in range(1, 32)]  # CDS automatically ignores invalid dates like Feb 30
TIMES = ["00:00", "06:00", "12:00", "18:00"]
AREA = [40, 60, 0, 100]  # [North, West, South, East]

os.makedirs("era5/winds_pl", exist_ok=True)
os.makedirs("era5/weather_sl", exist_ok=True)

client = cdsapi.Client(url=CDS_URL, key=CDS_KEY)

for year in YEARS:
    # A. Pressure-level winds (925 & 850 hPa) — 5,840 items/year
    pl_file = f"era5/winds_pl/era5_winds_{year}.nc"
    if not os.path.exists(pl_file):
        print(f">>> Downloading full-year winds (PL) for {year}...")
        client.retrieve(
            "reanalysis-era5-pressure-levels",
            {
                "product_type": ["reanalysis"],
                "variable": ["u_component_of_wind", "v_component_of_wind"],
                "pressure_level": ["850", "925"],
                "year": [str(year)],
                "month": MONTHS,
                "day": DAYS,
                "time": TIMES,
                "area": AREA,
                "data_format": "netcdf",
                "download_format": "unarchived",
            },
            pl_file,
        )
    else:
        print(f"[SKIP] {pl_file} already exists")

    # B. Single-level weather — 8,760 items/year
    sl_file = f"era5/weather_sl/era5_weather_{year}.nc"
    if not os.path.exists(sl_file):
        print(f">>> Downloading full-year weather (SL) for {year}...")
        client.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": ["reanalysis"],
                "variable": [
                    "boundary_layer_height",
                    "total_precipitation",
                    "2m_temperature",
                    "2m_dewpoint_temperature",
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                ],
                "year": [str(year)],
                "month": MONTHS,
                "day": DAYS,
                "time": TIMES,
                "area": AREA,
                "data_format": "netcdf",
                "download_format": "unarchived",
            },
            sl_file,
        )
    else:
        print(f"[SKIP] {sl_file} already exists")

print("All 4 yearly ERA5 downloads complete.")
