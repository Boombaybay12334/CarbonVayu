import argparse
import math
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from geopy.distance import geodesic
from scipy.stats import circstd

try:
    from xgboost import XGBRegressor
except Exception as exc:  # pragma: no cover - import guard
    raise ImportError("xgboost is required. Install it in your environment before running ml_m2_m3.py") from exc

from pipeline_m2_m3_vt import (
    CENTROIDS,
    KNOWN_CORRIDORS,
    STATE_AREA_KM2,
    STATES,
    WEIGHTS,
    archetype_for_state,
    bearing_degrees,
    circular_diff_deg,
    clip01,
    get_aqi_delta,
    get_re_fraction,
    load_inputs,
)


XGB_DEFAULT_PARAMS = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "verbosity": 0,
}

XGB_M3_PARAMS = {
    "n_estimators": 200,
    "max_depth": 2,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "verbosity": 0,
}

EPS = 1e-12


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _circular_mean_deg(angles_deg: np.ndarray) -> float:
    if angles_deg.size == 0:
        return 0.0
    radians = np.radians(angles_deg)
    s = float(np.mean(np.sin(radians)))
    c = float(np.mean(np.cos(radians)))
    return float((np.degrees(np.arctan2(s, c)) + 360.0) % 360.0)


def _build_corridor_conf_map():
    corr_map = {}
    for src, dst, _months, conf in KNOWN_CORRIDORS:
        corr_map[(src, dst)] = float(max(conf, corr_map.get((src, dst), 0.0)))
    return corr_map


def _read_era5_winds(base_dir: Path):
    era5_path = base_dir / "data" / "era5.nc"
    ds = xr.open_dataset(era5_path)

    if "u" not in ds.data_vars or "v" not in ds.data_vars:
        raise ValueError("ERA5 file must contain data variables 'u' and 'v'.")

    u_da = ds["u"]
    v_da = ds["v"]

    if "pressure_level" in u_da.dims:
        u_da = u_da.isel(pressure_level=0)
        v_da = v_da.isel(pressure_level=0)

    if "valid_time" in ds.coords:
        vt = pd.to_datetime(ds["valid_time"].values)
        months_of_year = vt.month.to_numpy()
    else:
        n_time = int(u_da.sizes.get("time", u_da.sizes.get("valid_time", 12)))
        months_of_year = np.arange(1, n_time + 1)

    WINTER_MONTHS = {10, 11, 12, 1, 2, 3}
    SUMMER_MONTHS = {4, 5, 6, 7, 8, 9}
    winter_idx = [m for m, mo in enumerate(months_of_year) if mo in WINTER_MONTHS]
    summer_idx = [m for m, mo in enumerate(months_of_year) if mo in SUMMER_MONTHS]

    winds = {}
    for state in STATES:
        lat, lon = CENTROIDS[state]
        u_series = u_da.sel(latitude=lat, longitude=lon, method="nearest").values.astype(float)
        v_series = v_da.sel(latitude=lat, longitude=lon, method="nearest").values.astype(float)

        wind_dir = (np.degrees(np.arctan2(u_series, v_series)) + 360.0) % 360.0
        wind_speed = np.sqrt(u_series ** 2 + v_series ** 2)

        winter_dir = _circular_mean_deg(wind_dir[winter_idx]) if winter_idx else _circular_mean_deg(wind_dir)
        summer_dir = _circular_mean_deg(wind_dir[summer_idx]) if summer_idx else _circular_mean_deg(wind_dir)

        winds[state] = {
            "u": u_series,
            "v": v_series,
            "dir": wind_dir,
            "speed": wind_speed,
            "mean_speed": float(np.mean(wind_speed)),
            "mean_dir": _circular_mean_deg(wind_dir),
            "dir_circ_std_deg": float(np.degrees(circstd(np.radians(wind_dir), high=2.0 * np.pi, low=0.0))),
            "winter_mean_speed": float(np.mean(wind_speed[winter_idx])) if winter_idx else float(np.mean(wind_speed)),
            "winter_mean_dir": float(winter_dir),
            "summer_mean_speed": float(np.mean(wind_speed[summer_idx])) if summer_idx else float(np.mean(wind_speed)),
            "summer_mean_dir": float(summer_dir),
        }

    ds.close()
    return winds, months_of_year, winter_idx, summer_idx


def _compute_deterministic_m2_targets(winds, months_of_year, winter_idx, summer_idx):
    n = len(STATES)
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

            weight[i, j] = max(weight_winter[i, j], weight_summer[i, j])

    for i in range(n):
        off_diag_sum = float(np.sum(weight[i, :]) - weight[i, i])
        if off_diag_sum > 0:
            for j in range(n):
                if i != j:
                    norm_weight[i, j] = weight[i, j] / off_diag_sum

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
        confidence[i, j] = float(conf)

    return norm_weight, confidence, weight_winter, weight_summer


def _pairwise_loocv_regression(X, y, src_idx, dst_idx, params, label):
    oof_pred = np.zeros_like(y, dtype=float)
    oof_baseline = np.zeros_like(y, dtype=float)
    fold_rmse = []
    fold_train_rmse = []
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"

    for hold_i, hold_state in enumerate(STATES):
        val_mask = (src_idx == hold_i) | (dst_idx == hold_i)
        train_mask = ~val_mask

        model = XGBRegressor(**params)
        model.fit(X[train_mask], y[train_mask])

        pred_train = model.predict(X[train_mask])
        pred_val = model.predict(X[val_mask])
        oof_pred[val_mask] = pred_val

        train_mean = float(np.mean(y[train_mask]))
        oof_baseline[val_mask] = train_mean

        rmse_train = _rmse(y[train_mask], pred_train)
        rmse_val = _rmse(y[val_mask], pred_val)
        fold_train_rmse.append(rmse_train)
        fold_rmse.append(rmse_val)

        if not fast_test_mode:
            print(
                f"{label} fold {hold_i + 1:02d}/{len(STATES)} holdout={hold_state}: "
                f"train_RMSE={rmse_train:.6f}, val_RMSE={rmse_val:.6f}"
            )

    rmse = _rmse(y, oof_pred)
    baseline_rmse = _rmse(y, oof_baseline)
    return {
        "pred": oof_pred,
        "baseline_pred": oof_baseline,
        "rmse": rmse,
        "baseline_rmse": baseline_rmse,
        "mean_train_rmse": float(np.mean(fold_train_rmse)),
        "mean_val_rmse": float(np.mean(fold_rmse)),
    }


def _state_loocv_regression(X, y, params, label):
    oof_pred = np.zeros_like(y, dtype=float)
    oof_baseline = np.zeros_like(y, dtype=float)
    fold_rmse = []
    fold_train_rmse = []
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"

    idx_all = np.arange(len(STATES), dtype=int)
    for hold_i, hold_state in enumerate(STATES):
        val_mask = idx_all == hold_i
        train_mask = ~val_mask

        model = XGBRegressor(**params)
        model.fit(X[train_mask], y[train_mask])

        pred_train = model.predict(X[train_mask])
        pred_val = model.predict(X[val_mask])
        oof_pred[val_mask] = pred_val

        train_mean = float(np.mean(y[train_mask]))
        oof_baseline[val_mask] = train_mean

        rmse_train = _rmse(y[train_mask], pred_train)
        rmse_val = _rmse(y[val_mask], pred_val)
        fold_train_rmse.append(rmse_train)
        fold_rmse.append(rmse_val)

        if not fast_test_mode:
            print(
                f"{label} fold {hold_i + 1:02d}/{len(STATES)} holdout={hold_state}: "
                f"train_RMSE={rmse_train:.6f}, val_RMSE={rmse_val:.6f}"
            )

    rmse = _rmse(y, oof_pred)
    baseline_rmse = _rmse(y, oof_baseline)
    return {
        "pred": oof_pred,
        "baseline_pred": oof_baseline,
        "rmse": rmse,
        "baseline_rmse": baseline_rmse,
        "mean_train_rmse": float(np.mean(fold_train_rmse)),
        "mean_val_rmse": float(np.mean(fold_rmse)),
    }


def _run_pairwise_with_overfit_guard(X, y, src_idx, dst_idx, base_params, label):
    metrics = _pairwise_loocv_regression(X, y, src_idx, dst_idx, base_params, label)
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"
    if fast_test_mode:
        return metrics
    if metrics["mean_train_rmse"] > 0 and metrics["mean_val_rmse"] > 2.0 * metrics["mean_train_rmse"]:
        tuned = dict(base_params)
        tuned["max_depth"] = max(2, int(tuned.get("max_depth", 4)) - 1)
        tuned["n_estimators"] = min(150, int(tuned.get("n_estimators", 200)))
        tuned["reg_alpha"] = float(tuned.get("reg_alpha", 0.1)) * 5.0
        tuned["reg_lambda"] = float(tuned.get("reg_lambda", 1.0)) * 2.0
        tuned["subsample"] = min(float(tuned.get("subsample", 0.8)), 0.7)
        tuned["colsample_bytree"] = min(float(tuned.get("colsample_bytree", 0.8)), 0.7)
        print(f"Warning: {label} shows overfitting (val/train > 2x). Retrying with stronger regularization.")
        metrics = _pairwise_loocv_regression(X, y, src_idx, dst_idx, tuned, f"{label} [retuned]")
    return metrics


def _run_state_with_overfit_guard(X, y, base_params, label):
    metrics = _state_loocv_regression(X, y, base_params, label)
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"
    if fast_test_mode:
        return metrics
    if metrics["mean_train_rmse"] > 0 and metrics["mean_val_rmse"] > 2.0 * metrics["mean_train_rmse"]:
        tuned = dict(base_params)
        tuned["max_depth"] = max(1, int(tuned.get("max_depth", 2)) - 1)
        tuned["n_estimators"] = min(120, int(tuned.get("n_estimators", 200)))
        tuned["reg_alpha"] = float(tuned.get("reg_alpha", 1.0)) * 2.0
        tuned["reg_lambda"] = float(tuned.get("reg_lambda", 5.0)) * 2.0
        tuned["subsample"] = min(float(tuned.get("subsample", 0.8)), 0.7)
        tuned["colsample_bytree"] = min(float(tuned.get("colsample_bytree", 0.8)), 0.7)
        print(f"Warning: {label} shows overfitting (val/train > 2x). Retrying with stronger regularization.")
        metrics = _state_loocv_regression(X, y, tuned, f"{label} [retuned]")
    return metrics


def xgb_compute_m2(base_dir, emission_2022_map):
    base_dir = Path(base_dir)
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"
    winds, months_of_year, winter_idx, summer_idx = _read_era5_winds(base_dir)
    n = len(STATES)

    norm_weight_target, confidence_target, weight_winter, weight_summer = _compute_deterministic_m2_targets(
        winds,
        months_of_year,
        winter_idx,
        summer_idx,
    )

    corridor_map = _build_corridor_conf_map()
    rows = []
    src_idx = []
    dst_idx = []
    y_transport = []
    y_conf = []

    for i, src in enumerate(STATES):
        for j, dst in enumerate(STATES):
            if i == j:
                continue

            lat1, lon1 = CENTROIDS[src]
            lat2, lon2 = CENTROIDS[dst]
            bearing = bearing_degrees(lat1, lon1, lat2, lon2)
            distance_km = float(geodesic((lat1, lon1), (lat2, lon2)).km)

            src_arch = archetype_for_state(src)
            dst_arch = archetype_for_state(dst)
            known_conf = float(corridor_map.get((src, dst), 0.0))

            row = [
                float(bearing),
                float(distance_km),
                float(winds[src]["mean_speed"]),
                float(winds[src]["mean_dir"]),
                float(winds[src]["dir_circ_std_deg"]),
                float(winds[src]["winter_mean_speed"]),
                float(winds[src]["winter_mean_dir"]),
                float(winds[src]["summer_mean_speed"]),
                float(winds[src]["summer_mean_dir"]),
                float(circular_diff_deg(winds[src]["mean_dir"], bearing)),
                float(STATE_AREA_KM2[src] / max(STATE_AREA_KM2[dst], EPS)),
                float(emission_2022_map[src] / (emission_2022_map[dst] + 1e-9)),
                float(src_arch == "F"),
                float(src_arch == "I"),
                float(src_arch == "M"),
                float(dst_arch == "F"),
                float(dst_arch == "I"),
                float(dst_arch == "M"),
                float((src, dst) in corridor_map),
                float(known_conf),
            ]

            rows.append(row)
            src_idx.append(i)
            dst_idx.append(j)
            y_transport.append(float(norm_weight_target[i, j]))
            y_conf.append(float(confidence_target[i, j]))

    X = np.asarray(rows, dtype=float)
    src_idx = np.asarray(src_idx, dtype=int)
    dst_idx = np.asarray(dst_idx, dtype=int)
    y_transport = np.asarray(y_transport, dtype=float)
    y_conf = np.asarray(y_conf, dtype=float)

    transport_params = dict(XGB_DEFAULT_PARAMS)
    transport_params["n_estimators"] = min(int(transport_params["n_estimators"]), 300)
    if fast_test_mode:
        transport_params["n_estimators"] = min(int(transport_params["n_estimators"]), 30)
    transport_metrics = _run_pairwise_with_overfit_guard(
        X,
        y_transport,
        src_idx,
        dst_idx,
        transport_params,
        "XGB_transport",
    )

    conf_params = dict(XGB_DEFAULT_PARAMS)
    if fast_test_mode:
        conf_params["n_estimators"] = min(int(conf_params["n_estimators"]), 30)
    conf_metrics = _run_pairwise_with_overfit_guard(
        X,
        y_conf,
        src_idx,
        dst_idx,
        conf_params,
        "XGB_confidence",
    )

    norm_weight_pred = np.zeros((n, n), dtype=float)
    confidence_pred = np.zeros((n, n), dtype=float)

    for k in range(len(src_idx)):
        i = int(src_idx[k])
        j = int(dst_idx[k])
        norm_weight_pred[i, j] = max(0.0, float(transport_metrics["pred"][k]))
        confidence_pred[i, j] = clip01(float(conf_metrics["pred"][k]))

    for i in range(n):
        row_sum = float(np.sum(norm_weight_pred[i, :]) - norm_weight_pred[i, i])
        if row_sum > EPS:
            for j in range(n):
                if i != j:
                    norm_weight_pred[i, j] = norm_weight_pred[i, j] / row_sum
        else:
            fallback = np.maximum(norm_weight_target[i, :], 0.0)
            fallback[i] = 0.0
            fallback_sum = float(np.sum(fallback))
            if fallback_sum > EPS:
                norm_weight_pred[i, :] = fallback / fallback_sum
            else:
                norm_weight_pred[i, :] = 0.0
                norm_weight_pred[i, np.arange(n) != i] = 1.0 / (n - 1)

    for src, dst, _months, corr_conf in KNOWN_CORRIDORS:
        i = STATES.index(src)
        j = STATES.index(dst)
        confidence_pred[i, j] = max(float(confidence_pred[i, j]), float(corr_conf))

    diagonal_frac = {
        state: STATE_AREA_KM2[state] / (STATE_AREA_KM2[state] + 50000.0)
        for state in STATES
    }

    M = np.zeros((n, n), dtype=float)
    for i, src in enumerate(STATES):
        emission_mt = float(emission_2022_map[src])
        diag_f = float(diagonal_frac[src])
        M[i, i] = emission_mt * diag_f
        for j in range(n):
            if i == j:
                continue
            M[i, j] = emission_mt * (1.0 - diag_f) * norm_weight_pred[i, j]

    for i, src in enumerate(STATES):
        target_row_sum = float(emission_2022_map[src])
        row_sum = float(np.sum(M[i, :]))
        if row_sum > EPS:
            M[i, :] *= target_row_sum / row_sum
        else:
            M[i, i] = target_row_sum

    emission_vec = np.array([float(emission_2022_map[s]) for s in STATES], dtype=float)
    row_sums = np.sum(M, axis=1)
    max_row_err = float(np.max(np.abs(row_sums - emission_vec)))
    if max_row_err > 1e-6:
        raise AssertionError(
            f"M2 row conservation failed: max row absolute error {max_row_err:.6e} exceeds 1e-6"
        )

    own_emission_mt = {state: float(M[idx, idx]) for idx, state in enumerate(STATES)}
    exported_harm_mt = {
        state: float(np.sum(M[idx, :]) - M[idx, idx])
        for idx, state in enumerate(STATES)
    }
    received_credit_mt = {
        state: float(np.sum(M[:, idx]) - M[idx, idx])
        for idx, state in enumerate(STATES)
    }

    baseline_transport = float(transport_metrics["baseline_rmse"])
    baseline_conf = float(conf_metrics["baseline_rmse"])
    transport_rmse = float(transport_metrics["rmse"])
    conf_rmse = float(conf_metrics["rmse"])

    if transport_rmse > baseline_transport:
        print("Warning: XGB_transport LOOCV RMSE is worse than the mean baseline.")
    if conf_rmse > baseline_conf:
        print("Warning: XGB_confidence LOOCV RMSE is worse than the mean baseline.")

    improvement = 0.0
    if baseline_transport > EPS:
        improvement = 100.0 * (baseline_transport - transport_rmse) / baseline_transport

    print("\n=== XGBoost M2 Transport Model ===")
    print(f"LOOCV RMSE (norm_weight): {transport_rmse:.6f}")
    print(f"Baseline RMSE (mean predictor): {baseline_transport:.6f}")
    print(f"Improvement over baseline: {improvement:.1f}%")
    print(f"Row conservation max error: {max_row_err:.2e}")

    print("\n=== XGBoost M2 Confidence Model ===")
    print(f"LOOCV RMSE (confidence): {conf_rmse:.6f}")
    print(f"Baseline RMSE: {baseline_conf:.6f}")

    return (
        M,
        confidence_pred,
        diagonal_frac,
        own_emission_mt,
        exported_harm_mt,
        received_credit_mt,
        weight_winter,
        weight_summer,
    )


def _build_m3_feature_target_table(absorption_map, panel_df, emission_2022_map):
    panel_df = panel_df.copy()
    panel_df["year"] = panel_df["year"].astype(int)

    panel_2019 = panel_df[panel_df["year"] == 2019][["state", "total_emission_mt"]]
    e2019_map = dict(zip(panel_2019["state"], panel_2019["total_emission_mt"]))

    max_absorption = max(float(absorption_map[s]) for s in STATES)

    rows = []
    for state in STATES:
        state_panel = panel_df[panel_df["state"] == state].sort_values("year")

        e2019 = float(e2019_map.get(state, 0.0))
        e2022_panel = state_panel[state_panel["year"] == 2022]["total_emission_mt"]
        e2022 = float(e2022_panel.iloc[0]) if not e2022_panel.empty else 0.0

        if e2019 > 0:
            emission_delta = (e2022 - e2019) / e2019
            s1 = clip01(1.0 - (emission_delta / 0.05))
        else:
            emission_delta = 0.0
            s1 = 0.5

        s2 = float(get_re_fraction(state))
        s3 = clip01(float(absorption_map[state]) / max_absorption)
        s4 = clip01(0.5 - (float(get_aqi_delta(state)) / 40.0))

        if not state_panel.empty:
            e_max = float(state_panel["total_emission_mt"].max())
            e_min = float(state_panel["total_emission_mt"].min())
            years = state_panel["year"].to_numpy(dtype=float)
            vals = state_panel["total_emission_mt"].to_numpy(dtype=float)
            if len(years) >= 2:
                slope = float(np.polyfit(years, vals, 1)[0])
            else:
                slope = 0.0
        else:
            e_max = 1.0
            e_min = 0.0
            slope = 0.0

        e_max_safe = e_max if e_max > 0 else 1.0
        s5 = clip01(1.0 - (e2022 / (e_max_safe * 1.05)))

        archetype = archetype_for_state(state)
        w = WEIGHTS[archetype]
        weighted_average = (
            w["S1"] * s1
            + w["S2"] * s2
            + w["S3"] * s3
            + w["S4"] * s4
            + w["S5"] * s5
        )
        effort_multiplier = float(np.clip(0.5 + 1.5 * weighted_average, 0.5, 2.0))

        e2022_feature = float(emission_2022_map[state])
        absorption = float(absorption_map[state])

        row = {
            "state": state,
            "archetype": archetype,
            "emission_2022_mt": e2022_feature,
            "emission_2019_mt": e2019,
            "emission_delta": emission_delta,
            "absorption_mt": absorption,
            "absorption_to_emission_ratio": float(absorption / (e2022_feature + 1e-9)),
            "re_fraction": s2,
            "aqi_delta": float(get_aqi_delta(state)),
            "e_max": e_max,
            "e_min": e_min,
            "emission_trend_slope": slope,
            "is_F": float(archetype == "F"),
            "is_I": float(archetype == "I"),
            "is_M": float(archetype == "M"),
            "state_area_km2": float(STATE_AREA_KM2[state]),
            "S1": float(s1),
            "S2": float(s2),
            "S3": float(s3),
            "S4": float(s4),
            "S5": float(s5),
            "effort_target": effort_multiplier,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def xgb_compute_m3(absorption_map, panel_df, emission_2022_map):
    fast_test_mode = os.environ.get("CARBONVAYU_FAST_TEST", "0") == "1"
    df = _build_m3_feature_target_table(absorption_map, panel_df, emission_2022_map)
    feature_cols = [
        "emission_2022_mt",
        "emission_2019_mt",
        "emission_delta",
        "absorption_mt",
        "absorption_to_emission_ratio",
        "re_fraction",
        "aqi_delta",
        "e_max",
        "e_min",
        "emission_trend_slope",
        "is_F",
        "is_I",
        "is_M",
        "state_area_km2",
    ]

    X = df[feature_cols].to_numpy(dtype=float)

    preds = {}
    metrics_by_signal = {}
    for signal in ["S1", "S2", "S3", "S4", "S5"]:
        y = df[signal].to_numpy(dtype=float)
        m3_params = dict(XGB_M3_PARAMS)
        if fast_test_mode:
            m3_params["n_estimators"] = min(int(m3_params["n_estimators"]), 30)
        metrics = _run_state_with_overfit_guard(X, y, m3_params, f"XGB_{signal}")
        pred = np.clip(metrics["pred"], 0.0, 1.0)

        preds[signal] = pred
        metrics_by_signal[signal] = metrics

        if metrics["rmse"] > metrics["baseline_rmse"]:
            print(f"Warning: {signal} LOOCV RMSE is worse than the mean baseline.")

    effort_pred = np.zeros(len(STATES), dtype=float)
    effort_true = df["effort_target"].to_numpy(dtype=float)
    effort_baseline_pred = np.zeros(len(STATES), dtype=float)

    for i, state in enumerate(STATES):
        archetype = archetype_for_state(state)
        w = WEIGHTS[archetype]
        weighted_average = (
            w["S1"] * float(preds["S1"][i])
            + w["S2"] * float(preds["S2"][i])
            + w["S3"] * float(preds["S3"][i])
            + w["S4"] * float(preds["S4"][i])
            + w["S5"] * float(preds["S5"][i])
        )
        effort_pred[i] = float(np.clip(0.5 + 1.5 * weighted_average, 0.5, 2.0))

        train_mask = np.arange(len(STATES), dtype=int) != i
        effort_baseline_pred[i] = float(np.mean(effort_true[train_mask]))

        fold_rmse = float(abs(effort_true[i] - effort_pred[i]))
        fold_baseline_rmse = float(abs(effort_true[i] - effort_baseline_pred[i]))
        if not fast_test_mode:
            print(
                f"effort_multiplier fold {i + 1:02d}/{len(STATES)} holdout={state}: "
                f"val_RMSE={fold_rmse:.6f}, baseline={fold_baseline_rmse:.6f}"
            )

    effort_rmse = _rmse(effort_true, effort_pred)
    effort_baseline_rmse = _rmse(effort_true, effort_baseline_pred)

    if effort_rmse > effort_baseline_rmse:
        print("Warning: effort_multiplier LOOCV RMSE is worse than the mean baseline.")

    print("\n=== XGBoost M3 S-Score Models ===")
    for signal in ["S1", "S2", "S3", "S4", "S5"]:
        sig_rmse = float(metrics_by_signal[signal]["rmse"])
        sig_base = float(metrics_by_signal[signal]["baseline_rmse"])
        print(f"{signal} LOOCV RMSE: {sig_rmse:.4f} | Baseline: {sig_base:.4f}")
    print(f"effort_multiplier LOOCV RMSE: {effort_rmse:.4f} | Baseline: {effort_baseline_rmse:.4f}")

    out = pd.DataFrame(
        {
            "state": STATES,
            "S1": preds["S1"],
            "S2": preds["S2"],
            "S3": preds["S3"],
            "S4": preds["S4"],
            "S5": preds["S5"],
            "archetype": [archetype_for_state(s) for s in STATES],
            "effort_multiplier": effort_pred,
        }
    )

    in_range = bool(((out["effort_multiplier"] >= 0.5) & (out["effort_multiplier"] <= 2.0)).all())
    if not in_range:
        observed_min = float(out["effort_multiplier"].min())
        observed_max = float(out["effort_multiplier"].max())
        raise AssertionError(
            f"M3 effort multiplier out of range: observed [{observed_min:.6f}, {observed_max:.6f}], expected [0.5, 2.0]"
        )

    return out[["state", "S1", "S2", "S3", "S4", "S5", "archetype", "effort_multiplier"]]


def _write_synthetic_era5(base_dir: Path, seed: int = 42):
    rng = np.random.default_rng(seed)

    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    lats = np.array(sorted({coords[0] for coords in CENTROIDS.values()}), dtype=float)
    lons = np.array(sorted({coords[1] for coords in CENTROIDS.values()}), dtype=float)
    times = pd.date_range("2022-01-01", periods=24, freq="MS")

    shape = (len(times), len(lats), len(lons))
    u = rng.normal(loc=0.0, scale=4.0, size=shape)
    v = rng.normal(loc=0.0, scale=4.0, size=shape)

    ds = xr.Dataset(
        {
            "u": (("valid_time", "latitude", "longitude"), u),
            "v": (("valid_time", "latitude", "longitude"), v),
        },
        coords={
            "valid_time": times,
            "latitude": lats,
            "longitude": lons,
        },
    )
    ds.to_netcdf(data_dir / "era5.nc")
    ds.close()


def _build_synthetic_m3_inputs(seed: int = 42):
    rng = np.random.default_rng(seed)

    absorption_map = {
        state: float(rng.uniform(50.0, 350.0))
        for state in STATES
    }

    panel_rows = []
    years = list(range(2015, 2023))
    for state in STATES:
        base = float(rng.uniform(80.0, 600.0))
        slope = float(rng.uniform(-12.0, 12.0))
        noise = rng.normal(0.0, 8.0, size=len(years))
        vals = np.maximum(5.0, base + slope * (np.array(years) - years[0]) + noise)
        for yr, val in zip(years, vals):
            panel_rows.append(
                {
                    "state": state,
                    "year": int(yr),
                    "total_emission_mt": float(val),
                }
            )

    panel_df = pd.DataFrame(panel_rows)
    emission_2022_map = {
        state: float(panel_df[(panel_df["state"] == state) & (panel_df["year"] == 2022)]["total_emission_mt"].iloc[0])
        for state in STATES
    }

    return absorption_map, panel_df, emission_2022_map


def run_smoke_test():
    start = time.perf_counter()
    prev_fast_flag = os.environ.get("CARBONVAYU_FAST_TEST")
    os.environ["CARBONVAYU_FAST_TEST"] = "1"

    try:
        with tempfile.TemporaryDirectory(prefix="carbonvayu_xgb_test_") as tmpdir:
            base_dir = Path(tmpdir)
            _write_synthetic_era5(base_dir)

            absorption_map, panel_df, emission_2022_map = _build_synthetic_m3_inputs()

            m2_start = time.perf_counter()
            m2_out = xgb_compute_m2(base_dir, emission_2022_map)
            m2_elapsed = time.perf_counter() - m2_start

            M, confidence, diagonal_frac, own_emission_mt, exported_harm_mt, received_credit_mt, weight_winter, weight_summer = m2_out

            n = len(STATES)
            assert isinstance(M, np.ndarray) and M.shape == (n, n), "M2 matrix shape mismatch"
            assert isinstance(confidence, np.ndarray) and confidence.shape == (n, n), "M2 confidence shape mismatch"
            assert isinstance(weight_winter, np.ndarray) and weight_winter.shape == (n, n), "M2 winter weights shape mismatch"
            assert isinstance(weight_summer, np.ndarray) and weight_summer.shape == (n, n), "M2 summer weights shape mismatch"
            assert len(diagonal_frac) == n and len(own_emission_mt) == n, "M2 derived dict lengths mismatch"
            assert len(exported_harm_mt) == n and len(received_credit_mt) == n, "M2 derived dict lengths mismatch"

            emission_vec = np.array([float(emission_2022_map[s]) for s in STATES], dtype=float)
            row_sums = np.sum(M, axis=1)
            max_row_err = float(np.max(np.abs(row_sums - emission_vec)))
            assert max_row_err <= 1e-6, f"Smoke test M2 conservation failed: max row error {max_row_err:.3e}"

            m3_start = time.perf_counter()
            m3_df = xgb_compute_m3(absorption_map, panel_df, emission_2022_map)
            m3_elapsed = time.perf_counter() - m3_start

            expected_cols = ["state", "S1", "S2", "S3", "S4", "S5", "archetype", "effort_multiplier"]
            assert list(m3_df.columns) == expected_cols, "M3 output schema mismatch"
            assert len(m3_df) == n, "M3 state row count mismatch"
            assert bool(((m3_df["effort_multiplier"] >= 0.5) & (m3_df["effort_multiplier"] <= 2.0)).all()), (
                "M3 effort multiplier must be within [0.5, 2.0]"
            )
    finally:
        if prev_fast_flag is None:
            os.environ.pop("CARBONVAYU_FAST_TEST", None)
        else:
            os.environ["CARBONVAYU_FAST_TEST"] = prev_fast_flag

    total_elapsed = time.perf_counter() - start
    assert total_elapsed < 60.0, f"Smoke test exceeded 60s: {total_elapsed:.2f}s"

    print("\n=== Smoke Test Passed ===")
    print(f"M2 runtime: {m2_elapsed:.2f}s")
    print(f"M3 runtime: {m3_elapsed:.2f}s")
    print(f"Total runtime: {total_elapsed:.2f}s")


def _parse_args():
    parser = argparse.ArgumentParser(description="XGBoost replacement for CarbonVayu M2 and M3 modules")
    parser.add_argument("--test", action="store_true", help="Run synthetic smoke tests")
    return parser.parse_args()


def _run_local_demo():
    base_dir = Path(__file__).resolve().parent
    absorption_map, panel_df, emission_2022_map = load_inputs(base_dir)

    _ = xgb_compute_m2(base_dir, emission_2022_map)
    _ = xgb_compute_m3(absorption_map, panel_df, emission_2022_map)


if __name__ == "__main__":
    args = _parse_args()
    if args.test:
        run_smoke_test()
    else:
        _run_local_demo()
