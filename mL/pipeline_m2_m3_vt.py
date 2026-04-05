import math
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from geopy.distance import geodesic
from scipy.stats import circstd


STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttarakhand", "Uttar Pradesh",
    "West Bengal"
]

CENTROIDS = {
    "Andhra Pradesh": (15.9, 79.7), "Arunachal Pradesh": (28.2, 94.7),
    "Assam": (26.2, 92.9), "Bihar": (25.6, 85.1), "Chhattisgarh": (21.3, 81.7),
    "Goa": (15.3, 74.0), "Gujarat": (22.3, 71.2), "Haryana": (29.1, 76.1),
    "Himachal Pradesh": (31.1, 77.2), "Jharkhand": (23.6, 85.3),
    "Karnataka": (15.3, 75.7), "Kerala": (10.8, 76.3), "Madhya Pradesh": (23.5, 78.7),
    "Maharashtra": (19.7, 75.7), "Manipur": (24.7, 93.9), "Meghalaya": (25.5, 91.4),
    "Mizoram": (23.2, 92.8), "Nagaland": (26.2, 94.6), "Odisha": (20.9, 85.1),
    "Punjab": (31.1, 75.3), "Rajasthan": (27.0, 74.2), "Sikkim": (27.5, 88.5),
    "Tamil Nadu": (11.1, 78.7), "Telangana": (17.9, 79.4), "Tripura": (23.8, 91.8),
    "Uttarakhand": (30.1, 79.3), "Uttar Pradesh": (27.1, 80.9),
    "West Bengal": (23.0, 87.9)
}

STATE_AREA_KM2 = {
    "Andhra Pradesh": 162975, "Arunachal Pradesh": 83743, "Assam": 78438,
    "Bihar": 94163, "Chhattisgarh": 135192, "Goa": 3702, "Gujarat": 196024,
    "Haryana": 44212, "Himachal Pradesh": 55673, "Jharkhand": 79716,
    "Karnataka": 191791, "Kerala": 38852, "Madhya Pradesh": 308252,
    "Maharashtra": 307713, "Manipur": 22327, "Meghalaya": 22429,
    "Mizoram": 21081, "Nagaland": 16579, "Odisha": 155707, "Punjab": 50362,
    "Rajasthan": 342239, "Sikkim": 7096, "Tamil Nadu": 130058,
    "Telangana": 112077, "Tripura": 10486, "Uttarakhand": 53483,
    "Uttar Pradesh": 240928, "West Bengal": 88752
}

TYPE_F = {"Arunachal Pradesh", "Meghalaya", "Mizoram", "Nagaland", "Manipur",
          "Tripura", "Sikkim", "Himachal Pradesh", "Uttarakhand", "Assam", "Goa"}
TYPE_I = {"Maharashtra", "Gujarat", "Tamil Nadu", "Telangana", "Haryana",
          "Jharkhand", "Punjab", "West Bengal", "Andhra Pradesh"}
TYPE_M = set(STATES) - TYPE_F - TYPE_I

RE_FRACTION = {
    "Karnataka": 0.72, "Rajasthan": 0.68, "Gujarat": 0.65, "Tamil Nadu": 0.62,
    "Andhra Pradesh": 0.58, "Himachal Pradesh": 0.90, "Uttarakhand": 0.85,
    "Arunachal Pradesh": 0.88, "Sikkim": 0.82, "Meghalaya": 0.75,
    "Manipur": 0.60, "Mizoram": 0.55, "Nagaland": 0.58, "Tripura": 0.30,
    "Assam": 0.25, "Kerala": 0.55, "Goa": 0.20, "Maharashtra": 0.42,
    "Madhya Pradesh": 0.45, "Chhattisgarh": 0.22, "Odisha": 0.20,
    "Jharkhand": 0.12, "West Bengal": 0.18, "Uttar Pradesh": 0.32,
    "Bihar": 0.15, "Punjab": 0.28, "Haryana": 0.30, "Telangana": 0.50
}

AQI_DELTA = {
    "Uttar Pradesh": 10, "Bihar": 8, "Haryana": 5, "West Bengal": 3,
    "Jharkhand": 0, "Rajasthan": 2, "Punjab": -5, "Odisha": -3,
    "Chhattisgarh": -2, "Maharashtra": -5, "Gujarat": -8, "Madhya Pradesh": -3,
    "Karnataka": -10, "Tamil Nadu": -12, "Andhra Pradesh": -8,
    "Telangana": -6, "Kerala": -15, "Assam": -5, "Himachal Pradesh": -18,
    "Uttarakhand": -12, "Arunachal Pradesh": -20, "Meghalaya": -18,
    "Manipur": -10, "Mizoram": -15, "Nagaland": -12, "Sikkim": -20,
    "Tripura": -8, "Goa": -10
}

WEIGHTS = {
    "F": {"S1": 0.10, "S2": 0.15, "S3": 0.35, "S4": 0.25, "S5": 0.15},
    "I": {"S1": 0.35, "S2": 0.25, "S3": 0.10, "S4": 0.15, "S5": 0.15},
    "M": {"S1": 0.20, "S2": 0.20, "S3": 0.20, "S4": 0.20, "S5": 0.20},
}

KNOWN_CORRIDORS = [
    ("Punjab", "Haryana", [10, 11], 0.92),
    ("Punjab", "Uttar Pradesh", [10, 11], 0.92),
    ("Haryana", "Uttar Pradesh", [10, 11, 12, 1, 2], 0.88),
    ("Jharkhand", "Odisha", list(range(1, 13)), 0.80),
    ("Jharkhand", "West Bengal", list(range(1, 13)), 0.80),
    ("Uttar Pradesh", "Bihar", [11, 12, 1, 2], 0.76),
    ("Uttar Pradesh", "West Bengal", [11, 12, 1, 2], 0.76),
    ("Rajasthan", "Haryana", [5, 6], 0.75),
    ("Maharashtra", "Telangana", [4, 5], 0.77),
    ("Maharashtra", "Andhra Pradesh", [4, 5], 0.77),
]


def clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def archetype_for_state(state: str) -> str:
    if state in TYPE_F:
        return "F"
    if state in TYPE_I:
        return "I"
    return "M"


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    angle = math.degrees(math.atan2(x, y))
    return (angle + 360.0) % 360.0


def circular_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def load_inputs(base_dir: Path):
    absorption_df = pd.read_csv(base_dir / "data" / "m1b.csv")
    panel_df = pd.read_csv(base_dir / "data" / "m1a" / "state_emissions_panel_2015_2022.csv")
    em2022_df = pd.read_csv(base_dir / "data" / "m1a" / "state_emissions_2022.csv")

    absorption_df = absorption_df[absorption_df["state"].isin(STATES)].copy()
    panel_df = panel_df[panel_df["state"].isin(STATES)].copy()
    em2022_df = em2022_df[em2022_df["state"].isin(STATES)].copy()

    absorption_map = dict(zip(absorption_df["state"], absorption_df["absorption_mtco2_per_year"]))
    emission_2022_map = dict(zip(em2022_df["state"], em2022_df["total_emission_mt"]))

    return absorption_map, panel_df, emission_2022_map


def compute_m2(base_dir: Path, emission_2022_map):
    era5_path = base_dir / "data" / "era5.nc"
    ds = xr.open_dataset(era5_path)

    print("ERA5 variables:", list(ds.data_vars))
    print("ERA5 dimensions:", dict(ds.sizes))

    if "u" not in ds.data_vars or "v" not in ds.data_vars:
        raise ValueError("ERA5 file must contain data variables 'u' and 'v'.")

    u_da = ds["u"]
    v_da = ds["v"]

    if "pressure_level" in u_da.dims:
        u_da = u_da.isel(pressure_level=0)
        v_da = v_da.isel(pressure_level=0)

    winds = {}
    months_of_year = None
    for state in STATES:
        lat, lon = CENTROIDS[state]
        u_series = u_da.sel(latitude=lat, longitude=lon, method="nearest").values.astype(float)
        v_series = v_da.sel(latitude=lat, longitude=lon, method="nearest").values.astype(float)
        wind_dir = (np.degrees(np.arctan2(u_series, v_series)) + 360.0) % 360.0
        wind_speed = np.sqrt(u_series ** 2 + v_series ** 2)
        winds[state] = {
            "u": u_series,
            "v": v_series,
            "dir": wind_dir,
            "speed": wind_speed,
        }

        if months_of_year is None:
            if "valid_time" in ds.coords:
                vt = pd.to_datetime(ds["valid_time"].values)
                months_of_year = vt.month.to_numpy()
            else:
                months_of_year = np.arange(1, len(wind_dir) + 1)

    ds.close()

    n = len(STATES)
    WINTER_MONTHS = {10, 11, 12, 1, 2, 3}
    SUMMER_MONTHS = {4, 5, 6, 7, 8, 9}
    winter_idx = [m for m, mo in enumerate(months_of_year) if mo in WINTER_MONTHS]
    summer_idx = [m for m, mo in enumerate(months_of_year) if mo in SUMMER_MONTHS]

    raw_weight = np.zeros((n, n, len(months_of_year)), dtype=float)
    weight = np.zeros((n, n), dtype=float)
    weight_winter = np.zeros((n, n), dtype=float)
    weight_summer = np.zeros((n, n), dtype=float)
    norm_weight = np.zeros((n, n), dtype=float)
    confidence = np.zeros((n, n), dtype=float)

    for i, src in enumerate(STATES):
        for j, dst in enumerate(STATES):
            if i == j:
                continue

            lat1, lon1 = CENTROIDS[src]
            lat2, lon2 = CENTROIDS[dst]
            bearing = bearing_degrees(lat1, lon1, lat2, lon2)
            distance_km = geodesic((lat1, lon1), (lat2, lon2)).km
            if distance_km <= 0:
                continue

            for m in range(len(months_of_year)):
                angle_diff = circular_diff_deg(winds[src]["dir"][m], bearing)
                if angle_diff <= 60.0:
                    raw_weight[i, j, m] = math.cos(math.radians(angle_diff)) / (distance_km ** 2)

            if winter_idx:
                weight_winter[i, j] = float(np.mean(raw_weight[i, j, winter_idx]))
            if summer_idx:
                weight_summer[i, j] = float(np.mean(raw_weight[i, j, summer_idx]))

            # Use the dominant season per pair.
            weight[i, j] = max(weight_winter[i, j], weight_summer[i, j])

    for i in range(n):
        off_diag_sum = float(np.sum(weight[i, :]) - weight[i, i])
        if off_diag_sum > 0:
            for j in range(n):
                if i != j:
                    norm_weight[i, j] = weight[i, j] / off_diag_sum

    diagonal_frac = {
        state: STATE_AREA_KM2[state] / (STATE_AREA_KM2[state] + 50000.0)
        for state in STATES
    }

    M = np.zeros((n, n), dtype=float)
    for i, src in enumerate(STATES):
        emission_mt = float(emission_2022_map[src])
        diag_f = diagonal_frac[src]
        M[i, i] = emission_mt * diag_f
        for j in range(n):
            if i == j:
                continue
            M[i, j] = emission_mt * (1.0 - diag_f) * norm_weight[i, j]

    for i, src in enumerate(STATES):
        for j, dst in enumerate(STATES):
            if i == j or norm_weight[i, j] <= 0:
                continue

            lat1, lon1 = CENTROIDS[src]
            lat2, lon2 = CENTROIDS[dst]
            bearing = bearing_degrees(lat1, lon1, lat2, lon2)
            monthly_angles = np.array([winds[src]["dir"][m] - bearing for m in range(len(months_of_year))], dtype=float)
            monthly_angles_rad = np.radians(monthly_angles)
            wind_sd = np.degrees(circstd(monthly_angles_rad, high=np.pi, low=-np.pi))

            if wind_sd < 20.0:
                confidence[i, j] = 0.80
            elif wind_sd < 50.0:
                confidence[i, j] = 0.65
            else:
                confidence[i, j] = 0.0

    for src, dst, _months, conf in KNOWN_CORRIDORS:
        i = STATES.index(src)
        j = STATES.index(dst)
        confidence[i, j] = conf

    own_emission_mt = {state: float(M[idx, idx]) for idx, state in enumerate(STATES)}
    exported_harm_mt = {
        state: float(np.sum(M[idx, :]) - M[idx, idx])
        for idx, state in enumerate(STATES)
    }
    received_credit_mt = {
        state: float(np.sum(M[:, idx]) - M[idx, idx])
        for idx, state in enumerate(STATES)
    }

    return (
        M,
        confidence,
        diagonal_frac,
        own_emission_mt,
        exported_harm_mt,
        received_credit_mt,
        weight_winter,
        weight_summer,
    )


def compute_m3(absorption_map, panel_df, emission_2022_map):
    panel_2019 = panel_df[panel_df["year"] == 2019][["state", "total_emission_mt"]].rename(columns={"total_emission_mt": "e2019"})
    panel_2022 = panel_df[panel_df["year"] == 2022][["state", "total_emission_mt"]].rename(columns={"total_emission_mt": "e2022"})
    trend_df = panel_2019.merge(panel_2022, on="state", how="inner")

    max_abs = max(absorption_map[s] for s in STATES)
    rows = []
    for state in STATES:
        row = trend_df[trend_df["state"] == state]
        e2019 = float(row["e2019"].iloc[0]) if not row.empty else 0.0
        e2022 = float(row["e2022"].iloc[0]) if not row.empty else 0.0

        if e2019 > 0:
            emission_delta = (e2022 - e2019) / e2019
            s1 = clip01(1.0 - (emission_delta / 0.05))
        else:
            s1 = 0.5

        s2 = float(RE_FRACTION[state])
        s3 = clip01(float(absorption_map[state]) / max_abs)
        s4 = clip01(0.5 - (AQI_DELTA.get(state, 0) / 40.0))
        e_max_val = panel_df[panel_df["state"] == state]["total_emission_mt"].max()
        e_max_val = float(e_max_val) if pd.notna(e_max_val) and e_max_val > 0 else 1.0
        s5 = clip01(1.0 - (e2022 / (e_max_val * 1.05)))

        archetype = archetype_for_state(state)
        w = WEIGHTS[archetype]
        weighted_average = (
            w["S1"] * s1
            + w["S2"] * s2
            + w["S3"] * s3
            + w["S4"] * s4
            + w["S5"] * s5
        )
        effort_multiplier = 0.5 + 1.5 * weighted_average

        rows.append({
            "state": state,
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": s4,
            "S5": s5,
            "archetype": archetype,
            "effort_multiplier": effort_multiplier,
        })

    m3_df = pd.DataFrame(rows)
    return m3_df


def compute_vt(absorption_map, panel_df, emission_2022_map, own_emission_mt, exported_harm_mt, received_credit_mt, m3_df):
    # Cap absorption at 2x current-year emissions to reduce scale dominance.
    absorption_capped = {
        state: min(float(absorption_map[state]), 2.0 * float(emission_2022_map[state]))
        for state in STATES
    }

    baseline_expected = {}
    for state in STATES:
        e_hist = panel_df[(panel_df["state"] == state) & (panel_df["year"].isin([2019, 2020, 2021]))]["total_emission_mt"]
        emissions_2019_2021 = float(e_hist.mean())
        baseline_expected[state] = float(absorption_capped[state]) - emissions_2019_2021

    effort_map = dict(zip(m3_df["state"], m3_df["effort_multiplier"]))
    archetype_map = dict(zip(m3_df["state"], m3_df["archetype"]))

    raw_balance = {}
    adjusted_balance = {}
    excess_over_baseline = {}
    for state in STATES:
        rb = (
            float(absorption_capped[state])
            - float(own_emission_mt[state])
            - float(exported_harm_mt[state])
            + float(received_credit_mt[state])
        )
        raw_balance[state] = rb
        adjusted_balance[state] = rb * float(effort_map[state])
        excess_over_baseline[state] = adjusted_balance[state] - float(baseline_expected[state])

    excess_values = np.array([excess_over_baseline[s] for s in STATES], dtype=float)
    median_excess = float(np.median(excess_values))
    spread = float(np.percentile(excess_values, 90) - np.percentile(excess_values, 10))
    iqr_half = spread / 2.0 if spread > 1e-12 else 1e-12

    def normalise(x: float) -> float:
        z = (x - median_excess) / iqr_half
        return float(np.clip(500.0 + z * 120.0, 300.0, 700.0))

    vt_score = {state: normalise(excess_over_baseline[state]) for state in STATES}

    rows = []
    for state in STATES:
        rows.append({
            "state": state,
            "archetype": archetype_map[state],
            "emission_2022_mt": float(emission_2022_map[state]),
            "absorption_mt": float(absorption_capped[state]),
            "own_emission_mt": float(own_emission_mt[state]),
            "exported_harm_mt": float(exported_harm_mt[state]),
            "received_credit_mt": float(received_credit_mt[state]),
            "raw_balance": float(raw_balance[state]),
            "effort_multiplier": float(effort_map[state]),
            "adjusted_balance": float(adjusted_balance[state]),
            "baseline_expected": float(baseline_expected[state]),
            "excess_over_baseline": float(excess_over_baseline[state]),
            "VT_score": float(vt_score[state]),
        })

    vt_df = pd.DataFrame(rows)
    return vt_df


def build_fine_claims(M, confidence):
    off_diag_vals = [
        float(M[i, j])
        for i in range(len(STATES))
        for j in range(len(STATES))
        if i != j and M[i, j] > 0
    ]
    harm_threshold = float(np.percentile(off_diag_vals, 75)) if off_diag_vals else 0.0
    print(f"Dynamic fine threshold (P75): {harm_threshold:.6f} MT")

    claims = []
    for i, src in enumerate(STATES):
        for j, dst in enumerate(STATES):
            if i == j:
                continue
            harm = float(M[i, j])
            conf = float(confidence[i, j])
            if conf > 0.75 and harm > harm_threshold:
                claims.append({
                    "defendant_state": src,
                    "claimant_state": dst,
                    "harm_mt": harm,
                    "confidence": conf,
                    "fine_vt_units": harm * conf,
                })
    columns = ["defendant_state", "claimant_state", "harm_mt", "confidence", "fine_vt_units"]
    claims_df = pd.DataFrame(claims, columns=columns)
    return claims_df, harm_threshold


def build_attribution_network(M, confidence, emission_2022_map):
    """
    For every ordered state pair (i, j) where i != j and M[i,j] > 0:
    - Record the directed harm from i to j
    - Record the reverse direction j to i (may be 0)
    - Compute net bilateral balance: who is the net aggressor and by how much
    - Flag if confidence > 0.75 (fine-eligible)
    - Compute what % of state i's total exported harm goes to state j
    - Compute what % of state j's total received harm comes from state i
    """
    _ = emission_2022_map
    n = len(STATES)
    rows = []

    total_exported = {
        state: sum(M[i, j] for j in range(n) if j != i)
        for i, state in enumerate(STATES)
    }
    total_received = {
        state: sum(M[i, j] for i in range(n) if i != j)
        for j, state in enumerate(STATES)
    }

    seen_pairs = set()
    for i, src in enumerate(STATES):
        for j, dst in enumerate(STATES):
            if i == j:
                continue

            harm_ij = float(M[i, j])
            if harm_ij <= 0:
                continue

            pair_key = tuple(sorted([i, j]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            harm_ji = float(M[j, i])
            net_harm = harm_ij - harm_ji

            conf_ij = float(confidence[i, j])
            conf_ji = float(confidence[j, i])

            if net_harm > 0:
                aggressor = src
                victim = dst
                net_magnitude = net_harm
            elif net_harm < 0:
                aggressor = dst
                victim = src
                net_magnitude = -net_harm
            else:
                aggressor = "balanced"
                victim = "balanced"
                net_magnitude = 0.0

            aggressor_idx = STATES.index(aggressor) if aggressor != "balanced" else i
            total_exp = total_exported[STATES[aggressor_idx]]
            export_share_pct = (net_magnitude / total_exp * 100) if total_exp > 0 else 0.0

            victim_idx = STATES.index(victim) if victim != "balanced" else j
            total_rec = total_received[STATES[victim_idx]]
            receipt_share_pct = (net_magnitude / total_rec * 100) if total_rec > 0 else 0.0

            rows.append({
                "state_A": src,
                "state_B": dst,
                "harm_A_to_B_mt": harm_ij,
                "harm_B_to_A_mt": harm_ji,
                "net_harm_mt": net_harm,
                "net_aggressor": aggressor,
                "net_victim": victim,
                "net_magnitude_mt": net_magnitude,
                "conf_A_to_B": conf_ij,
                "conf_B_to_A": conf_ji,
                "fine_eligible_A_to_B": conf_ij > 0.75,
                "fine_eligible_B_to_A": conf_ji > 0.75,
                "aggressor_export_share_pct": round(export_share_pct, 2),
                "victim_receipt_share_pct": round(receipt_share_pct, 2),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("net_magnitude_mt", ascending=False).reset_index(drop=True)
    return df


def build_state_impact_summary(M, confidence, attribution_network_df):
    """
    For each state, produce:
    - Top 3 states it harms most (by MT exported to them)
    - Top 3 states harming it most (by MT received from them)
    - Whether it is a net aggressor or net victim in the system overall
    - Total VT-relevant harm it exports vs receives
    """
    _ = attribution_network_df
    n = len(STATES)
    rows = []

    for idx, state in enumerate(STATES):
        outbound = []
        for j in range(n):
            if j != idx and M[idx, j] > 0:
                outbound.append((STATES[j], float(M[idx, j]), float(confidence[idx, j])))
        outbound.sort(key=lambda x: x[1], reverse=True)

        inbound = []
        for i in range(n):
            if i != idx and M[i, idx] > 0:
                inbound.append((STATES[i], float(M[i, idx]), float(confidence[i, idx])))
        inbound.sort(key=lambda x: x[1], reverse=True)

        total_exported = sum(x[1] for x in outbound)
        total_received = sum(x[1] for x in inbound)
        net_position = total_exported - total_received

        rows.append({
            "state": state,
            "total_exported_harm_mt": round(total_exported, 6),
            "total_received_harm_mt": round(total_received, 6),
            "net_position_mt": round(net_position, 6),
            "system_role": "net aggressor" if net_position > 0.001
            else "net victim" if net_position < -0.001
            else "balanced",
            "top_victim_1": outbound[0][0] if len(outbound) > 0 else "",
            "top_victim_1_mt": round(outbound[0][1], 6) if len(outbound) > 0 else 0,
            "top_victim_1_conf": round(outbound[0][2], 3) if len(outbound) > 0 else 0,
            "top_victim_2": outbound[1][0] if len(outbound) > 1 else "",
            "top_victim_2_mt": round(outbound[1][1], 6) if len(outbound) > 1 else 0,
            "top_victim_3": outbound[2][0] if len(outbound) > 2 else "",
            "top_victim_3_mt": round(outbound[2][1], 6) if len(outbound) > 2 else 0,
            "top_aggressor_1": inbound[0][0] if len(inbound) > 0 else "",
            "top_aggressor_1_mt": round(inbound[0][1], 6) if len(inbound) > 0 else 0,
            "top_aggressor_1_conf": round(inbound[0][2], 3) if len(inbound) > 0 else 0,
            "top_aggressor_2": inbound[1][0] if len(inbound) > 1 else "",
            "top_aggressor_2_mt": round(inbound[1][1], 6) if len(inbound) > 1 else 0,
            "top_aggressor_3": inbound[2][0] if len(inbound) > 2 else "",
            "top_aggressor_3_mt": round(inbound[2][1], 6) if len(inbound) > 2 else 0,
        })

    return pd.DataFrame(rows)


def save_outputs(
    base_dir: Path,
    M,
    confidence,
    own_emission_mt,
    exported_harm_mt,
    received_credit_mt,
    m3_df,
    vt_df,
    claims_df,
    attribution_df,
    impact_summary_df,
):
    out_dir = base_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    m2_matrix_df = pd.DataFrame(M, index=STATES, columns=STATES)
    m2_conf_df = pd.DataFrame(confidence, index=STATES, columns=STATES)
    m2_derived_df = pd.DataFrame({
        "state": STATES,
        "own_emission_mt": [own_emission_mt[s] for s in STATES],
        "exported_harm_mt": [exported_harm_mt[s] for s in STATES],
        "received_credit_mt": [received_credit_mt[s] for s in STATES],
    })

    m2_matrix_df.to_csv(out_dir / "M2_matrix.csv", index=True, index_label="state")
    m2_conf_df.to_csv(out_dir / "M2_confidence.csv", index=True, index_label="state")
    m2_derived_df.to_csv(out_dir / "M2_derived.csv", index=False)
    m3_df.to_csv(out_dir / "M3_effort.csv", index=False)
    vt_df.to_csv(out_dir / "VT_scores_final.csv", index=False)
    claims_df.to_csv(out_dir / "fine_claims.csv", index=False)
    attribution_df.to_csv(out_dir / "attribution_network.csv", index=False)
    impact_summary_df.to_csv(out_dir / "state_impact_summary.csv", index=False)


def print_completion(
    vt_df,
    claims_df,
    diagonal_frac,
    m3_df,
    attribution_df,
    impact_summary_df,
    weight_winter,
    weight_summer,
    harm_threshold,
    M,
    emission_2022_map,
):
    leaderboard = vt_df.sort_values("VT_score", ascending=False).reset_index(drop=True)
    print("\n1) Full leaderboard (VT_score desc):")
    print(leaderboard[["state", "VT_score"]].to_string(index=False))

    penalty_count = int((vt_df["VT_score"] < 500).sum())
    incentive_count = int((vt_df["VT_score"] >= 500).sum())
    print("\n2) Zone counts:")
    print(f"Penalty zone (VT < 500): {penalty_count}")
    print(f"Incentive zone (VT >= 500): {incentive_count}")

    print("\n3) Top 10 fine claims by harm_mt:")
    if claims_df.empty:
        print("No fine claims met the dynamic threshold.")
    else:
        top_claims = claims_df.sort_values("harm_mt", ascending=False).head(10)
        print(top_claims.to_string(index=False))

    delhi_proxy_area = 21400.0
    delhi_proxy_diag = delhi_proxy_area / (delhi_proxy_area + 50000.0)
    print("\n4) M2 sanity diagonal fractions:")
    print(f"Goa: {diagonal_frac['Goa']:.4f} (~7%)")
    print(f"Delhi proxy: {delhi_proxy_diag:.4f} (~30%)")
    print(f"Madhya Pradesh: {diagonal_frac['Madhya Pradesh']:.4f} (~86%)")
    print(f"Rajasthan: {diagonal_frac['Rajasthan']:.4f} (~87%)")

    min_effort = float(m3_df["effort_multiplier"].min())
    max_effort = float(m3_df["effort_multiplier"].max())
    in_range = bool(((m3_df["effort_multiplier"] >= 0.5) & (m3_df["effort_multiplier"] <= 2.0)).all())
    print("\n5) M3 sanity effort range:")
    print(f"Range observed: [{min_effort:.6f}, {max_effort:.6f}] ; all in [0.5, 2.0] = {in_range}")

    has_exact_300 = bool((vt_df["VT_score"] == 300.0).any())
    has_exact_700 = bool((vt_df["VT_score"] == 700.0).any())
    print("\n6) VT sanity clipping check:")
    print(f"Any exact 300: {has_exact_300}")
    print(f"Any exact 700: {has_exact_700}")

    print(
        f"\n7) Seasonal transport: winter-dominant pairs: {int((weight_winter > weight_summer).sum())}, "
        f"summer-dominant: {int((weight_summer > weight_winter).sum())}"
    )

    print("\n8) Attribution network summary:")
    print(f"   Total directed pairs with transport: {len(attribution_df)}")
    if not attribution_df.empty:
        top5 = attribution_df.head(5)
        print("   Top 5 net aggressor→victim pairs:")
        for _, row in top5.iterrows():
            flag = " [FINE ELIGIBLE]" if row["fine_eligible_A_to_B"] or row["fine_eligible_B_to_A"] else ""
            print(
                f"   {row['net_aggressor']} → {row['net_victim']}: "
                f"{row['net_magnitude_mt']:.4f} MT net{flag}"
            )

    print("\n9) Per-state system role (net aggressors):")
    aggressors = impact_summary_df[impact_summary_df["system_role"] == "net aggressor"].sort_values(
        "net_position_mt", ascending=False
    )
    for _, row in aggressors.iterrows():
        print(
            f"   {row['state']}: exports {row['total_exported_harm_mt']:.4f} MT, "
            f"top victim = {row['top_victim_1']} ({row['top_victim_1_mt']:.4f} MT)"
        )

    print("\n10) Per-state system role (net victims):")
    victims = impact_summary_df[impact_summary_df["system_role"] == "net victim"].sort_values("net_position_mt")
    for _, row in victims.iterrows():
        print(
            f"   {row['state']}: receives {row['total_received_harm_mt']:.4f} MT, "
            f"top aggressor = {row['top_aggressor_1']} ({row['top_aggressor_1_mt']:.4f} MT)"
        )

    print("\n11) Additional sanity checks:")
    print(f"No exact clipping endpoints (300/700): {not has_exact_300 and not has_exact_700}")
    print(f"Effort multipliers all within [0.5, 2.0]: {in_range}")

    s_compare = m3_df[["state", "S1", "S5"]].copy()
    s_compare["diff"] = (s_compare["S1"] - s_compare["S5"]).abs()
    s5_diff_count = int((s_compare["diff"] > 1e-12).sum())
    print(f"S5 differs from S1 for states: {s5_diff_count} (target >= 15)")
    print(s_compare[["state", "S1", "S5"]].to_string(index=False))

    print(f"Fine claims count > 0: {len(claims_df) > 0} ; count = {len(claims_df)}")
    print(f"Dynamic P75 fine threshold used: {harm_threshold:.6f} MT")

    emission_vec = np.array([float(emission_2022_map[s]) for s in STATES], dtype=float)
    row_sums = np.sum(M, axis=1)
    max_row_err = float(np.max(np.abs(row_sums - emission_vec)))
    print(f"M2 row sums conservation within 1e-10: {max_row_err <= 1e-10} ; max error = {max_row_err:.3e}")

    fine_eligible_pair_count = int(
        (
            attribution_df["fine_eligible_A_to_B"].astype(bool)
            | attribution_df["fine_eligible_B_to_A"].astype(bool)
        ).sum()
    ) if not attribution_df.empty else 0
    print(
        f"Attribution has at least 1 fine-eligible pair: {fine_eligible_pair_count > 0} ; "
        f"count = {fine_eligible_pair_count}"
    )

    state_count_impact = int(impact_summary_df["state"].nunique()) if not impact_summary_df.empty else 0
    print(f"Every state appears in state impact summary: {state_count_impact == len(STATES)} ; count = {state_count_impact}")

    print(
        f"Winter vs summer dominant counts: winter={int((weight_winter > weight_summer).sum())}, "
        f"summer={int((weight_summer > weight_winter).sum())}"
    )

    if not attribution_df.empty:
        top5 = attribution_df.sort_values("net_magnitude_mt", ascending=False).head(5)
        print("Top 5 net aggressor→victim pairs:")
        for _, row in top5.iterrows():
            print(f"  {row['net_aggressor']} → {row['net_victim']}: {row['net_magnitude_mt']:.4f} MT")

    victim_rows = impact_summary_df[impact_summary_df["system_role"] == "net victim"].sort_values("net_position_mt").head(3)
    print("Top 3 net victim states and primary aggressors:")
    for _, row in victim_rows.iterrows():
        print(
            f"  {row['state']} ; primary aggressor: {row['top_aggressor_1']} "
            f"({row['top_aggressor_1_mt']:.4f} MT)"
        )


def main():
    base_dir = Path(__file__).resolve().parent

    absorption_map, panel_df, emission_2022_map = load_inputs(base_dir)

    M, confidence, diagonal_frac, own_emission_mt, exported_harm_mt, received_credit_mt, weight_winter, weight_summer = compute_m2(
        base_dir, emission_2022_map
    )

    m3_df = compute_m3(absorption_map, panel_df, emission_2022_map)

    vt_df = compute_vt(
        absorption_map,
        panel_df,
        emission_2022_map,
        own_emission_mt,
        exported_harm_mt,
        received_credit_mt,
        m3_df,
    )

    claims_df, harm_threshold = build_fine_claims(M, confidence)
    attribution_df = build_attribution_network(M, confidence, emission_2022_map)
    impact_summary_df = build_state_impact_summary(M, confidence, attribution_df)

    save_outputs(
        base_dir,
        M,
        confidence,
        own_emission_mt,
        exported_harm_mt,
        received_credit_mt,
        m3_df,
        vt_df,
        claims_df,
        attribution_df,
        impact_summary_df,
    )

    print_completion(
        vt_df,
        claims_df,
        diagonal_frac,
        m3_df,
        attribution_df,
        impact_summary_df,
        weight_winter,
        weight_summer,
        harm_threshold,
        M,
        emission_2022_map,
    )


if __name__ == "__main__":
    main()