import glob
import os
import re
import pandas as pd
import pdfplumber

# Official national totals (Mt of Carbon) for sanity checking
OFFICIAL_MT = {
    2015: 7044.0,
    2017: 7083.0,
    2019: 7124.6,
    2021: 7204.0,
    2023: 7285.5,
}

# Known Indian states/UTs to reliably identify data rows
STATE_MARKERS = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "delhi", "goa", "gujarat", "haryana", "himachal pradesh", "jammu",
    "jharkhand", "karnataka", "kerala", "ladakh", "madhya pradesh",
    "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha",
    "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana",
    "tripura", "uttar pradesh", "uttarakhand", "west bengal", "andaman",
    "chandigarh", "dadra", "daman", "lakshadweep", "puducherry",
]

def clean_num(val):
    if not val:
        return None
    # Remove parenthesized per-hectare numbers like "(85.4)" and commas
    s = re.sub(r"\([^)]*\)", "", str(val))
    s = s.replace(",", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None

def is_state_row(text):
    t = text.lower()
    return any(st in t for st in STATE_MARKERS)

def extract_year_from_pdf(pdf_path, year):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = (page.extract_text() or "").lower()
            # Target pages that contain state-wise carbon stock tables
            if not ("carbon" in txt and ("agb" in txt or "soc" in txt or "biomass" in txt)):
                continue
            if not ("andhra pradesh" in txt or "arunachal pradesh" in txt or "maharashtra" in txt):
                continue

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cells = [str(c).replace("\n", " ").strip() if c else "" for c in row]
                    joined = " ".join(cells)
                    if not is_state_row(joined):
                        continue

                    # Find the state name cell
                    state_name = next((c for c in cells if is_state_row(c)), None)
                    if not state_name:
                        continue
                    # Strip leading serial numbers if merged with state name
                    state_name = re.sub(r"^\d+\.?\s*", "", state_name).strip()

                    # Parse all numeric cells after the state name
                    state_idx = cells.index(next(c for c in cells if is_state_row(c)))
                    nums = [clean_num(c) for c in cells[state_idx + 1:]]
                    nums = [n for n in nums if n is not None]
                    if len(nums) < 2:
                        continue

                    # Total carbon stock ('000 tonnes) is the largest value on the row
                    # (AGB + BGB + Dead Wood + Litter + SOC = Total; per-ha is much smaller)
                    total_kt = max(nums)
                    rows.append({
                        "year": year,
                        "state": state_name,
                        "carbon_stock_kt": total_kt,
                    })
    return rows

# Locate downloaded PDFs by year
all_rows = []
for year in sorted(OFFICIAL_MT.keys()):
    matches = sorted(glob.glob(f"fsi_isfr/*{year}*.pdf"))
    valid = [m for m in matches if os.path.getsize(m) > 10_000]
    if not valid:
        print(f"[SKIP] {year}: No valid PDF found in fsi_isfr/")
        continue
    print(f"Scanning {year}: {valid[0]} ...")
    extracted = extract_year_from_pdf(valid[0], year)
    # Deduplicate states if a table spanned pages or matched twice
    df_y = pd.DataFrame(extracted).drop_duplicates(subset=["state"]) if extracted else pd.DataFrame()
    if not df_y.empty:
        all_rows.append(df_y)
    else:
        print(f"  [WARN] No state-wise carbon rows auto-detected in {valid[0]}")

if not all_rows:
    raise SystemExit("No data extracted. Check ls -lh fsi_isfr/ to verify your PDFs downloaded properly.")

df = pd.concat(all_rows, ignore_index=True)
out_csv = "fsi_isfr/state_carbon_stock.csv"
df.to_csv(out_csv, index=False)
print(f"\nSaved {len(df)} rows to {out_csv}\n")

# Sanity check against official national totals
print(f"{'Year':<6} | {'States':>6} | {'Extracted (Mt)':>15} | {'Official (Mt)':>14} | {'Diff (%)':>9}")
print("-" * 62)
for year, official in OFFICIAL_MT.items():
    sub = df[df["year"] == year]
    if sub.empty:
        print(f"{year:<6} | {'0':>6} | {'MISSING':>15} | {official:>14.1f} | {'--':>9}")
        continue
    ext_mt = sub["carbon_stock_kt"].sum() / 1000.0  # '000 tonnes (kt) -> Mt
    diff_pct = ((ext_mt - official) / official) * 100.0
    print(f"{year:<6} | {len(sub):>6} | {ext_mt:>15.2f} | {official:>14.1f} | {diff_pct:>+8.2f}%")
