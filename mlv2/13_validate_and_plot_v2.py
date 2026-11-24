"""
13_validate_and_plot_v2.py -- CarbonVayu mlv2
1. Reverse-year validation (Train 2022 -> Test 2021) for Structured v2 (9 params) vs C
2. Parameter stability check (2021-fitted vs 2022-fitted shared-decay weights)
3. Saves 3 publication-ready figures to results/figures/:
   - fig1_igp_source_matrix_octnov_2022.png  (Receptor x Source % heatmap)
   - fig2_delhi_octnov_2022_sector_split.png (Delhi Top 8 sources: agri/other/sia)
   - fig3_decay_params_2021_vs_2022.png      (9 decay parameters across both train years)
"""
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
OUT = Path("results")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
N_BOOT = 300

pd.set_option("display.width", 180)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# ------------------------------------------------------------------ 1. Load data
base = pd.read_parquet("data/features_daily_2021_2022.parquet")
exp2 = pd.read_parquet("data/node_exposure_v2_daily_2021_2022.parquet")
nodes = pd.read_csv("data/node_list.csv")["node_name"].tolist()

base["date"] = pd.to_datetime(base["date"])
exp2["date"] = pd.to_datetime(exp2["date"])

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
SB_V2 = [(s, b) for s in ["agri", "other", "sia"] for b in BINS]
NAMES_V2 = [f"{s}_{b}" for s, b in SB_V2]

df = base.dropna(subset=COLS_C + ["pm25"]).copy()
df["month"] = df["date"].dt.month
df["year"] = df["date"].dt.year

v2_tots = pd.DataFrame({"location_id": exp2["location_id"], "date": exp2["date"]})
for s, b in SB_V2:
    v2_tots[f"v2_tot_{s}_{b}"] = exp2[[f"exp_{n}_{s}_{b}" for n in nodes]].sum(axis=1).astype(np.float32)

df = df.merge(v2_tots, on=["location_id", "date"], how="inner").reset_index(drop=True)
cols_v2 = [f"v2_tot_{s}_{b}" for s, b in SB_V2]

# ------------------------------------------------------------------ 2. Reverse-year split (2022 -> 2021)
tr = df[df["year"] == 2022].copy().reset_index(drop=True)
te = df[df["year"] == 2021].copy().reset_index(drop=True)
print(f"Reverse-year split — Train 2022: {len(tr):,} | Test 2021: {len(te):,}")

def make_lgb(seed=0):
    return lgb.LGBMRegressor(
        n_estimators=800, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1,
        colsample_bytree=0.8, reg_lambda=1.0,
        random_state=seed, n_jobs=-1, verbose=-1,
    )

print("Cross-fitting nuisance model C on 2022 (5-fold GroupKFold by ISO-week)...")
groups_22 = tr["date"].dt.isocalendar().week.astype(int).values
oof_c = np.zeros(len(tr), dtype=np.float64)
for tr_i, va_i in GroupKFold(n_splits=5).split(tr, groups=groups_22):
    m = make_lgb(0).fit(tr.loc[tr_i, COLS_C], np.log1p(tr.loc[tr_i, "pm25"].values))
    oof_c[va_i] = np.clip(np.expm1(m.predict(tr.loc[va_i, COLS_C])), 0, None)

pred_c_te = np.mean([
    np.clip(np.expm1(make_lgb(s).fit(tr[COLS_C], np.log1p(tr["pm25"].values)).predict(te[COLS_C])), 0, None)
    for s in [0, 1, 2]
], axis=0)
resid_tr = tr["pm25"].values - oof_c

def fit_shared_decay(X_tot, y_resid):
    X_aug = np.column_stack([np.ones(len(X_tot)), X_tot])
    lb = np.array([-np.inf] + [0.0] * X_tot.shape[1])
    ub = np.full(X_tot.shape[1] + 1, np.inf)
    sol = lsq_linear(X_aug, y_resid, bounds=(lb, ub))
    return sol.x[0], sol.x[1:]

a_rev, b_rev = fit_shared_decay(tr[cols_v2].values.astype(np.float64), resid_tr)
pred_v2_te = np.clip(pred_c_te + a_rev + te[cols_v2].values @ b_rev, 0, None)

def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    rmse = np.sqrt(np.mean((y - p) ** 2))
    mae = np.mean(np.abs(y - p))
    r2 = 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)
    sp = spearmanr(y, p)[0]
    return dict(n=len(y), RMSE=rmse, MAE=mae, R2=r2, Spearman=sp)

SUBSETS = {
    "all": np.ones(len(te), bool),
    "north_box": te["in_north_india_box"].astype(bool).values,
    "delhi_OctNov": ((te["state"] == "NCT of Delhi") & te["month"].isin([10, 11])).values,
}

eval_rows = []
for name, p in [("C (local only)", pred_c_te), ("Structured v2 (9 params)", pred_v2_te)]:
    for sub, msk in SUBSETS.items():
        eval_rows.append(dict(model=name, subset=sub, **metrics(te.loc[msk, "pm25"], p[msk])))
rev_df = pd.DataFrame(eval_rows)
rev_df.to_csv(OUT / "structured_v2_reverse_2022to2021.csv", index=False)

print("\n=== REVERSE-YEAR TEST (Train 2022 -> Test 2021) ===")
print(rev_df.to_string(index=False))

# Paired block bootstrap: Structured v2 vs C on 2021 test
blk_te = (te["location_id"].astype(str) + "_" + te["date"].dt.isocalendar().week.astype(str)).values
def boot_delta(p_hi, p_lo, mask):
    y = te["pm25"].values[mask]
    b = blk_te[mask]
    e_hi, e_lo = (y - p_hi[mask]) ** 2, (y - p_lo[mask]) ** 2
    ub, inv = np.unique(b, return_inverse=True)
    n = np.bincount(inv)
    s_hi, s_lo = np.bincount(inv, e_hi), np.bincount(inv, e_lo)
    rng = np.random.default_rng(42)
    out = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(ub), len(ub))
        N = n[idx].sum()
        out.append(np.sqrt(s_lo[idx].sum() / N) - np.sqrt(s_hi[idx].sum() / N))
    return np.sqrt(e_lo.mean()) - np.sqrt(e_hi.mean()), np.percentile(out, 2.5), np.percentile(out, 97.5)

print("\n=== PAIRED BOOTSTRAP (Test 2021): Structured v2 vs C (positive = v2 better) ===")
bt_rows = []
for sub, msk in SUBSETS.items():
    pt, lo, hi = boot_delta(pred_v2_te, pred_c_te, msk)
    verdict = "better" if lo > 0 else ("worse" if hi < 0 else "not distinguishable")
    bt_rows.append(dict(subset=sub, dRMSE=pt, ci_low=lo, ci_high=hi, verdict=verdict))
print(pd.DataFrame(bt_rows).to_string(index=False))

# Compare 2021-fitted vs 2022-fitted decay parameters
p21 = pd.read_csv(OUT / "structured_v2_decay_params.csv")
p21["beta_train_2022"] = b_rev
p21.to_csv(OUT / "structured_v2_decay_params_both_years.csv", index=False)
print(f"\n=== DECAY PARAMETER STABILITY (Train 2021 vs Train 2022, intercept_22={a_rev:+.2f}) ===")
print(p21[["param", "beta_ugm3_per_unit", "beta_train_2022"]].rename(
    columns={"beta_ugm3_per_unit": "beta_train_2021"}
).to_string(index=False))

# ------------------------------------------------------------------ 3. Figures
plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold"})

# Figure 1: North India / IGP Source Attribution Heatmap (Oct-Nov 2022, %)
mat = pd.read_csv(OUT / "structured_v2_matrix_octnov_2022_pct.csv", index_col=0)
receptors = [r for r in ["Punjab", "Haryana", "NCT of Delhi", "Uttar Pradesh", "Bihar", "Rajasthan", "West Bengal"] if r in mat.index]
sources = [
    "ext_pak", "ind_punjab", "ind_haryana", "ind_delhi",
    "ind_uttar_pradesh", "ind_bihar", "ind_rajasthan",
    "ind_west_bengal", "ind_jharkhand", "ind_odisha",
]
sources = [s for s in sources if s in mat.columns]
sub_mat = mat.loc[receptors, sources]

clean_src = [s.replace("ind_", "").replace("ext_pak", "Pakistan").replace("_", " ").title() for s in sources]

fig, ax = plt.subplots(figsize=(10.5, 5.2))
im = ax.imshow(sub_mat.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=55)
ax.set_xticks(range(len(sources)))
ax.set_xticklabels(clean_src, rotation=30, ha="right")
ax.set_yticks(range(len(receptors)))
ax.set_yticklabels(receptors)
ax.set_xlabel("Upwind Source Node")
ax.set_ylabel("Receptor State")
ax.set_title("Structured v2: IGP PM2.5 Transport Attribution Matrix (Oct–Nov 2022, % Share)")

for i in range(len(receptors)):
    for j in range(len(sources)):
        val = sub_mat.values[i, j]
        if val >= 1.0:
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                    color="white" if val > 30 else "black", fontsize=8.5, fontweight="bold" if val >= 15 else "normal")

cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("Share of Attributable Transport PM2.5 (%)")
fig.tight_layout()
fig.savefig(FIG / "fig1_igp_source_matrix_octnov_2022.png", dpi=200)
plt.close(fig)

# Figure 2: Delhi Oct-Nov 2022 Sectoral Split (Top 8 Sources)
del_df = pd.read_csv(OUT / "structured_v2_delhi_octnov_2022_sector_split.csv").head(8).iloc[::-1]
labels = [s.replace("ind_", "").replace("ext_pak", "Pakistan").replace("_", " ").title() for s in del_df["source_node"]]

fig, ax = plt.subplots(figsize=(9.0, 4.8))
y_pos = np.arange(len(del_df))
b_ag = ax.barh(y_pos, del_df["agri_ugm3"], color="#d95f02", label="Agriculture (Primary PM2.5)")
b_ot = ax.barh(y_pos, del_df["other_ugm3"], left=del_df["agri_ugm3"], color="#386cb0", label="Other Sectors (Primary PM2.5)")
b_si = ax.barh(y_pos, del_df["sia_ugm3"], left=del_df["agri_ugm3"] + del_df["other_ugm3"], color="#7570b3", label="SIA Precursors (SO2/NOx/NH3)")

for idx, (_, row) in enumerate(del_df.iterrows()):
    ax.text(row["total_ugm3"] + 0.08, idx,
            f"{row['share_pct']:.1f}% [{row['pct_ci_low']:.1f}–{row['pct_ci_high']:.1f}%]",
            va="center", fontsize=8.5)

ax.set_yticks(y_pos)
ax.set_yticklabels(labels)
ax.set_xlabel("Attributable Transport PM2.5 Increment (µg/m³)")
ax.set_title("NCT of Delhi (Oct–Nov 2022): Top 8 Upwind Sources by Sector (Structured v2)")
ax.set_xlim(0, del_df["total_ugm3"].max() * 1.38)
ax.legend(loc="lower right", frameon=True)
ax.grid(axis="x", linestyle="--", alpha=0.4)
fig.tight_layout()
fig.savefig(FIG / "fig2_delhi_octnov_2022_sector_split.png", dpi=200)
plt.close(fig)

# Figure 3: Decay Parameter Stability (Train 2021 vs Train 2022)
fig, ax = plt.subplots(figsize=(9.2, 4.4))
x = np.arange(len(p21))
w = 0.36
ax.bar(x - w/2, p21["beta_ugm3_per_unit"], width=w, color="#1b9e77", label="Trained on 2021")
ax.bar(x + w/2, p21["beta_train_2022"], width=w, color="#e7298a", label="Trained on 2022")
ax.set_xticks(x)
ax.set_xticklabels(p21["param"], rotation=25, ha="right")
ax.set_ylabel("Shared-Decay Weight β (µg/m³ per unit exposure)")
ax.set_title("Structured v2 Shared-Decay Parameter Stability (2021 vs 2022)")
ax.legend()
ax.grid(axis="y", linestyle="--", alpha=0.4)
fig.tight_layout()
fig.savefig(FIG / "fig3_decay_params_2021_vs_2022.png", dpi=200)
plt.close(fig)

print(f"\nSaved 3 figures to {FIG}/")
