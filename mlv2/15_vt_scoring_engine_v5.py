"""
15_vt_scoring_engine_v5.py -- CarbonVayu mlv3 Vaayu Token (VT) Economy Engine (v5)
Principle:
  VT = accountability for inter-state harm exported to others (55%)
     + credit for clean-energy sustainability investment (30%)
     + credit for matched-station emissions progress (15%).
  Uses the transport matrix strictly for inter-state transport (no diagonal own-node
  attribution, no observed PM2.5 levels or trends inside the VT score).

Outputs (never overwrites v3 or v4):
  results/v3_5yr/vt_economy_v5/
    - vt_constants_v5.json
    - VT_scores_v5_final.csv
    - fine_ledger.csv
    - fine_claims_v5.csv
    - attribution_network_v5.csv
    - M2_matrix_v5_ugm3.csv
    - M2_confidence_v5_boot.csv
    - transfer_rates_v5_per_edgar.csv
"""
import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from scipy.optimize import lsq_linear
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

OUT = Path("results/v3_5yr/vt_economy_v5")
CONST_PATH = OUT / "vt_constants_v5.json"
CACHE = Path("results/v3_5yr/diagnostics/stage1_loyo_cache.parquet")

N_BOOT = 300
LOW_N_THRESHOLD = 5
HARM_FLOOR = 0.40  # ug/m3 screening floor (1% of India's 40 ug/m3 annual PM2.5 NAAQS)

W_EXPORT = 0.55
W_PROGRESS = 0.15
W_RE = 0.30

# Fallback Census 2011 projected to 2022 (millions) if data/state_population_2022.csv is absent
FALLBACK_POP_2022 = {
    "Andhra Pradesh": 53.03,
    "Bihar": 125.57,
    "Chandigarh": 1.22,
    "Chhattisgarh": 29.88,
    "Delhi": 21.05,
    "Gujarat": 70.85,
    "Haryana": 29.93,
    "Himachal Pradesh": 7.43,
    "Jharkhand": 39.21,
    "Karnataka": 67.38,
    "Kerala": 35.72,
    "Madhya Pradesh": 85.79,
    "Maharashtra": 125.81,
    "Odisha": 46.12,
    "Puducherry": 1.63,
    "Punjab": 30.56,
    "Rajasthan": 80.38,
    "Tamil Nadu": 76.76,
    "Telangana": 37.93,
    "Uttar Pradesh": 234.67,
    "Uttarakhand": 11.55,
    "West Bengal": 98.76,
}

# Fallback RE share (2022) if data/re_fraction_2022.csv is absent
FALLBACK_RE_2022 = {
    "Karnataka": 0.72,
    "Rajasthan": 0.68,
    "Gujarat": 0.65,
    "Tamil Nadu": 0.62,
    "Andhra Pradesh": 0.58,
    "Kerala": 0.55,
    "Telangana": 0.50,
    "Madhya Pradesh": 0.45,
    "Maharashtra": 0.42,
    "Uttar Pradesh": 0.32,
    "Haryana": 0.30,
    "Punjab": 0.28,
    "Chhattisgarh": 0.22,
    "Odisha": 0.20,
    "Puducherry": 0.20,
    "West Bengal": 0.18,
    "Bihar": 0.15,
    "Chandigarh": 0.15,
    "Jharkhand": 0.12,
    "Delhi": 0.10,
    "Uttarakhand": 0.85,
    "Himachal Pradesh": 0.90,
}

WEATHER = [
    "blh_mean", "blh_min", "t2m_c", "rh_pct", "u10", "v10", "wspd10",
    "precip_mm", "u925", "v925", "wspd925", "u850", "v850", "wspd850",
]
CALENDAR = ["doy_sin", "doy_cos", "day_of_week", "is_weekend"]
LOCAL = [
    "edgar_pm25_agriculture", "edgar_pm25_buildings", "edgar_pm25_ind_combustion",
    "edgar_pm25_power_industry", "edgar_pm25_transport", "edgar_pm25_waste",
    "edgar_pm25_total", "edgar_bc_total", "edgar_co_total", "edgar_nh3_total",
    "edgar_nox_total", "edgar_so2_total",
]
BINS = ["0_24h", "24_48h", "48_72h"]
SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]


def parse_args():
    p = argparse.ArgumentParser(description="CarbonVayu VT v5 Scoring Engine")
    p.add_argument(
        "--recompute-constants",
        action="store_true",
        help="Force Pass 1 recomputation and overwrite vt_constants_v5.json.",
    )
    p.add_argument(
        "--n-boot",
        type=int,
        default=N_BOOT,
        help="Number of calendar-week block bootstrap replicates (default: 300).",
    )
    return p.parse_args()


def to_mono_design(Xe: np.ndarray) -> np.ndarray:
    Xc = np.zeros_like(Xe)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        Xc[:, c0] = Xe[:, c0]
        Xc[:, c1] = Xe[:, c0] + Xe[:, c1]
        Xc[:, c2] = Xe[:, c0] + Xe[:, c1] + Xe[:, c2]
    return np.hstack([np.ones((len(Xc), 1)), Xc])


def unpack_mono(sol_betas: np.ndarray) -> np.ndarray:
    b = np.zeros(9, dtype=np.float64)
    for k in range(3):
        c0, c1, c2 = 3 * k, 3 * k + 1, 3 * k + 2
        b[c2] = sol_betas[c2]
        b[c1] = sol_betas[c2] + sol_betas[c1]
        b[c0] = sol_betas[c2] + sol_betas[c1] + sol_betas[c0]
    return b


def solve_mono(AtA: np.ndarray, Aty: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.clip(np.diag(AtA), 1e-12, None))
    M = AtA / np.outer(d, d)
    L = np.linalg.cholesky(M + 1e-10 * np.eye(len(M)))
    z = solve_triangular(L, Aty / d, lower=True)
    sol = lsq_linear(L.T, z, bounds=(np.r_[-np.inf, np.zeros(9)], np.inf)).x / d
    return unpack_mono(sol[1:])


def solve_unconstrained(AtA: np.ndarray, Aty: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.clip(np.diag(AtA), 1e-12, None))
    M = AtA / np.outer(d, d)
    L = np.linalg.cholesky(M + 1e-10 * np.eye(len(M)))
    z = solve_triangular(L, Aty / d, lower=True)
    sol = lsq_linear(L.T, z, bounds=(np.r_[-np.inf, np.zeros(9)], np.inf)).x / d
    return np.clip(sol[1:], 0.0, None)


def load_population_2022(states: list[str]) -> np.ndarray:
    candidates = [
        Path("data/state_population_2022.csv"),
        Path("data/pop_2022.csv"),
    ]
    pop_map = dict(FALLBACK_POP_2022)
    for p in candidates:
        if p.exists():
            pdf = pd.read_csv(p)
            st_col = "state" if "state" in pdf.columns else pdf.columns[0]
            val_col = next(
                (c for c in ["pop_2022", "population_2022", "population", "pop"] if c in pdf.columns),
                pdf.columns[1],
            )
            for _, row in pdf.iterrows():
                pop_map[str(row[st_col]).strip()] = float(row[val_col])
            break
    vals = []
    for s in states:
        if s in pop_map and np.isfinite(pop_map[s]) and pop_map[s] > 0:
            vals.append(float(pop_map[s]))
        else:
            vals.append(float(np.median(list(pop_map.values()))))
    return np.asarray(vals, dtype=np.float64)


def load_re_fraction_2022(states: list[str]) -> tuple[np.ndarray, np.ndarray]:
    re_csv = Path("data/re_fraction_2022.csv")
    re_map = dict(FALLBACK_RE_2022)
    csv_states = set()
    if re_csv.exists():
        rdf = pd.read_csv(re_csv)
        st_col = "state" if "state" in rdf.columns else rdf.columns[0]
        val_col = next(
            (c for c in ["re_fraction", "re_share", "renewable_fraction"] if c in rdf.columns),
            rdf.columns[1],
        )
        for _, row in rdf.iterrows():
            st_name = str(row[st_col]).strip()
            val = float(row[val_col])
            if np.isfinite(val):
                re_map[st_name] = float(np.clip(val, 0.0, 1.0))
                csv_states.add(st_name)

    vals = np.zeros(len(states), dtype=np.float64)
    fallback_flags = np.zeros(len(states), dtype=bool)
    for i, s in enumerate(states):
        if s in re_map:
            vals[i] = float(np.clip(re_map[s], 0.0, 1.0))
            fallback_flags[i] = s not in csv_states
        else:
            vals[i] = 0.35
            fallback_flags[i] = True
    return vals, fallback_flags


def compute_matched_edgar_ratios(
    df: pd.DataFrame,
    states: list[str],
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """
    For each station present in both 2019 and 2022, compute ratio = edgar_pm25_total(2022) / edgar_pm25_total(2019).
    State ratio r_i = median of station ratios (or resampled stations if rng is provided).
    Empirical Bayes shrinkage toward national median r_nat with w = n / (n + 5).
    """
    d19 = df[df["year"] == 2019].groupby(["state", "location_id"])["edgar_pm25_total"].mean()
    d22 = df[df["year"] == 2022].groupby(["state", "location_id"])["edgar_pm25_total"].mean()

    raw_ratios = np.ones(len(states), dtype=np.float64)
    n_matched = np.zeros(len(states), dtype=int)

    for i, st in enumerate(states):
        s19 = d19.loc[st] if st in d19.index.get_level_values(0) else pd.Series(dtype=float)
        s22 = d22.loc[st] if st in d22.index.get_level_values(0) else pd.Series(dtype=float)
        common_locs = sorted(set(s19.index).intersection(set(s22.index)))
        valid_vals = []
        for loc in common_locs:
            v19, v22 = float(s19.loc[loc]), float(s22.loc[loc])
            if np.isfinite(v19) and v19 > 1e-12 and np.isfinite(v22) and v22 >= 0.0:
                valid_vals.append(v22 / v19)
        arr = np.asarray(valid_vals, dtype=np.float64)
        n_matched[i] = len(arr)
        if len(arr) > 0:
            draws = rng.choice(arr, size=len(arr), replace=True) if rng is not None else arr
            raw_ratios[i] = float(np.median(draws))
        else:
            raw_ratios[i] = np.nan

    obs_mask = np.isfinite(raw_ratios)
    r_nat = float(np.median(raw_ratios[obs_mask])) if np.any(obs_mask) else 1.0
    raw_filled = np.where(obs_mask, raw_ratios, r_nat)

    shrunk_ratios = np.zeros(len(states), dtype=np.float64)
    for i in range(len(states)):
        n_i = int(n_matched[i])
        w_i = n_i / (n_i + 5.0) if n_i > 0 else 0.0
        shrunk_ratios[i] = w_i * raw_filled[i] + (1.0 - w_i) * r_nat

    return raw_filled, shrunk_ratios, n_matched, (n_matched < LOW_N_THRESHOLD), r_nat


def compute_audit_metrics(df: pd.DataFrame, states: list[str], shrunk_ratios: np.ndarray) -> pd.DataFrame:
    """
    Audit columns (NOT used in VT score):
      - matched-station observed PM2.5 trend (deadbanded +/- 3 ug/m3)
      - NAAQS daily compliance rate (PM2.5 <= 60 ug/m3)
      - observed PM2.5 level (2022-2023)
      - audit_flag when EDGAR emission progress and observed matched PM2.5 trend diverge
    """
    rows = []
    for i, st in enumerate(states):
        sub = df[df["state"] == st]
        sb = sub[sub["year"].isin([2019, 2021])]
        sc = sub[sub["year"].isin([2022, 2023])]
        pm_curr = float(sc["pm25"].mean()) if not sc.empty else float(sub["pm25"].mean())
        common = sorted(set(sb["location_id"].unique()).intersection(set(sc["location_id"].unique())))
        if common:
            mb = sb[sb["location_id"].isin(common)].groupby("location_id")["pm25"].mean()
            mc = sc[sc["location_id"].isin(common)].groupby("location_id")["pm25"].mean()
            match_drop = float((mb - mc).mean())  # positive = observed PM2.5 fell
        else:
            match_drop = 0.0

        deadband_drop = float(np.sign(match_drop) * max(abs(match_drop) - 3.0, 0.0))
        naaqs_comp = float((sc["pm25"] <= 60.0).mean()) if not sc.empty else float((sub["pm25"] <= 60.0).mean())

        emi_improving = shrunk_ratios[i] < 0.99
        emi_worsening = shrunk_ratios[i] > 1.01
        pm_improving = deadband_drop > 0.0
        pm_worsening = deadband_drop < 0.0

        if emi_improving and pm_worsening:
            flag = "DIVERGENT_EMI_BETTER_PM_WORSE"
        elif emi_worsening and pm_improving:
            flag = "DIVERGENT_EMI_WORSE_PM_BETTER"
        else:
            flag = "ALIGNED_OR_NEUTRAL"

        rows.append({
            "state": st,
            "cpcb_match_drop_ugm3": match_drop,
            "cpcb_deadband_drop_ugm3": deadband_drop,
            "cpcb_naaqs_comp": naaqs_comp,
            "pm25_curr": pm_curr,
            "audit_flag": flag,
        })
    return pd.DataFrame(rows)


def compute_pillar_a_export(M_dom: np.ndarray, share: np.ndarray, x_med: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Pillar A (weight 0.55):
      Uses ONLY off-diagonal inter-state transport (never diagonal own-node).
      X_i = sum_{j != i} M_dom[i, j] * share[j]
      A_i = exp(-ln(2) * X_i / X_MED)
    """
    off = ~np.eye(M_dom.shape[0], dtype=bool)
    X = ((M_dom * off) * share[None, :]).sum(axis=1)
    A = np.exp(-np.log(2.0) * X / max(x_med, 1e-9))
    return X, A


def compute_pillar_b_progress(shrunk_ratios: np.ndarray, prog_scale: float) -> np.ndarray:
    """
    Pillar B (weight 0.15):
      P_i = clip(0.5 + (1 - r_i') / PROG_SCALE, 0, 1)
    """
    return np.clip(0.5 + (1.0 - shrunk_ratios) / max(prog_scale, 1e-6), 0.0, 1.0)


def raw_and_vt_from_pillars(
    A: np.ndarray, P: np.ndarray, C: np.ndarray, center: float, scale: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw = W_EXPORT * A + W_PROGRESS * P + W_RE * C
    z = (raw - center) / max(scale, 1e-9)
    vt = 500.0 + 200.0 * np.tanh(z / 2.0)
    return raw, z, vt


def evaluate_fines(
    states: list[str],
    pop: np.ndarray,
    M_mono: np.ndarray,
    M_uncon: np.ndarray,
    C_mat: np.ndarray,
    jb_lo_mono: np.ndarray,
    jb_lo_uncon: np.ndarray,
    d_ref: float | None,
) -> tuple[list[dict], float]:
    """
    Zero-sum fine eligibility:
      - C_ij > 0.75 and CI_low > 0 under BOTH monotone and unconstrained specs
      - harm >= 0.4 ug/m3
      - D_ij = M[i, j] * pop[j] * C_ij
      - fine_pts = 20 + 130 * (1 - exp(-D_ij / D_REF))
    """
    n_st = len(states)
    raw_claims = []
    for i in range(n_st):
        for j in range(i + 1, n_st):
            for u, v in [(i, j), (j, i)]:
                harm_m = float(M_mono[u, v])
                harm_u = float(M_uncon[u, v])
                conf = float(C_mat[u, v])
                if (
                    conf > 0.75
                    and float(jb_lo_mono[u, v]) > 0.0
                    and float(jb_lo_uncon[u, v]) > 0.0
                    and harm_m >= HARM_FLOOR
                    and harm_u >= HARM_FLOOR
                ):
                    d_ij = harm_m * float(pop[v]) * conf
                    raw_claims.append({
                        "def_idx": u,
                        "clm_idx": v,
                        "defendant": states[u],
                        "claimant": states[v],
                        "harm_ugm3": harm_m,
                        "harm_uncon_ugm3": harm_u,
                        "harm_ci_low": float(jb_lo_mono[u, v]),
                        "confidence": conf,
                        "D_ij": d_ij,
                        "fine_vt_units": harm_m * conf,
                    })

    if not raw_claims:
        return [], (float(d_ref) if d_ref is not None else 1.0)

    d_vals = np.asarray([c["D_ij"] for c in raw_claims], dtype=np.float64)
    ref = float(d_ref) if (d_ref is not None and d_ref > 1e-9) else max(float(np.median(d_vals)), 1e-9)

    for c in raw_claims:
        pts = 20.0 + 130.0 * (1.0 - np.exp(-c["D_ij"] / ref))
        c["fine_vt_points"] = round(float(pts), 3)

    raw_claims.sort(key=lambda r: r["fine_vt_points"], reverse=True)
    return raw_claims, ref


def settle_in_z_space(
    n_st: int,
    z_base: np.ndarray,
    claims: list[dict],
    fine_to_z: float | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    owed = np.zeros(n_st, dtype=np.float64)
    received = np.zeros(n_st, dtype=np.float64)
    for c in claims:
        pts = float(c["fine_vt_points"])
        owed[c["def_idx"]] += pts
        received[c["clm_idx"]] += pts

    net_transfer = owed - received  # positive => net payer (penalty)
    max_abs_net = float(np.max(np.abs(net_transfer))) if len(net_transfer) > 0 else 0.0
    scale_fz = (
        float(fine_to_z)
        if (fine_to_z is not None and fine_to_z > 1e-9)
        else max(max_abs_net, 1.0)
    )
    z_settled = z_base - (net_transfer / scale_fz)
    vt_settled = 500.0 + 200.0 * np.tanh(z_settled / 2.0)
    return vt_settled, owed, received, scale_fz


def run_bootstrap_and_transport(
    df: pd.DataFrame,
    exp: pd.DataFrame,
    nodes: list[str],
    states: list[str],
    ind_idx: list[int],
    ext_idx: list[int],
    X_base: np.ndarray,
    resid_full: np.ndarray,
    n_boot: int,
    seed: int = 42,
):
    n_st = len(states)
    A_mono = to_mono_design(X_base)
    ub_yw, inv_yw = np.unique(df["yw"].values, return_inverse=True)
    n_weeks = len(ub_yw)

    AtA_w = np.zeros((n_weeks, 10, 10), dtype=np.float64)
    Aty_w = np.zeros((n_weeks, 10), dtype=np.float64)
    for w in range(n_weeks):
        idx = np.where(inv_yw == w)[0]
        Aw = A_mono[idx]
        AtA_w[w] = Aw.T @ Aw
        Aty_w[w] = Aw.T @ resid_full[idx]

    b_mono_pt = solve_mono(AtA_w.sum(axis=0), Aty_w.sum(axis=0))
    b_uncon_pt = solve_unconstrained(AtA_w.sum(axis=0), Aty_w.sum(axis=0))

    w_sc_idx = np.where(np.isin(ub_yw // 100, [2022, 2023]))[0]
    E_w_sum = np.zeros((len(w_sc_idx), n_st, len(nodes), 9), dtype=np.float64)
    E_w_cnt = np.zeros((len(w_sc_idx), n_st), dtype=np.float64)
    exp_cols = [exp[f"exp_{n}_{sec}_{b}"].values for n in nodes for sec, b in SB]
    exp_stack = np.column_stack(exp_cols).reshape(len(exp), len(nodes), 9)

    for wi, w in enumerate(w_sc_idx):
        w_rows = np.where(inv_yw == w)[0]
        st_w = df["state"].values[w_rows]
        for r, st in enumerate(states):
            rm = w_rows[st_w == st]
            if len(rm) == 0:
                continue
            E_w_cnt[wi, r] = len(rm)
            E_w_sum[wi, r] = exp_stack[rm].sum(axis=0)

    E_score_pt = E_w_sum.sum(axis=0) / np.maximum(E_w_cnt.sum(axis=0)[:, None, None], 1.0)
    T_mono_pt = np.einsum("rnj,j->nr", E_score_pt, b_mono_pt)
    T_uncon_pt = np.einsum("rnj,j->nr", E_score_pt, b_uncon_pt)

    M_mono_pt = T_mono_pt[ind_idx, :]
    M_uncon_pt = T_uncon_pt[ind_idx, :]
    ext_rec_pt = T_mono_pt[ext_idx, :].sum(axis=0)

    rng = np.random.default_rng(seed)
    M_mono_boot = np.zeros((n_boot, n_st, n_st), dtype=np.float64)
    M_uncon_boot = np.zeros((n_boot, n_st, n_st), dtype=np.float64)
    ext_rec_boot = np.zeros((n_boot, n_st), dtype=np.float64)
    r_shrunk_boot = np.zeros((n_boot, n_st), dtype=np.float64)

    for k in range(n_boot):
        cnt_all = np.bincount(rng.integers(0, n_weeks, n_weeks), minlength=n_weeks).astype(float)
        bk_m = solve_mono(np.tensordot(cnt_all, AtA_w, 1), cnt_all @ Aty_w)
        bk_u = solve_unconstrained(np.tensordot(cnt_all, AtA_w, 1), cnt_all @ Aty_w)

        cnt_sc = cnt_all[w_sc_idx]
        tot_cnt = np.maximum(cnt_sc @ E_w_cnt, 1.0)
        E_k = np.tensordot(cnt_sc, E_w_sum, 1) / tot_cnt[:, None, None]

        Tk_m = np.einsum("rnj,j->nr", E_k, bk_m)
        Tk_u = np.einsum("rnj,j->nr", E_k, bk_u)
        M_mono_boot[k] = Tk_m[ind_idx, :]
        M_uncon_boot[k] = Tk_u[ind_idx, :]
        ext_rec_boot[k] = Tk_m[ext_idx, :].sum(axis=0)

        _, r_shrunk_k, _, _, _ = compute_matched_edgar_ratios(df, states, rng=rng)
        r_shrunk_boot[k] = r_shrunk_k

    jb_mean = M_mono_boot.mean(axis=0)
    jb_std = M_mono_boot.std(axis=0) + 1e-12
    jb_lo_m = np.percentile(M_mono_boot, 2.5, axis=0)
    jb_lo_u = np.percentile(M_uncon_boot, 2.5, axis=0)
    jb_snr = np.where(jb_lo_m > 0, jb_mean / jb_std, 0.0)
    C_mat = np.clip(jb_snr / (jb_snr + 1.5), 0.0, 0.99)
    np.fill_diagonal(C_mat, 1.0)

    return {
        "b_mono_pt": b_mono_pt,
        "b_uncon_pt": b_uncon_pt,
        "M_mono_pt": M_mono_pt,
        "M_uncon_pt": M_uncon_pt,
        "ext_rec_pt": ext_rec_pt,
        "M_mono_boot": M_mono_boot,
        "M_uncon_boot": M_uncon_boot,
        "ext_rec_boot": ext_rec_boot,
        "r_shrunk_boot": r_shrunk_boot,
        "C_mat": C_mat,
        "jb_lo_m": jb_lo_m,
        "jb_lo_u": jb_lo_u, "exp_stack": exp_stack,
    }


def main():
    args = parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    if not CACHE.exists():
        raise SystemExit(f"{CACHE} not found -- run 13_diagnostics_and_placebos_v3.py first.")

    print("[1/6] Loading 5-year features, exposures, and cached Stage-1 LOYO residuals...")
    base = pd.read_parquet("data/features_daily_2019_2023.parquet")
    exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
    nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()
    cache = pd.read_parquet(CACHE)

    base["date"] = pd.to_datetime(base["date"])
    exp["date"] = pd.to_datetime(exp["date"])
    base["state"] = base["state"].replace({"TamilNadu": "Tamil Nadu"})

    df = base.dropna(subset=WEATHER + CALENDAR + LOCAL + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
    exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
    df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)
    assert len(df) == len(cache), f"Cache mismatch: {len(cache)} vs {len(df)}"

    df["year"] = df["date"].dt.year
    df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)
    y_all = df["pm25"].values.astype(np.float64)
    resid_full = y_all - cache["pred_c_full"].values

    state_to_node = {"Delhi": "ind_delhi", "Jammu & Kashmir": "ind_jk", "Jammu and Kashmir": "ind_jk"}
    for st in sorted(df["state"].dropna().unique()):
        if st not in state_to_node:
            cand = "ind_" + st.lower().replace(" ", "_").replace("&", "and")
            if cand in nodes:
                state_to_node[st] = cand

    st_counts = df["state"].value_counts()
    states = sorted([s for s in st_counts[st_counts >= 100].index if s in state_to_node])
    ind_nodes = [state_to_node[s] for s in states]
    ext_nodes = [n for n in nodes if n.startswith("ext_")]
    ind_idx = [nodes.index(n) for n in ind_nodes]
    ext_idx = [nodes.index(n) for n in ext_nodes]
    n_st = len(states)

    pop_2022 = load_population_2022(states)
    pop_share = pop_2022 / np.maximum(pop_2022.sum(), 1e-12)
    re_vec, re_fallback = load_re_fraction_2022(states)

    print("[2/6] Computing matched-station 2019->2022 EDGAR progress & Pillar B distribution...")
    r_raw, r_shrunk, n_matched, low_n_flag, r_nat = compute_matched_edgar_ratios(df, states, rng=None)
    p10, p50, p90 = np.percentile(r_shrunk, [10, 50, 90])
    prog_scale_ref = float(max(2.0 * (p90 - p10), 0.15))
    flat_ratio_note = "NEARLY_FLAT (floored at 0.15)" if (p90 - p10) < 0.03 else "DISPERSING"
    print(
        f"  Matched EDGAR ratio (r_i') distribution: P10={p10:.4f}, P50={p50:.4f}, "
        f"P90={p90:.4f}, r_nat={r_nat:.4f} -> {flat_ratio_note}"
    )

    print(f"[3/6] Fitting Monotone & Unconstrained Stage-2 + {args.n_boot}x joint (E, beta) bootstrap...")
    X_base = np.column_stack([
        exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).values for s, b in SB
    ]).astype(np.float64)
    boot = run_bootstrap_and_transport(
        df, exp, nodes, states, ind_idx, ext_idx, X_base, resid_full, n_boot=args.n_boot, seed=42
    )
    M_mono_pt = boot["M_mono_pt"]
    M_uncon_pt = boot["M_uncon_pt"]
    C_mat = boot["C_mat"]
    jb_lo_m = boot["jb_lo_m"]
    jb_lo_u = boot["jb_lo_u"]

    # Pass 1 vs Pass 2 frozen constants handling
    if CONST_PATH.exists() and not args.recompute_constants:
        print(f"[4/6] Pass 2+: Reading frozen constants from {CONST_PATH} (no recompute)...")
        consts = json.loads(CONST_PATH.read_text())
        x_med = float(consts["X_MED"])
        prog_scale = float(consts["PROG_SCALE"])
        center = float(consts["CENTER"])
        scale = float(consts["SCALE"])
        d_ref = float(consts["D_REF"])
        fine_to_z = float(consts["FINE_TO_Z"])
    else:
        print("[4/6] Pass 1: Computing and freezing v5 constants...")
        X_ref, _ = compute_pillar_a_export(M_mono_pt, pop_share, x_med=1.0)
        x_med = float(max(np.median(X_ref), 1e-6))
        _, A_ref = compute_pillar_a_export(M_mono_pt, pop_share, x_med=x_med)
        P_ref = compute_pillar_b_progress(r_shrunk, prog_scale=prog_scale_ref)
        raw_ref = W_EXPORT * A_ref + W_PROGRESS * P_ref + W_RE * re_vec
        center = float(np.median(raw_ref))
        iqr_ref = float(np.percentile(raw_ref, 75) - np.percentile(raw_ref, 25))
        scale = float(max(iqr_ref / 1.35, 1e-4))
        prog_scale = prog_scale_ref

        _, z_ref, _ = raw_and_vt_from_pillars(A_ref, P_ref, re_vec, center, scale)
        claims_ref, d_ref = evaluate_fines(
            states, pop_2022, M_mono_pt, M_uncon_pt, C_mat, jb_lo_m, jb_lo_u, d_ref=None
        )
        _, _, _, fine_to_z = settle_in_z_space(n_st, z_ref, claims_ref, fine_to_z=None)

        consts = {
            "version": "vt_v5_frozen_reference",
            "reference_period": "2022-2023 (EDGAR 2019->2022 matched stations)",
            "weights": {"pillar_A_export": W_EXPORT, "pillar_B_progress": W_PROGRESS, "pillar_C_re": W_RE},
            "X_MED": x_med,
            "PROG_SCALE": prog_scale,
            "CENTER": center,
            "SCALE": scale,
            "D_REF": d_ref,
            "FINE_TO_Z": fine_to_z,
            "HARM_FLOOR_UGM3": HARM_FLOOR,
        }
        CONST_PATH.write_text(json.dumps(consts, indent=2))
        print(f"  Wrote frozen constants -> {CONST_PATH}")

    print("[5/6] Computing VT v5 pillars, bootstrap CIs, zero-sum fine settlement, and audit flags...")
    X_pt, A_pt = compute_pillar_a_export(M_mono_pt, pop_share, x_med=x_med)
    P_pt = compute_pillar_b_progress(r_shrunk, prog_scale=prog_scale)
    raw_pt, z_pt, vt_base_pt = raw_and_vt_from_pillars(A_pt, P_pt, re_vec, center, scale)

    # Unconstrained beta comparison
    _, A_uncon_pt = compute_pillar_a_export(M_uncon_pt, pop_share, x_med=x_med)
    _, _, vt_uncon_pt = raw_and_vt_from_pillars(A_uncon_pt, P_pt, re_vec, center, scale)

    # Zero-sum fine claims & settlement in z-space
    claims, d_ref = evaluate_fines(
        states, pop_2022, M_mono_pt, M_uncon_pt, C_mat, jb_lo_m, jb_lo_u, d_ref=d_ref
    )
    vt_settled_pt, owed_pt, rec_fine_pt, fine_to_z = settle_in_z_space(
        n_st, z_pt, claims, fine_to_z=fine_to_z
    )

    # 300x joint (E, beta) + matched-station r_i bootstrap CIs (settled in z-space)
    vt_boot = np.zeros((args.n_boot, n_st), dtype=np.float64)
    for k in range(args.n_boot):
        Mk = boot["M_mono_boot"][k]
        _, Ak = compute_pillar_a_export(Mk, pop_share, x_med=x_med)
        Pk = compute_pillar_b_progress(boot["r_shrunk_boot"][k], prog_scale=prog_scale)
        _, zk, _ = raw_and_vt_from_pillars(Ak, Pk, re_vec, center, scale)
        owed_k = np.zeros(n_st, dtype=np.float64)
        rec_k = np.zeros(n_st, dtype=np.float64)
        for c in claims:
            u, v = c["def_idx"], c["clm_idx"]
            d_k = max(float(Mk[u, v]), 0.0) * float(pop_2022[v]) * float(C_mat[u, v])
            pts_k = 20.0 + 130.0 * (1.0 - np.exp(-d_k / max(d_ref, 1e-9)))
            owed_k[u] += pts_k
            rec_k[v] += pts_k
        zk_settled = zk - (owed_k - rec_k) / max(fine_to_z, 1e-9)
        vt_boot[k] = 500.0 + 200.0 * np.tanh(zk_settled / 2.0)

    audit_df = compute_audit_metrics(df, states, r_shrunk).set_index("state")
    off_mask = ~np.eye(n_st, dtype=bool)
    rec_dom_pt = (M_mono_pt * off_mask).sum(axis=0)
    exp_dom_pt = (M_mono_pt * off_mask).sum(axis=1)

    rows = []
    for i, st in enumerate(states):
        ad = audit_df.loc[st]
        pm_c = float(ad["pm25_curr"])
        r_d = float(rec_dom_pt[i])
        e_d = float(exp_dom_pt[i])
        rows.append({
            "state": st,
            "archetype": "v5_open",
            "pm25_curr": pm_c,
            "received_dom_ugm3": r_d,
            "exported_dom_ugm3": e_d,
            "acct_burden_curr": max(pm_c - r_d, 0.0) + e_d,
            "effort_multiplier": float(P_pt[i]),
            "vt_score": float(vt_settled_pt[i]),
            "vt_base": float(vt_base_pt[i]),
            "vt_settled": float(vt_settled_pt[i]),
            "vt_ci_low": float(np.percentile(vt_boot[:, i], 2.5)),
            "vt_ci_high": float(np.percentile(vt_boot[:, i], 97.5)),
            "vt_score_unconstrained": float(vt_uncon_pt[i]),
            "pop_2022_m": float(pop_2022[i]),
            "export_pop_X_ugm3": float(X_pt[i]),
            "pillar_A_export": float(A_pt[i]),
            "pillar_B_progress": float(P_pt[i]),
            "pillar_C_re": float(re_vec[i]),
            "raw_score_v5": float(raw_pt[i]),
            "z_score_base": float(z_pt[i]),
            "edgar_ratio_raw": float(r_raw[i]),
            "edgar_ratio_shrunk": float(r_shrunk[i]),
            "n_matched_19_22": int(n_matched[i]),
            "low_n_flag": bool(low_n_flag[i]),
            "re_fallback_flag": bool(re_fallback[i]),
            "fines_owed_pts": float(owed_pt[i]),
            "fines_received_pts": float(rec_fine_pt[i]),
            "cpcb_match_drop_ugm3": float(ad["cpcb_match_drop_ugm3"]),
            "cpcb_naaqs_comp": float(ad["cpcb_naaqs_comp"]),
            "audit_flag": str(ad["audit_flag"]),
        })

    vt_df = pd.DataFrame(rows).sort_values("vt_settled", ascending=False).reset_index(drop=True)
    vt_df["rank"] = np.arange(1, len(vt_df) + 1)

    uncon_rank_order = (
        vt_df.sort_values("vt_score_unconstrained", ascending=False)["state"]
        .reset_index(drop=True)
    )
    uncon_rank_map = {st: idx + 1 for idx, st in enumerate(uncon_rank_order)}
    vt_df["rank_unconstrained"] = vt_df["state"].map(uncon_rank_map)
    vt_df["rank_shift_unconstrained"] = vt_df["rank_unconstrained"] - vt_df["rank"]
    vt_df["rank_shift_gt3_flag"] = vt_df["rank_shift_unconstrained"].abs() > 3

    # Save outputs
    pd.DataFrame(M_mono_pt, index=states, columns=states).to_csv(OUT / "M2_matrix_v5_ugm3.csv")
    pd.DataFrame(C_mat, index=states, columns=states).to_csv(OUT / "M2_confidence_v5_boot.csv")
    m_score = df["year"].isin([2022, 2023]).values
    src_edgar = np.array([
        float(df.loc[m_score & (df["state"] == s), "edgar_pm25_total"].mean()) for s in states
    ])
    pd.DataFrame(M_mono_pt / np.maximum(src_edgar[:, None], 1e-9), index=states, columns=states).to_csv(
        OUT / "transfer_rates_v5_per_edgar.csv"
    )
    vt_df.to_csv(OUT / "VT_scores_v5_final.csv", index=False)

    claims_df = pd.DataFrame(claims)
    if claims_df.empty:
        claims_df = pd.DataFrame(columns=[
            "defendant", "claimant", "harm_ugm3", "harm_uncon_ugm3",
            "harm_ci_low", "confidence", "D_ij", "fine_vt_units", "fine_vt_points",
        ])
    claims_df.to_csv(OUT / "fine_claims_v5.csv", index=False)

    ledger_rows = [
        {
            "state": r["state"],
            "rank": int(r["rank"]),
            "vt_base": r["vt_base"],
            "fines_owed_pts": r["fines_owed_pts"],
            "fines_received_pts": r["fines_received_pts"],
            "net_fine_balance_pts": r["fines_owed_pts"] - r["fines_received_pts"],
            "vt_settled": r["vt_settled"],
        }
        for _, r in vt_df.iterrows()
    ]
    pd.DataFrame(ledger_rows).to_csv(OUT / "fine_ledger.csv", index=False)

    net_rows = []
    for i in range(n_st):
        for j in range(i + 1, n_st):
            a, b = states[i], states[j]
            hab, hba = float(M_mono_pt[i, j]), float(M_mono_pt[j, i])
            net = hab - hba
            agg, vic = (a, b) if net >= 0 else (b, a)
            net_rows.append({
                "state_A": a, "state_B": b, "harm_A_to_B_ugm3": hab, "harm_B_to_A_ugm3": hba,
                "net_harm_ugm3": abs(net), "net_aggressor": agg, "net_victim": vic,
                "conf_A_to_B": float(C_mat[i, j]), "conf_B_to_A": float(C_mat[j, i]),
            })
    pd.DataFrame(net_rows).sort_values("net_harm_ugm3", ascending=False).to_csv(
        OUT / "attribution_network_v5.csv", index=False
    )

    # ------------------------------------------------------------------ Mandatory Validation Printouts
    print("\n[6/6] Running mandatory v5 validation suite...")
    print("\n=== VT v5 LEADERBOARD (Settled vs Base, 95% Bootstrap CIs) ===")
    disp_cols = [
        "rank", "state", "pillar_A_export", "pillar_B_progress", "pillar_C_re",
        "vt_base", "vt_settled", "vt_ci_low", "vt_ci_high", "rank_shift_unconstrained",
    ]
    print(vt_df[disp_cols].to_string(index=False))

    print(f"\n=== ZERO-SUM BILATERAL FINE CLAIMS (C > 0.75, Both CI_low > 0, harm >= {HARM_FLOOR:.2f} ug/m3) ===")
    if not claims_df.empty:
        print(claims_df[["defendant", "claimant", "harm_ugm3", "harm_uncon_ugm3", "confidence", "D_ij", "fine_vt_points"]].to_string(index=False))
    else:
        print("None")

    # 1. Split-half Spearman: 2022 alone vs 2023 alone
    vt_2022 = np.zeros(n_st)
    vt_2023 = np.zeros(n_st)
    for yr, out_arr in [(2022, vt_2022), (2023, vt_2023)]:
        m_yr = df["year"].values == yr
        E_yr = np.zeros((n_st, len(nodes), 9))
        for r_i, st in enumerate(states):
            rm = m_yr & (df["state"].values == st)
            if rm.any():
                E_yr[r_i] = boot["exp_stack"][rm].mean(axis=0)
        M_yr = np.einsum("rnj,j->nr", E_yr, boot["b_mono_pt"])[ind_idx, :]
        _, A_yr = compute_pillar_a_export(M_yr, pop_share, x_med=x_med)
        _, _, vt_y = raw_and_vt_from_pillars(A_yr, P_pt, re_vec, center, scale)
        out_arr[:] = vt_y
    rho_split = float(spearmanr(vt_2022, vt_2023).statistic)

    # 2. Spearman vs pm25_curr
    rho_pm = float(spearmanr(vt_df["vt_settled"].values, vt_df["pm25_curr"].values).statistic)

    # 3. Rank stability: monotone vs unconstrained betas
    shifted_states = vt_df[vt_df["rank_shift_gt3_flag"]][["state", "rank", "rank_unconstrained", "rank_shift_unconstrained"]]

    # 4. Placebos P1 / P2 / P3 through pipeline (real null bootstrap C_ij & CI_low)
    rng_p = np.random.default_rng(999)
    placebo_fine_counts = {}
    for p_name, mode in [
        ("P1_TrajShift", "shift"),
        ("P2_EmissionShuffle", "shuffle"),
        ("P3_ResidenceOnly", "flat"),
    ]:
        if mode == "shift":
            resid_p = np.roll(resid_full, len(resid_full) // 3)
            X_p = X_base
        elif mode == "shuffle":
            resid_p = rng_p.permutation(resid_full)
            X_p = X_base
        else:
            resid_p = resid_full - resid_full.mean()
            X_p = np.full_like(X_base, X_base.mean(axis=0))
        b_p = run_bootstrap_and_transport(
            df, exp, nodes, states, ind_idx, ext_idx, X_p, resid_p, n_boot=50, seed=999
        )
        p_claims, _ = evaluate_fines(
            states, pop_2022, b_p["M_mono_pt"], b_p["M_uncon_pt"],
            b_p["C_mat"], b_p["jb_lo_m"], b_p["jb_lo_u"], d_ref=d_ref
        )
        placebo_fine_counts[p_name] = len(p_claims)

    # 5. Matched station counts & n < 5 flags
    low_n_states = [states[i] for i in range(n_st) if low_n_flag[i]]

    # 6. Eligible fine pairs & C_ij spread
    off_confs = C_mat[off_mask]
    c_min, c_med, c_max = float(off_confs.min()), float(np.median(off_confs)), float(off_confs.max())

    print("\n=== MANDATORY VALIDATION PRINTOUTS ===")
    print(f"1. Split-half Spearman (2022 alone vs 2023 alone): {rho_split:.4f}")
    print(f"2. Spearman (VT_settled vs pm25_curr): {rho_pm:.4f}" + (" [WARN > 0.90]" if abs(rho_pm) > 0.90 else " [OK <= 0.90]"))
    print(f"3. Rank shifts |shift| > 3 (Monotone vs Unconstrained): {len(shifted_states)} states")
    if not shifted_states.empty:
        print(shifted_states.to_string(index=False))
    print(
        f"4. Placebo fine pairs above floor (P1/P2/P3): "
        f"P1={placebo_fine_counts['P1_TrajShift']}, "
        f"P2={placebo_fine_counts['P2_EmissionShuffle']}, "
        f"P3={placebo_fine_counts['P3_ResidenceOnly']}"
    )
    print(f"5. Matched station counts (n < {LOW_N_THRESHOLD} flagged): {low_n_states}")
    print(
        f"6. Eligible fine pairs (C>0.75, CI_low>0, harm>={HARM_FLOOR:.2f}): {len(claims_df)} | "
        f"Off-diag C_ij spread: min={c_min:.3f}, med={c_med:.3f}, max={c_max:.3f}"
    )
    print(f"\nCompleted in {time.time() - t0:.1f}s -> {OUT}/")


if __name__ == "__main__":
    main()
