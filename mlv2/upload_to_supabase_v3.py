"""
upload_to_supabase_v3.py
========================
Uploads validated 5-year mlv3 PM2.5 transport and Vaayu Token (VT) Economy
model outputs to Supabase.

Data Sources (mlv2/results/v3_5yr/vt_economy/):
  - VT_scores_v3_final.csv       -> states, vt_history (year=2023, period='2023-v3')
  - fine_claims_v3.csv          -> carbon_relations (relation_type='fine', status='fine_pending')
  - attribution_network_v3.csv  -> carbon_relations (relation_type='transport', status='neutral'/'fine_pending')

Tables updated:
  states           <- 22 modeled states updated (ranks 1-22), unmodeled states retained
  vt_history       <- snapshot for 2023 (evaluating 2019-2023 5-yr period)
  carbon_relations <- period='2023-v3' fine claims and directional transport impacts

Setup:
  Uses SUPABASE_URL and SUPABASE_KEY (service-role key) from .env
"""

import os
import sys
import math
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_FILE)

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Also fallback to legacy mL/.env if needed
    fallback_env = Path(__file__).resolve().parent.parent / "mL" / ".env"
    if fallback_env.exists():
        load_dotenv(fallback_env)
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit(
        "ERROR: Set SUPABASE_URL and SUPABASE_KEY in your environment or .env file.\n"
        "Use the service-role key (not the anon key) so writes are allowed."
    )

OUTPUT_DIR = Path(__file__).resolve().parent / "results" / "v3_5yr" / "vt_economy"
PERIOD_TAG = "2023-v3"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_AREA_KM2 = {
    "Andhra Pradesh": 162975, "Arunachal Pradesh": 83743, "Assam": 78438,
    "Bihar": 94163, "Chandigarh": 114, "Chhattisgarh": 135192, "Delhi": 1484,
    "Goa": 3702, "Gujarat": 196024, "Haryana": 44212, "Himachal Pradesh": 55673,
    "Jharkhand": 79716, "Karnataka": 191791, "Kerala": 38852,
    "Madhya Pradesh": 308252, "Maharashtra": 307713, "Manipur": 22327,
    "Meghalaya": 22429, "Mizoram": 21081, "Nagaland": 16579, "Odisha": 155707,
    "Puducherry": 492, "Punjab": 50362, "Rajasthan": 342239, "Sikkim": 7096,
    "Tamil Nadu": 130058, "Telangana": 112077, "Tripura": 10486,
    "Uttarakhand": 53483, "Uttar Pradesh": 240928, "West Bengal": 88752,
}

ECOSYSTEM_LABEL = {"F": "forest", "I": "industrial", "M": "mixed"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_csv(filename: str) -> pd.DataFrame:
    path = OUTPUT_DIR / filename
    if not path.exists():
        print(f"  [SKIP] {filename} not found at {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    print(f"  [OK]   {filename}  ({len(df)} rows)")
    return df


def clean(val):
    """Replace NaN / inf with None for valid JSON serialization."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
    except (TypeError, ValueError):
        pass
    return val


def sanitise(records: list[dict]) -> list[dict]:
    return [{k: clean(v) for k, v in row.items()} for row in records]


def upsert_states(supabase: Client, rows: list[dict], chunk: int = 100):
    if not rows:
        return
    total = len(rows)
    done = 0
    for start in range(0, total, chunk):
        batch = rows[start : start + chunk]
        supabase.table("states").upsert(batch, on_conflict="name").execute()
        done += len(batch)
    print(f"  [DONE] states: {total} rows upserted")


def insert_batches(supabase: Client, table: str, rows: list[dict], chunk: int = 100):
    if not rows:
        print(f"  [SKIP] {table}: nothing to insert")
        return
    total = len(rows)
    done = 0
    for start in range(0, total, chunk):
        batch = rows[start : start + chunk]
        supabase.table(table).insert(batch).execute()
        done += len(batch)
        print(f"  {table}: {done}/{total}", end="\r")
    print(f"  [DONE] {table}: {total} rows inserted          ")


# ---------------------------------------------------------------------------
# Table Builders
# ---------------------------------------------------------------------------

def build_states(vt_df: pd.DataFrame, existing_states: list[dict]) -> list[dict]:
    """
    Build state updates:
      - 22 modeled states get ranks 1-22, accurate vt_balance, archetype, ecosystem, area.
      - Unmodeled states already in DB retain their IDs and get ranks 23+ so no FK breaks.
    """
    df = vt_df.sort_values("rank", ascending=True).reset_index(drop=True)
    rows = []
    modeled_names = set()

    for _, r in df.iterrows():
        name = r["state"]
        modeled_names.add(name)
        rows.append({
            "name":       name,
            "vt_balance": round(float(r["vt_score"]), 2),
            "archetype":  r["archetype"],
            "ecosystem":  ECOSYSTEM_LABEL.get(r["archetype"], "mixed"),
            "area_km2":   STATE_AREA_KM2.get(name),
            "rank":       int(r["rank"]),
        })

    # Gracefully adjust unmodeled legacy states so they don't collide with ranks 1..22
    next_rank = 23
    for s in sorted(existing_states, key=lambda x: x.get("name", "")):
        if s["name"] not in modeled_names:
            rows.append({
                "name":       s["name"],
                "vt_balance": s.get("vt_balance", 0) or 0,
                "archetype":  s.get("archetype") or "Unmonitored",
                "ecosystem":  s.get("ecosystem") or "mixed",
                "area_km2":   STATE_AREA_KM2.get(s["name"], s.get("area_km2")),
                "rank":       next_rank,
            })
            next_rank += 1

    return sanitise(rows)


def build_vt_history(vt_df: pd.DataFrame, id_map: dict) -> list[dict]:
    """
    Build vt_history rows for evaluation year 2023 (5-year baseline 2019-2021 vs 2022-2023).
    """
    rows = []
    for _, r in vt_df.iterrows():
        sid = id_map.get(r["state"])
        if not sid:
            print(f"    [WARN] No UUID for '{r['state']}' — skipping vt_history row")
            continue
        rows.append({
            "state_id": sid,
            "year":     2023,
            "vt_score": round(float(r["vt_score"]), 2),
            "note": (
                f"archetype={r['archetype']}; "
                f"pm25_curr={round(float(r['pm25_curr']), 2)} ug/m3; "
                f"pm25_base={round(float(r['pm25_base']), 2)} ug/m3; "
                f"effort_multiplier={round(float(r['effort_multiplier']), 3)}; "
                f"95% CI=[{round(float(r['vt_ci_low']), 1)}, {round(float(r['vt_ci_high']), 1)}]"
            ),
        })
    return sanitise(rows)


def build_carbon_relations_from_claims(claims_df: pd.DataFrame, id_map: dict) -> list[dict]:
    """
    fine_claims_v3.csv -> carbon_relations
      source_state_id <- defendant (polluter)
      target_state_id <- claimant (harmed state)
      relation_type   = 'fine'
      vt_impact       <- fine_vt_points
      status          = 'fine_pending'
      period          = '2023-v3'
    """
    rows = []
    for _, r in claims_df.iterrows():
        src = id_map.get(r["defendant"])
        tgt = id_map.get(r["claimant"])
        if not src or not tgt:
            print(f"    [WARN] Missing UUID for claim '{r['defendant']}' -> '{r['claimant']}'")
            continue
        rows.append({
            "source_state_id": src,
            "target_state_id": tgt,
            "relation_type":   "fine",
            "vt_impact":       round(float(r["fine_vt_points"]), 2),
            "status":          "fine_pending",
            "period":          PERIOD_TAG,
        })
    return sanitise(rows)


def build_carbon_relations_from_attribution(attr_df: pd.DataFrame, id_map: dict) -> list[dict]:
    """
    attribution_network_v3.csv -> carbon_relations
      source_state_id <- net_aggressor
      target_state_id <- net_victim
      relation_type   = 'transport'
      vt_impact       <- net_harm_ugm3
      status          = 'fine_pending' (if confidence >= 0.82 and harm >= 0.1 ug/m3) else 'neutral'
      period          = '2023-v3'
    """
    rows = []
    for _, r in attr_df.iterrows():
        aggressor = r.get("net_aggressor", "")
        victim = r.get("net_victim", "")
        if not aggressor or aggressor == "balanced" or not victim or victim == "balanced":
            continue

        src = id_map.get(aggressor)
        tgt = id_map.get(victim)
        if not src or not tgt:
            continue

        net_harm = float(r.get("net_harm_ugm3", 0.0))
        if net_harm <= 1e-6:
            continue

        conf_a = float(r.get("conf_A_to_B", 0.0))
        conf_b = float(r.get("conf_B_to_A", 0.0))
        max_conf = max(conf_a, conf_b)

        # Gated status: if high confidence and noticeable impact, mark pending
        status = "fine_pending" if (max_conf >= 0.82 and net_harm >= 0.1) else "neutral"

        rows.append({
            "source_state_id": src,
            "target_state_id": tgt,
            "relation_type":   "transport",
            "vt_impact":       round(net_harm, 4),
            "status":          status,
            "period":          PERIOD_TAG,
        })
    return sanitise(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\n=== CarbonVayu Supabase v3 Upload (Period: {PERIOD_TAG}) ===\n")
    print(f"Reading CSVs from: {OUTPUT_DIR}\n")

    vt_df = load_csv("VT_scores_v3_final.csv")
    claims_df = load_csv("fine_claims_v3.csv")
    attr_df = load_csv("attribution_network_v3.csv")

    if vt_df.empty:
        sys.exit("VT_scores_v3_final.csv is required. Check directory path.")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Connected to Supabase.\n")

    # Fetch current states so we preserve existing rows & foreign keys
    res = supabase.table("states").select("id, name, vt_balance, archetype, ecosystem, area_km2, rank").execute()
    existing_states = res.data or []
    print(f"Found {len(existing_states)} existing states in database.")

    # 1. Update/Upsert states
    print("\nStep 1 — Updating states...")
    state_rows = build_states(vt_df, existing_states)
    upsert_states(supabase, state_rows)

    # Re-fetch state UUID map after upsert
    res = supabase.table("states").select("id, name").execute()
    id_map = {row["name"]: row["id"] for row in res.data}
    print(f"Retrieved {len(id_map)} state UUIDs.\n")

    # 2. Insert vt_history for 2023
    print("Step 2 — Ingesting vt_history (year=2023)...")
    # Clean any pre-existing 2023 snapshot before inserting to keep history clean
    supabase.table("vt_history").delete().eq("year", 2023).execute()
    vt_hist_rows = build_vt_history(vt_df, id_map)
    insert_batches(supabase, "vt_history", vt_hist_rows)
    print()

    # 3. Ingest carbon_relations for 2023-v3
    print(f"Step 3 — Ingesting carbon_relations (period='{PERIOD_TAG}')...")
    # Clean any pre-existing PERIOD_TAG relations to allow safe re-runs
    supabase.table("carbon_relations").delete().eq("period", PERIOD_TAG).execute()

    cr_rows = []
    if not claims_df.empty:
        fine_rows = build_carbon_relations_from_claims(claims_df, id_map)
        print(f"  fine_claims_v3       -> {len(fine_rows)} rows")
        cr_rows.extend(fine_rows)

    if not attr_df.empty:
        transport_rows = build_carbon_relations_from_attribution(attr_df, id_map)
        print(f"  attribution_network  -> {len(transport_rows)} rows")
        cr_rows.extend(transport_rows)

    insert_batches(supabase, "carbon_relations", cr_rows)
    print()

    print("=== Upload Complete ===")
    print(f"  states updated/upserted  : {len(state_rows)}")
    print(f"  vt_history (2023) inserted: {len(vt_hist_rows)}")
    print(f"  carbon_relations ({PERIOD_TAG}) : {len(cr_rows)}")


if __name__ == "__main__":
    main()
