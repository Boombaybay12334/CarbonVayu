import calendar
import os
import cdsapi
from dotenv import load_dotenv

load_dotenv()

CDS_URL = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")
CDS_KEY = os.getenv("CDS_API_KEY")

if not CDS_KEY or CDS_KEY == "YOUR_API_KEY":
    raise SystemExit("ERROR: Set your real CDS_API_KEY in .env first.")

YEARS = [2021, 2022]  # Add 2023 here if you want 3 years
AREA = [40, 60, 0, 100]  # [North, West, South, East]
TIMES = ["00:00", "06:00", "12:00", "18:00"]

os.makedirs("era5/winds_pl", exist_ok=True)
os.makedirs("era5/weather_sl", exist_ok=True)

client = cdsapi.Client(url=CDS_URL, key=CDS_KEY)

for year in YEARS:
    for month in range(1, 13):
        days = [f"{d:02d}" for d in range(1, calendar.monthrange(year, month)[1] + 1)]
        ym = f"{year}_{month:02d}"

        # A. Pressure-level winds (925 & 850 hPa)
        pl_file = f"era5/winds_pl/era5_winds_{ym}.nc"
        if not os.path.exists(pl_file):
            print(f">>> Downloading winds (PL) for {ym}...")
            client.retrieve(
                "reanalysis-era5-pressure-levels",
                {
                    "product_type": ["reanalysis"],
                    "variable": ["u_component_of_wind", "v_component_of_wind"],
                    "pressure_level": ["850", "925"],
                    "year": [str(year)],
                    "month": [f"{month:02d}"],
                    "day": days,
                    "time": TIMES,
                    "area": AREA,
                    "data_format": "netcdf",
                    "download_format": "unarchived",
                },
                pl_file,
            )
        else:
            print(f"[SKIP] {pl_file} already exists")

        # B. Single-level weather
        sl_file = f"era5/weather_sl/era5_weather_{ym}.nc"
        if not os.path.exists(sl_file):
            print(f">>> Downloading weather (SL) for {ym}...")
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
                    "month": [f"{month:02d}"],
                    "day": days,
                    "time": TIMES,
                    "area": AREA,
                    "data_format": "netcdf",
                    "download_format": "unarchived",
                },
                sl_file,
            )
        else:
            print(f"[SKIP] {sl_file} already exists")

print("All ERA5 downloads complete.")
