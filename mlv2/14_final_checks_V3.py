"""
14_final_checks_v3.py -- CarbonVayu mlv3: the last step before writing.

  1. PAIRED significance tests (calendar-week block bootstrap) of the real model vs each placebo / variant
  2. REGIME-ADJUSTED Stage 2: flow-regime (residence-time) nuisance regressors enter the fit, but only the
     emission-weighted betas are used for attribution.
        R1 = 9 summed residence-time nuisance columns      (R0 = same, WITHOUT emission columns)
        R2 = 35-node x 3-bin residence-time nuisance cols  (R0b = same, WITHOUT emission columns)
             NOTE: R2 is a PREDICTIVE stress test only. Node-level residence time is almost a linear combination of the
             emission-weighted exposures, so R2's emission betas are not identifiable and are NOT used for attribution.
     "Do emissions add anything beyond flow regime?"  =  R1 vs R0  and  R2 vs R0b
  3. FINAL BRACKET for Delhi Oct-Nov: 4 specs x node shares with week-bootstrap CIs (betas refit inside the bootstrap),
     plus the min-max range across specs. This is the table to put in the paper.

Reuses results/v3_5yr/diagnostics/stage1_loyo_cache.parquet from 13_diagnostics_and_placebos_v3.py (no Stage-1 retraining).
Run from the project root:  python 14_final_checks_v3.py
"""
import time, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.linalg import solve_triangular
from scipy.optimize import lsq_linear

warnings.filterwarnings("ignore"); t_all = time.time()
OUT = Path("results/v3_5yr/final"); OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path("results/v3_5yr/diagnostics/stage1_loyo_cache.parquet")
YEARS = [2019, 2020, 2021, 2022, 2023]; N_BOOT = 300
pd.set_option("display.width", 220); pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
if not CACHE.exists(): raise SystemExit(f"{CACHE} not found - run 13_diagnostics_and_placebos_v3.py first")

# ------------------------------------------------------------------ data (identical alignment to script 13)
print("[1/5] loading & aligning ...")
base = pd.read_parquet("data/features_daily_2019_2023.parquet")
exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()
base["date"] = pd.to_datetime(base["date"]); exp["date"] = pd.to_datetime(exp["date"])
base["state"] = base["state"].replace({"TamilNadu": "Tamil Nadu"})
WEATHER = ["blh_mean","blh_min","t2m_c","rh_pct","u10","v10","wspd10","precip_mm","u925","v925","wspd925","u850","v850","wspd850"]
CALENDAR = ["doy_sin","doy_cos","day_of_week","is_weekend"]
LOCAL = ["edgar_pm25_agriculture","edgar_pm25_buildings","edgar_pm25_ind_combustion","edgar_pm25_power_industry",
         "edgar_pm25_transport","edgar_pm25_waste","edgar_pm25_total","edgar_bc_total","edgar_co_total",
         "edgar_nh3_total","edgar_nox_total","edgar_so2_total"]
COLS_FULL = WEATHER + CALENDAR + LOCAL
BINS = ["0_24h", "24_48h", "48_72h"]; SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES = [f"{s}_{b}" for s, b in SB]
df = base.dropna(subset=COLS_FULL + ["pm25"]).sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="inner")
df = df.merge(exp[["location_id", "date"]], on=["location_id", "date"], how="inner").reset_index(drop=True)
df["year"] = df.date.dt.year; df["month"] = df.date.dt.month; df["day"] = df.date.dt.day
df["yw"] = df.year * 100 + df.date.dt.isocalendar().week.astype(int)
y_all = df.pm25.values.astype(np.float64); yw_all = df.yw.values
SUBSETS = {"all": np.ones(len(df), bool), "north_box": df.in_north_india_box.astype(bool).values,
           "delhi_OctNov": ((df.state == "Delhi") & df.month.isin([10, 11])).values}
STATE_TO_NODE = {"Delhi": "ind_delhi", "Jammu & Kashmir": "ind_jk", "Jammu and Kashmir": "ind_jk"}
for s in df.state.dropna().unique():
    if s not in STATE_TO_NODE:
        c = "ind_" + s.lower().replace(" ", "_").replace("&", "and")
        if c in nodes: STATE_TO_NODE[s] = c
cache = pd.read_parquet(CACHE)
if len(cache) != len(df): raise SystemExit(f"cache rows {len(cache)} != aligned rows {len(df)}: rerun 13 or check inputs")
pred_c_full = cache.pred_c_full.values; pred_c_wonly = cache.pred_c_wonly.values
oof_full = {yr: cache.loc[df.year != yr, f"oof_full_{yr}"].values for yr in YEARS}
oof_wonly = {yr: cache.loc[df.year != yr, f"oof_wonly_{yr}"].values for yr in YEARS}
print(f"  rows {len(df):,} | stations {df.location_id.nunique()} | weeks {df.yw.nunique()}")

# ------------------------------------------------------------------ exposure matrices (same definitions as script 13)
print("[2/5] building exposure matrices ...")
col = lambda n, s, b: f"exp_{n}_{s}_{b}"
X_base = np.column_stack([exp[[col(n, s, b) for n in nodes]].sum(axis=1).values for s, b in SB]).astype(np.float64)
X_excl = X_base.copy(); own = df.state.map(STATE_TO_NODE).values
for n in nodes:
    m = own == n
    if m.any():
        for j, (s, b) in enumerate(SB): X_excl[m, j] -= exp.loc[m, col(n, s, b)].values
sh = pd.DataFrame(X_base, columns=NAMES)
for c in ("location_id", "year", "month", "day"): sh[c] = df[c].values
sh["shift_year"] = sh.year.map({2019: 2020, 2020: 2021, 2021: 2022, 2022: 2023, 2023: 2019})
ms = df[["location_id", "year", "month", "day"]].merge(sh.drop(columns=["year"]).rename(columns={"shift_year": "year"}),
                                                       on=["location_id", "year", "month", "day"], how="left")
X_p1 = ms[NAMES].fillna(ms[NAMES].mean()).values.astype(np.float64)
scale = np.zeros((len(nodes), len(SB)))
for i, n in enumerate(nodes):
    for j, (s, b) in enumerate(SB):
        v = exp[col(n, s, b)].values; nz = v[v > 0]; scale[i, j] = float(nz.mean()) if len(nz) else 0.0
rng_p = np.random.default_rng(123); X_p2_list = []
for _ in range(5):
    perm = rng_p.permutation(len(nodes)); Xs = np.zeros_like(X_base)
    for i, n in enumerate(nodes):
        for j, (s, b) in enumerate(SB):
            if scale[i, j] > 0: Xs[:, j] += exp[col(n, s, b)].values * (scale[perm[i], j] / scale[i, j])
    X_p2_list.append(Xs)
X_rt = np.zeros_like(X_base)                                   # P3 / R1 nuisance: 9 summed residence-time columns
for i, n in enumerate(nodes):
    for j, (s, b) in enumerate(SB):
        if scale[i, j] > 0: X_rt[:, j] += exp[col(n, s, b)].values / scale[i, j]
node_rt, node_rt_names = [], []                                # R2 nuisance: node x bin residence time (sector-averaged)
for i, n in enumerate(nodes):
    for k, b in enumerate(BINS):
        v = np.zeros(len(df)); c = 0
        for s in ["agri", "other", "sia"]:
            j = SB.index((s, b))
            if scale[i, j] > 0: v += exp[col(n, s, b)].values / scale[i, j]; c += 1
        if c and v.std() > 0: node_rt.append(v / c); node_rt_names.append(f"{n}_{b}")
X_nrt = np.column_stack(node_rt).astype(np.float64); print(f"  node-level nuisance columns: {X_nrt.shape[1]}")
EMPTY = np.zeros((len(df), 0))

# ------------------------------------------------------------------ fast bounded least squares (normal equations, standardised)
def solve_normal(AtA, Aty, lb):
    d = np.sqrt(np.clip(np.diag(AtA), 1e-12, None)); M = AtA / np.outer(d, d); v = Aty / d
    L = np.linalg.cholesky(M + 1e-10 * np.eye(len(M)))
    z = solve_triangular(L, v, lower=True)
    return lsq_linear(L.T, z, bounds=(lb, np.inf)).x / d

def design(Xe, Ne, mono):
    if mono:                                                    # b0>=b1>=b2>=0 per sector via cumulative columns
        Xc = np.zeros_like(Xe)
        for k in range(3):
            c0, c1, c2 = 3*k, 3*k+1, 3*k+2
            Xc[:, c0] = Xe[:, c0]; Xc[:, c1] = Xe[:, c0] + Xe[:, c1]; Xc[:, c2] = Xe[:, c0] + Xe[:, c1] + Xe[:, c2]
        Xe = Xc
    A = np.hstack([np.ones((len(Xe), 1)), Xe, Ne])
    lb = np.r_[-np.inf, np.zeros(Xe.shape[1]), np.full(Ne.shape[1], -np.inf)]
    return A, lb

def unpack(sol, ke, mono):
    a, be, g = sol[0], sol[1:1+ke].copy(), sol[1+ke:]
    if mono and ke == 9:
        out = np.zeros(9)
        for k in range(3):
            c0, c1, c2 = 3*k, 3*k+1, 3*k+2
            out[c2] = be[c2]; out[c1] = be[c2] + be[c1]; out[c0] = be[c2] + be[c1] + be[c0]
        be = out
    return a, be, g

def fit(Xe, Ne, y, mono=False):
    A, lb = design(Xe, Ne, mono); return unpack(solve_normal(A.T @ A, A.T @ y, lb), Xe.shape[1], mono)

def loyo(Xe, Ne, pred_c, oof, mono=False):
    out = np.zeros(len(df)); betas = {}
    for h in YEARS:
        tr, te = (df.year != h).values, (df.year == h).values
        a, be, g = fit(Xe[tr], Ne[tr], y_all[tr] - oof[h], mono)
        out[te] = np.clip(pred_c[te] + a + Xe[te] @ be + Ne[te] @ g, 0, None); betas[h] = be
    return out, betas

# solver self-check against scipy on one fold
tr0 = (df.year != YEARS[0]).values; r0 = y_all[tr0] - oof_full[YEARS[0]]
A0 = np.column_stack([np.ones(tr0.sum()), X_base[tr0]]); ref = lsq_linear(A0, r0, bounds=(np.r_[-np.inf, np.zeros(9)], np.inf)).x
mine = fit(X_base[tr0], EMPTY[tr0], r0); print(f"  solver check vs scipy lsq_linear: max |beta diff| = {np.abs(mine[1]-ref[1:]).max():.2e}")

# ------------------------------------------------------------------ variants
print("[3/5] fitting variants (5-fold LOYO) ...")
P = {}; B = {}
P["B  baseline"], B["B"] = loyo(X_base, EMPTY, pred_c_full, oof_full)
P["M  monotone"], B["M"] = loyo(X_base, EMPTY, pred_c_full, oof_full, mono=True)
P["X  excl own node"], B["X"] = loyo(X_excl, EMPTY, pred_c_full, oof_full)
P["P1 traj shift"], _ = loyo(X_p1, EMPTY, pred_c_full, oof_full)
P["P2 emission shuffle"] = np.mean([loyo(Xs, EMPTY, pred_c_full, oof_full)[0] for Xs in X_p2_list], axis=0)
P["P3 residence time"], _ = loyo(X_rt, EMPTY, pred_c_full, oof_full)
P["R0  regime only (9)"], _ = loyo(EMPTY, X_rt, pred_c_full, oof_full)
P["R1  regime(9) + emissions"], B["R1"] = loyo(X_base, X_rt, pred_c_full, oof_full)
P["R0b regime only (node)"], _ = loyo(EMPTY, X_nrt, pred_c_full, oof_full)
P["R2  regime(node) + emissions"], _ = loyo(X_base, X_nrt, pred_c_full, oof_full)   # predictive check ONLY (see note)
P["C  stage-1 only"] = pred_c_full

# ------------------------------------------------------------------ paired tests
def wk_pair(y, p_a, p_b, yw, seed=42):
    """RMSE(p_b) - RMSE(p_a); positive => A better. Calendar-week block bootstrap over all stations."""
    ea, eb = (y - p_a)**2, (y - p_b)**2; _, inv = np.unique(yw, return_inverse=True)
    n = np.bincount(inv); sa, sb = np.bincount(inv, ea), np.bincount(inv, eb); rng = np.random.default_rng(seed); out = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(n), len(n)); N = n[idx].sum(); out.append(np.sqrt(sb[idx].sum()/N) - np.sqrt(sa[idx].sum()/N))
    return np.sqrt(eb.mean()) - np.sqrt(ea.mean()), np.percentile(out, 2.5), np.percentile(out, 97.5)

PAIRS = [("B  baseline", "P1 traj shift", "real exposures vs trajectories from another year"),
         ("B  baseline", "P2 emission shuffle", "real vs shuffled node emissions"),
         ("B  baseline", "P3 residence time", "real vs residence-time-only"),
         ("B  baseline", "M  monotone", "cost of forcing monotone decay"),
         ("X  excl own node", "B  baseline", "excluding the receptor's own node"),
         ("R1  regime(9) + emissions", "R0  regime only (9)", "KEY: emissions beyond flow regime (9 nuisance cols)"),
         ("R2  regime(node) + emissions", "R0b regime only (node)", "KEY: emissions beyond flow regime (node-level nuisance)"),
         ("B  baseline", "C  stage-1 only", "baseline gain over Stage 1 (reference)")]
rows = []
for a_, b_, why in PAIRS:
    for sub, m in SUBSETS.items():
        pt, lo, hi = wk_pair(y_all[m], P[a_][m], P[b_][m], yw_all[m])
        rows.append(dict(test=f"{a_.split()[0]} vs {b_.split()[0]}", meaning=why, subset=sub, dRMSE=pt, ci_low=lo, ci_high=hi,
                         verdict="A better" if lo > 0 else ("B better" if hi < 0 else "not distinguishable")))
pt_df = pd.DataFrame(rows); pt_df.to_csv(OUT/"paired_tests.csv", index=False)
print("\n=== PAIRED TESTS (week-block bootstrap; dRMSE>0 means the first-named model is better) ===")
print(pt_df.to_string(index=False))
rm = pd.DataFrame([{"variant": k, **{s: float(np.sqrt(np.mean((y_all[m] - p[m])**2))) for s, m in SUBSETS.items()}} for k, p in P.items()])
rm.to_csv(OUT/"variant_rmse.csv", index=False); print("\n=== RMSE by variant ==="); print(rm.to_string(index=False))
bt = pd.DataFrame({"param": NAMES, **{k: np.mean([B[k][y] for y in YEARS], axis=0) for k in B}})
bt.to_csv(OUT/"betas_by_variant.csv", index=False); print("\n=== MEAN EMISSION BETAS ==="); print(bt.to_string(index=False))

# ------------------------------------------------------------------ Delhi bracket with refit-inside-bootstrap
print(f"\n[4/5] Delhi Oct-Nov bracket ({N_BOOT} week-block bootstraps, betas refit inside) ...")
dm = SUBSETS["delhi_OctNov"]; obs = float(y_all[dm].mean())
dexp = np.array([[exp.loc[dm, col(n, s, b)].mean() for s, b in SB] for n in nodes])         # (nodes, 9)
ub, inv = np.unique(yw_all, return_inverse=True); W = len(ub)

def bracket(Xe, Ne, resid, mono, tag):
    A, lb = design(Xe, Ne, mono); p = A.shape[1]
    AtA_w = np.zeros((W, p, p)); Aty_w = np.zeros((W, p))
    for w in range(W):
        rows = np.where(inv == w)[0]; Aw = A[rows]; AtA_w[w] = Aw.T @ Aw; Aty_w[w] = Aw.T @ resid[rows]
    def beta_from(counts):
        sol = solve_normal(np.tensordot(counts, AtA_w, 1), counts @ Aty_w, lb); return unpack(sol, Xe.shape[1], mono)[1]
    b_pt = beta_from(np.ones(W)); rng = np.random.default_rng(42)
    bb = np.array([beta_from(np.bincount(rng.integers(0, W, W), minlength=W).astype(float)) for _ in range(N_BOOT)])
    ug_pt = dexp @ b_pt; ug_b = bb @ dexp.T; tot_pt = max(ug_pt.sum(), 1e-9); tot_b = np.maximum(ug_b.sum(1, keepdims=True), 1e-9)
    res = pd.DataFrame({"source_node": nodes, "ugm3": ug_pt, "ugm3_lo": np.percentile(ug_b, 2.5, 0), "ugm3_hi": np.percentile(ug_b, 97.5, 0),
                        "pct_obs": 100*ug_pt/obs, "pct_inc": 100*ug_pt/tot_pt,
                        "inc_lo": np.percentile(100*ug_b/tot_b, 2.5, 0), "inc_hi": np.percentile(100*ug_b/tot_b, 97.5, 0)}).sort_values("ugm3", ascending=False)
    res.to_csv(OUT/f"delhi_octnov_{tag}.csv", index=False)
    return res, tot_pt, np.percentile(ug_b.sum(1), [2.5, 97.5])

res_full, res_wo = y_all - pred_c_full, y_all - pred_c_wonly
SPECS = {"Unconstrained": (X_base, EMPTY, res_full, False), "Monotone": (X_base, EMPTY, res_full, True),
         "WeatherOnly-S1": (X_base, EMPTY, res_wo, False), "Regime-adj R1": (X_base, X_rt, res_full, False)}
tabs, tots = {}, []
for name, (Xe, Ne, r, mono) in SPECS.items():
    t, tot, (tlo, thi) = bracket(Xe, Ne, r, mono, name.replace(" ", "_").replace("-", "_")); tabs[name] = t
    tots.append(dict(spec=name, total_ugm3=tot, total_lo=tlo, total_hi=thi, pct_of_obs=100*tot/obs)); print(f"  done: {name}")
print(f"\nDelhi Oct-Nov observed mean PM2.5 = {obs:.1f} ug/m3")
print("\n=== TOTAL ATTRIBUTABLE TRANSPORT BY SPEC ==="); print(pd.DataFrame(tots).to_string(index=False))

TOP = ["ext_pak", "ind_punjab", "ind_haryana", "ind_uttar_pradesh", "ind_delhi", "ind_rajasthan"]
rows = []
for n in [x for x in TOP if x in nodes]:
    r = {"node": n}; pts, los, his = [], [], []
    for name, t in tabs.items():
        q = t.set_index("source_node").loc[n]; r[name] = f"{q.pct_inc:4.1f} [{q.inc_lo:4.1f}-{q.inc_hi:4.1f}]"
        pts.append(q.pct_inc); los.append(q.inc_lo); his.append(q.inc_hi)
    r["range_of_point_estimates"] = f"{min(pts):.1f} - {max(pts):.1f}"; r["union_of_CIs"] = f"{min(los):.1f} - {max(his):.1f}"; rows.append(r)
fin = pd.DataFrame(rows); fin.to_csv(OUT/"delhi_octnov_final_bracket_pct_of_increment.csv", index=False)
print("\n=== DELHI OCT-NOV: % OF ATTRIBUTABLE INCREMENT, point [95% week-bootstrap CI] ==="); print(fin.to_string(index=False))
ug = pd.DataFrame({"node": [x for x in TOP if x in nodes]})
for name, t in tabs.items(): ug[name] = [t.set_index("source_node").loc[n, "ugm3"] for n in ug.node]
ug.to_csv(OUT/"delhi_octnov_final_bracket_ugm3.csv", index=False); print("\n=== SAME, in ug/m3 ==="); print(ug.to_string(index=False))

pd.DataFrame({"location_id": df.location_id, "date": df.date, "state": df.state, "pm25": y_all,
              **{k.split()[0]: v for k, v in P.items()}}).to_parquet(OUT/"loyo_predictions_variants.parquet", index=False)
print(f"\n[5/5] done in {time.time()-t_all:.0f}s -> {OUT}/")
