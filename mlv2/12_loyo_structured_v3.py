"""
12_loyo_structured_v3.py -- CarbonVayu mlv3 (5-year 2019-2023)
1. 5-fold Leave-One-Year-Out (LOYO) validation: Structured v3 (9 params) vs C (local only)
2. Decay parameter stability across all 5 held-out years + full 5-year bootstrap CIs
3. Out-of-sample 5-year IGP attribution matrices (annual & Oct-Nov) + Delhi sector split
4. Saves CSVs & 3 publication-ready figures to results/v3_5yr/
"""
import time
import warnings
from pathlib import Path
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
t0 = time.time()

OUT = Path("results/v3_5yr")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
N_BOOT = 300
YEARS = [2019, 2020, 2021, 2022, 2023]

pd.set_option("display.width", 180)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# ------------------------------------------------------------------ 1. Load & merge
print("Loading 5-year features and Trajectory v3 exposures...")
base = pd.read_parquet("data/features_daily_2019_2023.parquet")
exp = pd.read_parquet("data/node_exposure_v3_daily_2019_2023.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()

base["date"] = pd.to_datetime(base["date"])
exp["date"] = pd.to_datetime(exp["date"])
base["state"] = base["state"].replace({"TamilNadu": "Tamil Nadu"})

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
COLS_C = WEATHER + CALENDAR + LOCAL
BINS = ["0_24h", "24_48h", "48_72h"]
SB = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES = [f"{s}_{b}" for s, b in SB]
TOT_COLS = [f"tot_{s}_{b}" for s, b in SB]

tots = pd.DataFrame({"location_id": exp["location_id"], "date": exp["date"]})
for s, b in SB:
    tots[f"tot_{s}_{b}"] = exp[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).astype(np.float32)

df = base.dropna(subset=COLS_C + ["pm25"]).merge(tots, on=["location_id", "date"], how="inner")
df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
exp = df[["location_id", "date"]].merge(exp, on=["location_id", "date"], how="left")
df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month
df["yw"] = df["year"] * 100 + df["date"].dt.isocalendar().week.astype(int)
print(f"Aligned 5-year dataset: {len(df):,} rows | {df['location_id'].nunique()} stations")


def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )


def fit_shared_decay(X_tot, y_resid):
    X_aug = np.column_stack([np.ones(len(X_tot)), X_tot])
    lb = np.array([-np.inf] + [0.0] * X_tot.shape[1])
    ub = np.full(X_tot.shape[1] + 1, np.inf)
    sol = lsq_linear(X_aug, y_resid, bounds=(lb, ub))
    return sol.x[0], sol.x[1:]


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    mae = np.mean(np.abs(y - p))
    r2 = 1.0 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
    sp = spearmanr(y, p)[0]
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp)


def boot_delta(y, p_hi, p_lo, blk):
    e_hi, e_lo = (y - p_hi) ** 2, (y - p_lo) ** 2
    ub, inv = np.unique(blk, return_inverse=True)
    n = np.bincount(inv)
    s_hi, s_lo = np.bincount(inv, e_hi), np.bincount(inv, e_lo)
    rng = np.random.default_rng(42)
    out = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(ub), len(ub))
        N = n[idx].sum()
        out.append(np.sqrt(s_lo[idx].sum() / N) - np.sqrt(s_hi[idx].sum() / N))
    pt = np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean())
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5)


# ------------------------------------------------------------------ 2. 5-Fold LOYO
pred_c_loyo = np.zeros(len(df), dtype=np.float64)
pred_v3_loyo = np.zeros(len(df), dtype=np.float64)
loyo_eval_rows = []
loyo_boot_rows = []
loyo_params = {}
loyo_intercepts = {}

for hold_yr in YEARS:
    t_yr = time.time()
    tr_mask = (df["year"] != hold_yr).values
    te_mask = (df["year"] == hold_yr).values
    tr = df.loc[tr_mask].reset_index(drop=True)
    te = df.loc[te_mask].reset_index(drop=True)

    # Cross-fit nuisance model C on the 4 training years (grouped by year-week)
    oof_c = np.zeros(len(tr), dtype=np.float64)
    for tr_i, va_i in GroupKFold(n_splits=5).split(tr, groups=tr["yw"].values):
        m = make_lgb(0).fit(tr.loc[tr_i, COLS_C], np.log1p(tr.loc[tr_i, "pm25"].values))
        oof_c[va_i] = np.clip(np.expm1(m.predict(tr.loc[va_i, COLS_C])), 0, None)

    pred_c_te = np.mean([
        np.clip(np.expm1(make_lgb(s).fit(tr[COLS_C], np.log1p(tr["pm25"].values)).predict(te[COLS_C])), 0, None)
        for s in [0, 1, 2]
    ], axis=0)

    resid_tr = tr["pm25"].values - oof_c
    alpha, betas = fit_shared_decay(tr[TOT_COLS].values.astype(np.float64), resid_tr)
    pred_v3_te = np.clip(pred_c_te + alpha + te[TOT_COLS].values @ betas, 0, None)

    pred_c_loyo[te_mask] = pred_c_te
    pred_v3_loyo[te_mask] = pred_v3_te
    loyo_params[hold_yr] = betas
    loyo_intercepts[hold_yr] = alpha

    subsets = {
        "all": np.ones(len(te), bool),
        "north_box": te["in_north_india_box"].astype(bool).values,
        "delhi_OctNov": ((te["state"] == "Delhi") & te["month"].isin([10, 11])).values,
    }
    blk_te = (te["location_id"].astype(str) + "_" + te["yw"].astype(str)).values
    for sub, msk in subsets.items():
        for mname, p in [("C (local only)", pred_c_te), ("Structured v3 (9 params)", pred_v3_te)]:
            loyo_eval_rows.append(dict(test_year=hold_yr, model=mname, subset=sub, **metrics(te.loc[msk, "pm25"], p[msk])))
        pt, lo, hi = boot_delta(te["pm25"].values[msk], pred_v3_te[msk], pred_c_te[msk], blk_te[msk])
        verdict = "better" if lo > 0 else ("worse" if hi < 0 else "not distinguishable")
        loyo_boot_rows.append(dict(test_year=hold_yr, subset=sub, dRMSE=pt, ci_low=lo, ci_high=hi, verdict=verdict))

    print(f"  [LOYO {hold_yr}] done in {time.time() - t_yr:.1f}s | intercept={alpha:+.2f}")

# Pooled 5-year out-of-sample evaluation
blk_all = (df["location_id"].astype(str) + "_" + df["yw"].astype(str)).values
pooled_subsets = {
    "all": np.ones(len(df), bool),
    "north_box": df["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((df["state"] == "Delhi") & df["month"].isin([10, 11])).values,
}
for sub, msk in pooled_subsets.items():
    for mname, p in [("C (local only)", pred_c_loyo), ("Structured v3 (9 params)", pred_v3_loyo)]:
        loyo_eval_rows.append(dict(test_year="POOLED_5YR", model=mname, subset=sub, **metrics(df.loc[msk, "pm25"], p[msk])))
    pt, lo, hi = boot_delta(df["pm25"].values[msk], pred_v3_loyo[msk], pred_c_loyo[msk], blk_all[msk])
    verdict = "better" if lo > 0 else ("worse" if hi < 0 else "not distinguishable")
    loyo_boot_rows.append(dict(test_year="POOLED_5YR", subset=sub, dRMSE=pt, ci_low=lo, ci_high=hi, verdict=verdict))

eval_df = pd.DataFrame(loyo_eval_rows)
boot_df = pd.DataFrame(loyo_boot_rows)
eval_df.to_csv(OUT / "loyo_5yr_metrics.csv", index=False)
boot_df.to_csv(OUT / "loyo_5yr_bootstrap_delta.csv", index=False)

print("\n=== 5-YEAR LOYO PERFORMANCE (POOLED + PER-YEAR) ===")
print(eval_df[eval_df["test_year"] == "POOLED_5YR"].to_string(index=False))
print("\n=== PAIRED BLOCK-BOOTSTRAP dRMSE (Structured v3 vs C; positive = v3 better) ===")
print(boot_df.to_string(index=False))

# Parameter stability table across all 5 LOYO folds
param_df = pd.DataFrame({"param": NAMES})
for yr in YEARS:
    param_df[f"holdout_{yr}"] = loyo_params[yr]
param_df["mean_beta"] = param_df[[f"holdout_{yr}" for yr in YEARS]].mean(axis=1)
param_df["std_beta"] = param_df[[f"holdout_{yr}" for yr in YEARS]].std(axis=1)
param_df.to_csv(OUT / "loyo_5yr_decay_params.csv", index=False)
print("\n=== 5-YEAR LOYO DECAY PARAMETER STABILITY ===")
print(param_df.to_string(index=False))

# ------------------------------------------------------------------ 3. Out-of-Sample 5-Year Attribution Matrices
# Use each held-out year's own LOYO betas for strictly out-of-sample attribution
b_row = np.vstack([loyo_params[yr] for yr in df["year"].values])  # (N, 9)

c_agri, c_other, c_sia, c_tot = {}, {}, {}, {}
for n in nodes:
    ag = sum(b_row[:, i] * exp[f"exp_{n}_agri_{b}"].values for i, b in enumerate(BINS))
    ot = sum(b_row[:, 3 + i] * exp[f"exp_{n}_other_{b}"].values for i, b in enumerate(BINS))
    si = sum(b_row[:, 6 + i] * exp[f"exp_{n}_sia_{b}"].values for i, b in enumerate(BINS))
    c_agri[n], c_other[n], c_sia[n], c_tot[n] = ag, ot, si, ag + ot + si

c_df = pd.DataFrame(c_tot)
c_df["receptor_state"] = df["state"].values
c_df["month"] = df["month"].values

for tag, sub_df in [("annual_2019_2023", c_df), ("octnov_2019_2023", c_df[c_df["month"].isin([10, 11])])]:
    mat_ug = sub_df.groupby("receptor_state")[nodes].mean()
    mat_pct = mat_ug.div(mat_ug.sum(axis=1).replace(0, np.nan), axis=0) * 100.0
    mat_ug.to_csv(OUT / f"structured_v3_matrix_{tag}_ugm3.csv")
    mat_pct.to_csv(OUT / f"structured_v3_matrix_{tag}_pct.csv")
    if tag == "octnov_2019_2023":
        oct_pct = mat_pct

# Delhi Oct-Nov (2019-2023) breakdown + cross-year min/max range
del_mask = pooled_subsets["delhi_OctNov"]
del_rows = []
tot_del_sum = max(sum(c_tot[k][del_mask].mean() for k in nodes), 1e-9)

# Compute year-by-year Delhi share to show 5-year range
yr_shares = {n: [] for n in nodes}
for yr in YEARS:
    ym = del_mask & (df["year"].values == yr)
    ysum = max(sum(c_tot[k][ym].mean() for k in nodes), 1e-9)
    for n in nodes:
        yr_shares[n].append(100.0 * c_tot[n][ym].mean() / ysum)

for n in nodes:
    ag_v = c_agri[n][del_mask].mean()
    ot_v = c_other[n][del_mask].mean()
    si_v = c_sia[n][del_mask].mean()
    tv = ag_v + ot_v + si_v
    del_rows.append({
        "source_node": n,
        "agri_ugm3": ag_v, "other_ugm3": ot_v, "sia_ugm3": si_v, "total_ugm3": tv,
        "share_pct": 100.0 * tv / tot_del_sum,
        "yr_min_pct": float(np.min(yr_shares[n])),
        "yr_max_pct": float(np.max(yr_shares[n])),
    })

del_df = pd.DataFrame(del_rows).sort_values("total_ugm3", ascending=False)
del_df.to_csv(OUT / "structured_v3_delhi_octnov_2019_2023_sector_split.csv", index=False)

print("\n=== STRUCTURED V3: DELHI (Oct-Nov 2019-2023, LOYO Out-of-Sample) — TOP 10 SOURCES ===")
print(del_df.head(10).to_string(index=False))

print("\n=== STRUCTURED V3: KEY IGP RECEPTORS (Oct-Nov 2019-2023, Top 5 % Share) ===")
for rec in ["Delhi", "Haryana", "Uttar Pradesh", "Punjab", "Bihar"]:
    if rec in oct_pct.index:
        top5 = oct_pct.loc[rec].sort_values(ascending=False).head(5)
        print(f"  {rec:<15} -> " + " | ".join([f"{k}: {v:.1f}%" for k, v in top5.items()]))

# ------------------------------------------------------------------ 4. Figures
plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold"})

# Fig 1: IGP Source Attribution Heatmap (Oct-Nov 2019-2023, %)
receptors = [r for r in ["Punjab", "Haryana", "Delhi", "Uttar Pradesh", "Bihar", "Rajasthan", "West Bengal"] if r in oct_pct.index]
sources = [s for s in [
    "ext_pak", "ind_punjab", "ind_haryana", "ind_delhi",
    "ind_uttar_pradesh", "ind_bihar", "ind_rajasthan",
    "ind_west_bengal", "ind_jharkhand", "ind_odisha",
] if s in oct_pct.columns]
sub_mat = oct_pct.loc[receptors, sources]
clean_src = [s.replace("ind_", "").replace("ext_pak", "Pakistan").replace("_", " ").title() for s in sources]

fig, ax = plt.subplots(figsize=(10.5, 5.2))
im = ax.imshow(sub_mat.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=55)
ax.set_xticks(range(len(sources)))
ax.set_xticklabels(clean_src, rotation=30, ha="right")
ax.set_yticks(range(len(receptors)))
ax.set_yticklabels(receptors)
ax.set_xlabel("Upwind Source Node")
ax.set_ylabel("Receptor State")
ax.set_title("Structured v3 (5-Yr LOYO): IGP PM2.5 Transport Attribution (Oct–Nov 2019–2023, % Share)")

for i in range(len(receptors)):
    for j in range(len(sources)):
        val = sub_mat.values[i, j]
        if val >= 1.0:
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                    color="white" if val > 30 else "black", fontsize=8.5, fontweight="bold" if val >= 15 else "normal")

cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("Share of Attributable Transport PM2.5 (%)")
fig.tight_layout()
fig.savefig(FIG / "fig1_igp_source_matrix_octnov_2019_2023.png", dpi=200)
plt.close(fig)

# Fig 2: Delhi Oct-Nov 2019-2023 Sectoral Split (Top 8 Sources)
top8 = del_df.head(8).iloc[::-1]
labels = [s.replace("ind_", "").replace("ext_pak", "Pakistan").replace("_", " ").title() for s in top8["source_node"]]

fig, ax = plt.subplots(figsize=(9.2, 4.8))
y_pos = np.arange(len(top8))
ax.barh(y_pos, top8["agri_ugm3"], color="#d95f02", label="Agriculture (Primary PM2.5)")
ax.barh(y_pos, top8["other_ugm3"], left=top8["agri_ugm3"], color="#386cb0", label="Other Sectors (Primary PM2.5)")
ax.barh(y_pos, top8["sia_ugm3"], left=top8["agri_ugm3"] + top8["other_ugm3"], color="#7570b3", label="SIA Precursors (SO2/NOx/NH3)")

for idx, (_, row) in enumerate(top8.iterrows()):
    ax.text(row["total_ugm3"] + 0.08, idx,
            f"{row['share_pct']:.1f}% ({row['yr_min_pct']:.1f}–{row['yr_max_pct']:.1f}%)",
            va="center", fontsize=8.5)

ax.set_yticks(y_pos)
ax.set_yticklabels(labels)
ax.set_xlabel("Attributable Transport PM2.5 Increment (µg/m³)")
ax.set_title("Delhi (Oct–Nov 2019–2023): Top 8 Upwind Sources by Sector (5-Yr LOYO Range)")
ax.set_xlim(0, top8["total_ugm3"].max() * 1.40)
ax.legend(loc="lower right", frameon=True)
ax.grid(axis="x", linestyle="--", alpha=0.4)
fig.tight_layout()
fig.savefig(FIG / "fig2_delhi_octnov_2019_2023_sector_split.png", dpi=200)
plt.close(fig)

# Fig 3: 5-Year LOYO Decay Parameter Stability
fig, ax = plt.subplots(figsize=(10.0, 4.6))
x = np.arange(len(param_df))
w = 0.15
colors = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e"]
for i, yr in enumerate(YEARS):
    ax.bar(x + (i - 2) * w, param_df[f"holdout_{yr}"], width=w, color=colors[i], label=f"Holdout {yr}")
ax.set_xticks(x)
ax.set_xticklabels(param_df["param"], rotation=25, ha="right")
ax.set_ylabel("Shared-Decay Weight β (µg/m³ per unit exposure)")
ax.set_title("Structured v3 Shared-Decay Parameter Stability Across 5 LOYO Folds (2019–2023)")
ax.legend(ncol=5, fontsize=8.5)
ax.grid(axis="y", linestyle="--", alpha=0.4)
fig.tight_layout()
fig.savefig(FIG / "fig3_loyo_decay_params_2019_2023.png", dpi=200)
plt.close(fig)

print(f"\nAll done in {time.time() - t0:.1f}s! Saved outputs & 3 figures to {OUT}/")
