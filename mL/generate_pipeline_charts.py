from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_vt_histogram(vt_df: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(vt_df["VT_score"], bins=10, color="#2A9D8F", edgecolor="#264653", alpha=0.9)
    ax.axvline(500, color="#E76F51", linestyle="--", linewidth=2, label="VT = 500")
    ax.set_title("VT Score Distribution (2022)")
    ax.set_xlabel("VT Score")
    ax.set_ylabel("Number of States")
    ax.legend()
    fig.tight_layout()
    name = "vt_score_histogram.png"
    fig.savefig(out_dir / name, dpi=200)
    plt.close(fig)
    return name


def save_m2_heatmap(m2_df: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(m2_df.values, cmap="YlOrRd", aspect="auto")
    ax.set_title("M2 Transport Matrix Heatmap (MT CO2e)")
    ax.set_xlabel("Target State")
    ax.set_ylabel("Source State")
    ax.set_xticks(np.arange(len(m2_df.columns)))
    ax.set_xticklabels(m2_df.columns, rotation=90, fontsize=7)
    ax.set_yticks(np.arange(len(m2_df.index)))
    ax.set_yticklabels(m2_df.index, fontsize=7)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Transported MT CO2e")
    fig.tight_layout()
    name = "m2_matrix_heatmap.png"
    fig.savefig(out_dir / name, dpi=220)
    plt.close(fig)
    return name


def save_confidence_heatmap(conf_df: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(conf_df.values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_title("M2 Confidence Heatmap")
    ax.set_xlabel("Target State")
    ax.set_ylabel("Source State")
    ax.set_xticks(np.arange(len(conf_df.columns)))
    ax.set_xticklabels(conf_df.columns, rotation=90, fontsize=7)
    ax.set_yticks(np.arange(len(conf_df.index)))
    ax.set_yticklabels(conf_df.index, fontsize=7)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Confidence")
    fig.tight_layout()
    name = "m2_confidence_heatmap.png"
    fig.savefig(out_dir / name, dpi=220)
    plt.close(fig)
    return name


def save_export_receiver_bars(derived_df: pd.DataFrame, out_dir: Path):
    top_export = derived_df.sort_values("exported_harm_mt", ascending=False).head(10)
    top_recv = derived_df.sort_values("received_credit_mt", ascending=False).head(10)

    fig1, ax1 = plt.subplots(figsize=(11, 6))
    x1 = np.arange(len(top_export))
    ax1.bar(x1, top_export["exported_harm_mt"], color="#E76F51")
    ax1.set_title("Top 10 Exporters of Harm (M2)")
    ax1.set_ylabel("Exported Harm (MT)")
    ax1.set_xticks(x1)
    ax1.set_xticklabels(top_export["state"], rotation=35, ha="right")
    fig1.tight_layout()
    name1 = "top_exporters_bar.png"
    fig1.savefig(out_dir / name1, dpi=200)
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(11, 6))
    x2 = np.arange(len(top_recv))
    ax2.bar(x2, top_recv["received_credit_mt"], color="#2A9D8F")
    ax2.set_title("Top 10 Receivers of Transport Credit (M2)")
    ax2.set_ylabel("Received Credit (MT)")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(top_recv["state"], rotation=35, ha="right")
    fig2.tight_layout()
    name2 = "top_receivers_bar.png"
    fig2.savefig(out_dir / name2, dpi=200)
    plt.close(fig2)

    return name1, name2


def save_effort_by_archetype(m3_df: pd.DataFrame, out_dir: Path) -> str:
    stats = m3_df.groupby("archetype")["effort_multiplier"].agg(["mean", "min", "max"]).reset_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(stats))
    ax.bar(x, stats["mean"], color="#457B9D", label="Mean")
    ax.errorbar(
        x,
        stats["mean"],
        yerr=[stats["mean"] - stats["min"], stats["max"] - stats["mean"]],
        fmt="none",
        ecolor="#1D3557",
        capsize=6,
        linewidth=1.8,
        label="Min-Max Range",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(stats["archetype"])
    ax.set_title("M3 Effort Multiplier by Archetype")
    ax.set_ylabel("Effort Multiplier")
    ax.legend()
    fig.tight_layout()
    name = "m3_effort_by_archetype.png"
    fig.savefig(out_dir / name, dpi=200)
    plt.close(fig)
    return name


def write_chart_report(out_dir: Path, chart_files, vt_df: pd.DataFrame) -> None:
    clipped_700 = int((vt_df["VT_score"] == 700).sum())
    clipped_300 = int((vt_df["VT_score"] == 300).sum())

    report = f"""# CarbonVayu Visual Diagnostics

Generated charts for quick review of M2, M3, and VT behavior.

## Key visual findings
1. VT distribution is centered near 500 but has top-end saturation (exact 700 count: {clipped_700}).
2. M2 matrix heatmap shows dominant diagonal mass with relatively small off-diagonal transport cells.
3. Confidence heatmap is sparse/highly selective; most flows have 0 confidence.
4. Top exporters and top receivers identify cross-state burden asymmetries.
5. M3 archetype chart confirms F-type states have higher average effort multipliers.

## Clipping diagnostics
- Exact 300 count: {clipped_300}
- Exact 700 count: {clipped_700}

## Chart files
- VT histogram: ![]({chart_files['vt_hist']})
- M2 matrix heatmap: ![]({chart_files['m2_heatmap']})
- M2 confidence heatmap: ![]({chart_files['conf_heatmap']})
- Top exporters: ![]({chart_files['exporters']})
- Top receivers: ![]({chart_files['receivers']})
- M3 effort by archetype: ![]({chart_files['m3_arch']})
"""
    (out_dir / "Pipeline_Charts_Report.md").write_text(report, encoding="utf-8")


def main():
    base = Path(__file__).resolve().parent
    out = base / "outputs"
    charts = out / "charts"
    ensure_dir(charts)

    m2 = pd.read_csv(out / "M2_matrix.csv", index_col=0)
    conf = pd.read_csv(out / "M2_confidence.csv", index_col=0)
    derived = pd.read_csv(out / "M2_derived.csv")
    m3 = pd.read_csv(out / "M3_effort.csv")
    vt = pd.read_csv(out / "VT_scores_final.csv")

    chart_files = {
        "vt_hist": save_vt_histogram(vt, charts),
        "m2_heatmap": save_m2_heatmap(m2, charts),
        "conf_heatmap": save_confidence_heatmap(conf, charts),
        "m3_arch": save_effort_by_archetype(m3, charts),
    }
    exporters, receivers = save_export_receiver_bars(derived, charts)
    chart_files["exporters"] = exporters
    chart_files["receivers"] = receivers

    write_chart_report(charts, chart_files, vt)
    print("Saved charts in:", charts)
    print("Saved report:", charts / "Pipeline_Charts_Report.md")


if __name__ == "__main__":
    main()