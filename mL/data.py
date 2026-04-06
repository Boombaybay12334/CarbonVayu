import ee

# -----------------------------
# INIT
# -----------------------------
ee.Initialize(project='carbonvayu')

# -----------------------------
# CONFIGURATION
# -----------------------------
START_DATE = "2023-01-01"
END_DATE = "2023-06-01"
SCALE_ATM = 1000

# Step 1: Spatial Masking Boundaries (Using Districts for rich ML data)
districts_fc = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq("ADM0_NAME", "India"))

# -----------------------------
# DATASET SETUP
# -----------------------------
# Step 2: Emissions
co_ds = ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_CO").select("CO_column_number_density")

# Step 3: Wind Physics (850hPa)
merra2_ds = ee.ImageCollection("NASA/GSFC/MERRA/slv/2").select(["U850", "V850"])

# Step 4: Surface Features (Zero-Upload)
esa_lulc_ds = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").rename("ESA_Class")

# FIXED BUG: We select the band here, but do NOT rename the whole collection
viirs_ds = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG").select("avg_rad")

# Generate server-side month list
def get_months_ee(start, end):
    start_date = ee.Date(start)
    end_date = ee.Date(end)
    months = end_date.difference(start_date, 'month').round()
    return ee.List.sequence(0, months.subtract(1)).map(lambda n: start_date.advance(n, 'month'))

months_list = get_months_ee(START_DATE, END_DATE)

# -----------------------------
# THE ALL-IN-ONE PHYSICS ENGINE
# -----------------------------
def process_month(date):
    start = ee.Date(date)
    end = start.advance(1, 'month')
    target_month = start.get('month')
    target_year = start.get('year')
    
    # --- STEP 2: BACKGROUND SUBTRACTION ---
    historical = co_ds \
        .filter(ee.Filter.calendarRange(target_year.subtract(3), target_year.subtract(1), 'year')) \
        .filter(ee.Filter.calendarRange(target_month, target_month, 'month'))
    background_co = historical.reduce(ee.Reducer.percentile([10]))
    
    current_co = co_ds.filterDate(start, end).mean()
    net_own_co = current_co.subtract(background_co).rename("CO_net_emission")
    
    # --- STEP 3: WIND DRIFT EXCLUSION (850hPa) ---
    merra2 = merra2_ds.filterDate(start, end).mean()
    u_wind = merra2.select("U850")
    v_wind = merra2.select("V850")
    
    flux_u = net_own_co.multiply(u_wind).rename("CO_flux_U_850")
    flux_v = net_own_co.multiply(v_wind).rename("CO_flux_V_850")
    drift_magnitude = flux_u.pow(2).add(flux_v.pow(2)).sqrt().rename("CO_drift_magnitude_850")
    
    # --- STEP 4: SURFACE FEATURES ---
    # FIXED BUG: We flatten the month into a single image (.mean()) and THEN rename it
    viirs = viirs_ds.filterDate(start, end).mean().rename("Nighttime_Lights")
    
    # --- COMBINE ALL ---
    combined = ee.Image([
        net_own_co, 
        drift_magnitude, 
        esa_lulc_ds, 
        viirs
    ])
    
    # --- STEP 1: SPATIAL MASKING & EXTRACTION ---
    def extract_district(feature):
        # We combine mean and mode reducers so we can extract both continuous 
        # data (physics) and categorical data (ESA Land cover) simultaneously.
        stats = combined.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.mode(),
                sharedInputs=True
            ),
            geometry=feature.geometry(),
            scale=SCALE_ATM,
            maxPixels=1e13,
            tileScale=4 # <-- This acts as your safety buffer to prevent memory crashes
        )
        
        return feature.set({
            'state': feature.get('ADM1_NAME'),
            'district': feature.get('ADM2_NAME'),
            'month_start': start.format("YYYY-MM-dd"),
            'CO_net_emission': stats.get('CO_net_emission_mean'),
            'CO_drift_magnitude_850': stats.get('CO_drift_magnitude_850_mean'),
            'ESA_Majority_Class': stats.get('ESA_Class_mode'),
            'Avg_Nighttime_Lights': stats.get('Nighttime_Lights_mean')
        })
        
    return districts_fc.map(extract_district)

# Flatten the collection
final_unified_fc = ee.FeatureCollection(months_list.map(process_month)).flatten()

# -----------------------------
# BATCH EXPORT (GOOGLE'S QUEUE)
# -----------------------------
task = ee.batch.Export.table.toDrive(
    collection=final_unified_fc,
    description='M1a_Complete_XGBoost_Features',
    folder='EarthEngineExports',
    fileFormat='CSV',
    selectors=[
        'state', 'district', 'month_start', 
        'CO_net_emission', 'CO_drift_magnitude_850', 
        'ESA_Majority_Class', 'Avg_Nighttime_Lights'
    ]
)

task.start()
print("✅ ALL-IN-ONE M1a Task successfully sent to Google Earth Engine!")
print("Google will now manage the memory limits and process this in the background.")


