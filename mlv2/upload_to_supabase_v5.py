"""
upload_to_supabase_v5.py -- Sync CarbonVayu VT v5 outputs to Supabase (Non-Destructive)
Reads from results/v3_5yr/vt_economy_v5/:
  - VT_scores_v5_final.csv
  - fine_claims_v5.csv
  - attribution_network_v5.csv

Safety guarantees:
  - Preserves all existing state UUIDs and user_profiles foreign keys (updates in place).
  - Gracefully strips optional v5 columns if they are not yet added to Supabase tables.
"""
import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

V5_DIR = Path("results/v3_5yr/vt_economy_v5")
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("VITE_SUPABASE_ANON_KEY")
)


def parse_args():
    p = argparse.ArgumentParser(description="Upload VT v5 stats to Supabase")
    p.add_argument("--period", default="2023-v5", help="Period tag for carbon_relations (default: 2023-v5)")
    p.add_argument(
        "--sync-v3-alias",
        action="store_true",
        help="Also overwrite period='2023-v3' so the currently deployed frontend shows v5 immediately.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print payload counts without writing to Supabase.")
    return p.parse_args()


def get_existing_columns(sb, table: str) -> set[str]:
    res = sb.table(table).select("*").limit(1).execute()
    if res.data:
        return set(res.data[0].keys())
    return set()


def filter_payload(row: dict, allowed_cols: set[str]) -> dict:
    if not allowed_cols:
        return row
    return {k: v for k, v in row.items() if k in allowed_cols}


def main():
    args = parse_args()
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env / environment.")

    vt = pd.read_csv(V5_DIR / "VT_scores_v5_final.csv")
    claims = pd.read_csv(V5_DIR / "fine_claims_v5.csv")
    net = pd.read_csv(V5_DIR / "attribution_network_v5.csv")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Inspect existing states & columns (preserve UUIDs!)
    existing_states = sb.table("states").select("id, name").execute().data or []
    name_to_id = {r["name"]: r["id"] for r in existing_states}
    state_cols = get_existing_columns(sb, "states")
    hist_cols = get_existing_columns(sb, "vt_history")
    rel_cols = get_existing_columns(sb, "carbon_relations")

    print(f"[1/3] Syncing {len(vt)} modeled states to `states` (preserving {len(name_to_id)} existing UUIDs)...")
    updated_states, inserted_states = 0, 0

    for _, r in vt.iterrows():
        st_name = str(r["state"])
        full_payload = {
            "name": st_name,
            "vt_score": round(float(r["vt_settled"]), 2),
            "vt_base": round(float(r["vt_base"]), 2),
            "vt_settled": round(float(r["vt_settled"]), 2),
            "vt_ci_low": round(float(r["vt_ci_low"]), 2),
            "vt_ci_high": round(float(r["vt_ci_high"]), 2),
            "rank": int(r["rank"]),
            "pm25_curr": round(float(r["pm25_curr"]), 2),
            "pillar_a_export": round(float(r["pillar_A_export"]), 3),
            "pillar_b_progress": round(float(r["pillar_B_progress"]), 3),
            "pillar_c_re": round(float(r["pillar_C_re"]), 3),
            "fines_owed_pts": round(float(r["fines_owed_pts"]), 2),
            "fines_received_pts": round(float(r["fines_received_pts"]), 2),
            "audit_flag": str(r["audit_flag"]),
            "archetype": "v5_open",
        }
        payload = filter_payload(full_payload, state_cols)

        if st_name in name_to_id:
            if not args.dry_run:
                sb.table("states").update(payload).eq("id", name_to_id[st_name]).execute()
            updated_states += 1
        else:
            if not args.dry_run:
                res = sb.table("states").insert(payload).execute()
                if res.data:
                    name_to_id[st_name] = res.data[0]["id"]
            inserted_states += 1

    print(f"  -> Updated: {updated_states}, Inserted: {inserted_states}")

    # 2. Sync vt_history (2023 v5 snapshot)
    print(f"[2/3] Syncing 2023 v5 snapshots to `vt_history`...")
    hist_rows = []
    for _, r in vt.iterrows():
        st_name = str(r["state"])
        st_id = name_to_id.get(st_name)
        if not st_id:
            continue
        h_row = filter_payload({
            "state_id": st_id,
            "state_name": st_name,
            "year": 2023,
            "period": args.period,
            "vt_score": round(float(r["vt_settled"]), 2),
            "vt_base": round(float(r["vt_base"]), 2),
            "vt_ci_low": round(float(r["vt_ci_low"]), 2),
            "vt_ci_high": round(float(r["vt_ci_high"]), 2),
            "rank": int(r["rank"]),
        }, hist_cols)
        hist_rows.append(h_row)

    if not args.dry_run and hist_rows:
        if "year" in hist_cols:
            sb.table("vt_history").delete().eq("year", 2023).execute()
        sb.table("vt_history").insert(hist_rows).execute()
    print(f"  -> Prepared/Inserted {len(hist_rows)} `vt_history` rows")

    # 3. Sync carbon_relations (10 CSAPR-gated fine claims + directional transport flows)
    periods_to_write = [args.period] + (["2023-v3"] if args.sync_v3_alias and args.period != "2023-v3" else [])
    print(f"[3/3] Syncing `carbon_relations` for periods: {periods_to_write}...")

    for per in periods_to_write:
        rel_rows = []
        # A. 10 Eligible Fine Claims
        for _, c in claims.iterrows():
            src_id = name_to_id.get(str(c["defendant"]))
            dst_id = name_to_id.get(str(c["claimant"]))
            if not src_id or not dst_id:
                continue
            rel_rows.append(filter_payload({
                "source_state_id": src_id,
                "target_state_id": dst_id,
                "from_state": str(c["defendant"]),
                "to_state": str(c["claimant"]),
                "relation_type": "fine",
                "type": "fine",
                "amount": round(float(c["fine_vt_points"]), 2),
                "harm_ugm3": round(float(c["harm_ugm3"]), 3),
                "confidence": round(float(c["confidence"]), 3),
                "period": per,
            }, rel_cols))

        # B. Directional Transport Network (net_harm >= 0.05 ug/m3 for clean map arcs)
        for _, n in net.iterrows():
            if float(n["net_harm_ugm3"]) < 0.05:
                continue
            agg = str(n["net_aggressor"])
            vic = str(n["net_victim"])
            src_id, dst_id = name_to_id.get(agg), name_to_id.get(vic)
            if not src_id or not dst_id:
                continue
            conf = float(n["conf_A_to_B"]) if agg == str(n["state_A"]) else float(n["conf_B_to_A"])
            rel_rows.append(filter_payload({
                "source_state_id": src_id,
                "target_state_id": dst_id,
                "from_state": agg,
                "to_state": vic,
                "relation_type": "transport",
                "type": "transport",
                "amount": round(float(n["net_harm_ugm3"]), 3),
                "harm_ugm3": round(float(n["net_harm_ugm3"]), 3),
                "confidence": round(conf, 3),
                "period": per,
            }, rel_cols))

        if not args.dry_run and rel_rows:
            if "period" in rel_cols:
                sb.table("carbon_relations").delete().eq("period", per).execute()
            # Batch insert in chunks of 100
            for start in range(0, len(rel_rows), 100):
                sb.table("carbon_relations").insert(rel_rows[start : start + 100]).execute()
        print(f"  -> Period '{per}': {len(claims)} fine rows + {len(rel_rows) - len(claims)} transport rows synced.")

    print("\nSupabase VT v5 sync complete!")


if __name__ == "__main__":
    main()
