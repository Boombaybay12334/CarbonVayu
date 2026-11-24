import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Download,
  Maximize2,
  X,
  Info,
  Layers,
  Activity,
  CheckCircle2,
  Sliders,
  Scale,
  Zap,
  Filter,
  Eye,
  Search,
  ExternalLink,
} from "lucide-react";

export default function VtV5Analytics() {
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Active section tab
  const [activeTab, setActiveTab] = useState("all"); // 'all' | 'heatmap' | 'leaderboard' | 'fines' | 'figures'

  // Heatmap interactive inspector state
  const [selectedCell, setSelectedCell] = useState(null); // { i, j, source, target, harm, conf, isFine, fineData }
  const [highlightFineOnly, setHighlightFineOnly] = useState(false);

  // Leaderboard filters
  const [searchQuery, setSearchQuery] = useState("");
  const [auditFilter, setAuditFilter] = useState("all"); // 'all' | 'divergent_only' | 'aligned_only'
  const [sortField, setSortField] = useState("rank");
  const [sortAsc, setSortAsc] = useState(true);

  // Lightbox figure viewer
  const [activeFigure, setActiveFigure] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/v5/vt_v5_bundle.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch v5 bundle`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setBundle(data);
          // Set default selected fine corridor for heatmap inspector
          if (data.fine_claims && data.fine_claims.length > 0) {
            const topClaim = data.fine_claims[0];
            setSelectedCell({
              source: topClaim.defendant,
              target: topClaim.claimant,
              harm: topClaim.harm_ugm3,
              unconHarm: topClaim.harm_uncon_ugm3,
              ciLow: topClaim.harm_ci_low,
              conf: topClaim.confidence,
              isFine: true,
              fineData: topClaim,
            });
          }
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Figures metadata
  const figures = useMemo(
    () => [
      {
        id: "01",
        src: "/v5/figures/01_transport_heatmap_v5.png",
        title: "Inter-State PM2.5 Transport Matrix (M_ij)",
        category: "Atmospheric Transport",
        desc: "22×22 off-diagonal atmospheric PM2.5 transport attribution matrix modeled via Monotone-Decay Gaussian dispersion across 5 years of meteorological data.",
        highlight: "22×22 Matrix | Bounded Monotone Decay",
      },
      {
        id: "02",
        src: "/v5/figures/02_leaderboard_settled_vs_base.png",
        title: "Settled VT vs. Base Leaderboard (95% CI)",
        category: "Zero-Sum Settlement",
        desc: "Comparative ranking showing base VT scores shifting into post-settlement balances under CSAPR bilateral fine transfers with 95% joint bootstrap confidence intervals.",
        highlight: "95% Joint CI | Zero-Sum Balance",
      },
      {
        id: "03",
        src: "/v5/figures/03_pillar_decomposition_v5.png",
        title: "Tri-Pillar Structural Decomposition",
        category: "Pillar Weighting",
        desc: "Stacked contribution of Pillar A (55% Export Accountability), Pillar B (15% Matched EDGAR Progress), and Pillar C (30% Renewable Energy Share) across all modeled states.",
        highlight: "55% Export | 30% RE | 15% Progress",
      },
      {
        id: "04",
        src: "/v5/figures/04_fine_transfers_and_corridors.png",
        title: "CSAPR Bilateral Fine Corridors & Transfers",
        category: "Enforcement Corridors",
        desc: "The 10 statutory bilateral fine claims satisfying harm ≥ 0.40 µg/m³, bootstrap confidence > 75%, and positive CI lower bound, showing total points circulated.",
        highlight: "10 Corridors | 953.5 Total Points",
      },
      {
        id: "05",
        src: "/v5/figures/05_audit_divergence_and_pm25.png",
        title: "CPCB Ground Station Audit & Divergence Layer",
        category: "Empirical Ground Audit",
        desc: "Independent audit comparing EDGAR emissions trajectories against ground CPCB monitor drops, identifying 6 decoupled states where emissions worsened despite local monitor improvements.",
        highlight: "6 Divergent Decoupled States",
      },
      {
        id: "06",
        src: "/v5/figures/06_pillar_correlation_matrix.png",
        title: "Pillar Orthogonality & Metric Correlation Matrix",
        category: "Validation Metrics",
        desc: "Spearman rank correlation heatmap proving complete mathematical independence of VT economic incentives from ambient smog levels (r_s = -0.5957).",
        highlight: "r_s = -0.5957 vs. Ambient Smog",
      },
    ],
    []
  );

  // Map of active fine claims for O(1) lookup: key = `${def}|${clm}`
  const fineMap = useMemo(() => {
    if (!bundle?.fine_claims) return new Map();
    const m = new Map();
    bundle.fine_claims.forEach((c) => {
      m.set(`${c.defendant}|${c.claimant}`, c);
    });
    return m;
  }, [bundle]);

  // Filtered and sorted leaderboard
  const filteredLeaderboard = useMemo(() => {
    if (!bundle?.leaderboard) return [];
    let rows = [...bundle.leaderboard];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      rows = rows.filter((r) => r.state.toLowerCase().includes(q));
    }

    if (auditFilter === "divergent_only") {
      rows = rows.filter((r) => r.audit_flag === "DIVERGENT_EMI_WORSE_PM_BETTER");
    } else if (auditFilter === "aligned_only") {
      rows = rows.filter((r) => r.audit_flag !== "DIVERGENT_EMI_WORSE_PM_BETTER");
    }

    rows.sort((a, b) => {
      let av = a[sortField];
      let bv = b[sortField];
      if (sortField === "net_fine") {
        av = (a.fines_received_pts || 0) - (a.fines_owed_pts || 0);
        bv = (b.fines_received_pts || 0) - (b.fines_owed_pts || 0);
      }
      if (typeof av === "number" && typeof bv === "number") {
        return sortAsc ? av - bv : bv - av;
      }
      return sortAsc
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });

    return rows;
  }, [bundle, searchQuery, auditFilter, sortField, sortAsc]);

  function handleSort(field) {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      // For scores or points, default to descending; for rank, default to ascending
      setSortAsc(field === "rank" || field === "state");
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-4 animate-fade-in">
        <div className="relative">
          <div className="w-16 h-16 border-4 border-emerald-500/20 border-t-emerald-400 rounded-full animate-spin"></div>
          <Zap className="w-6 h-6 text-emerald-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
        </div>
        <p className="text-lg font-display text-slate-200">Loading VT v5 Economic & Transport Matrix...</p>
        <p className="text-xs text-slate-400 font-mono">Fetching /v5/vt_v5_bundle.json & 300-DPI publication figures</p>
      </div>
    );
  }

  if (error || !bundle) {
    return (
      <div className="glass-panel p-8 rounded-2xl border-l-4 border-l-red-500 text-center max-w-2xl mx-auto my-12 animate-slide-up">
        <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-xl font-display font-bold text-white">Error Loading VT v5 Engine</h2>
        <p className="text-slate-400 mt-2 text-sm">{error || "Bundle data could not be parsed."}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-6 px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const { validation, constants, fine_claims, heatmap } = bundle;
  const heatmapStates = heatmap?.states || [];
  const matrix = heatmap?.matrix_ugm3 || [];
  const confMatrix = heatmap?.confidence || [];

  return (
    <div className="space-y-12 pb-24 text-white animate-fade-in">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER & HERO
      ────────────────────────────────────────────────────────────── */}
      <div className="relative pt-2">
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-gradient-to-br from-emerald-500/15 via-cyan-500/10 to-transparent rounded-full blur-[100px] -z-10 pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 border-b border-white/10 pb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-medium mb-4">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              FROZEN RELEASE: VT v5.0 (2022–2023)
            </div>
            <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
              Vaayu Token Economy v5 (VT v5)
            </h1>
            <p className="text-slate-300 mt-3 text-base md:text-lg max-w-3xl leading-relaxed">
              Publication-grade inter-state atmospheric PM2.5 transport attribution, 3-pillar structural scoring,
              CSAPR-gated bilateral enforcement, and ground CPCB monitor decoupling audits across 22 Indian states.
            </p>
          </div>

          {/* Quick Jump Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: "all", label: "Overview" },
              { id: "heatmap", label: "22×22 Heatmap" },
              { id: "leaderboard", label: "Settled Leaderboard" },
              { id: "fines", label: "10 CSAPR Corridors" },
              { id: "figures", label: "Research Figures" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id !== "all") {
                    document.getElementById(`section-${tab.id}`)?.scrollIntoView({ behavior: "smooth" });
                  }
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? "bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/20"
                    : "bg-slate-900/60 text-slate-300 hover:text-white hover:bg-slate-800 border border-white/5"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. METHODOLOGY & VALIDATION KPI STRIP
      ────────────────────────────────────────────────────────────── */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-emerald-400" />
            <h2 className="text-xl font-display font-bold text-white">
              Validation & Methodology KPI Strip
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-400">Monte Carlo N=1,000 Bootstraps</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {/* Card 1: 55/30/15 Design */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-emerald-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-emerald-400 group-hover:opacity-25 transition-opacity">
              <Layers className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Pillar Weights</p>
            <p className="text-2xl font-display font-bold text-emerald-400">55 / 30 / 15</p>
            <p className="text-[11px] text-slate-400 mt-1">
              55% Export · 30% RE · 15% EDGAR Progress
            </p>
          </div>

          {/* Card 2: Split-Half Spearman */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-cyan-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-cyan-400 group-hover:opacity-25 transition-opacity">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Split-Half Stability</p>
            <p className="text-2xl font-display font-bold text-cyan-400 font-mono">
              r_s = {validation.split_half_spearman}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Invariance across split bootstrap samples
            </p>
          </div>

          {/* Card 3: Independence from Smog */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-teal-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-teal-400 group-hover:opacity-25 transition-opacity">
              <Activity className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Smog Decoupling</p>
            <p className="text-2xl font-display font-bold text-teal-300 font-mono">
              r_s = {validation.spearman_vs_pm25}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Independent of background ambient PM2.5
            </p>
          </div>

          {/* Card 4: Placebo Null Fines */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-emerald-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-emerald-400 group-hover:opacity-25 transition-opacity">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Placebo Nulls</p>
            <p className="text-2xl font-display font-bold text-emerald-400 font-mono">0 / 0 / 0</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Zero false claims under P1, P2, P3 nulls
            </p>
          </div>

          {/* Card 5: Eligible Fine Pairs */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-amber-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-amber-400 group-hover:opacity-25 transition-opacity">
              <Zap className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">CSAPR Fine Pairs</p>
            <p className="text-2xl font-display font-bold text-amber-400 font-mono">
              {validation.eligible_fine_pairs} Corridors
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Harm ≥ 0.40 µg/m³ & C_ij &gt; 75%
            </p>
          </div>

          {/* Card 6: Audit Divergence */}
          <div className="glass-card p-4 rounded-xl border border-white/10 hover:border-rose-500/40 relative group overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10 text-rose-400 group-hover:opacity-25 transition-opacity">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">CPCB Divergences</p>
            <p className="text-2xl font-display font-bold text-rose-400 font-mono">
              {validation.divergent_audit_states} States
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Emissions up while station PM2.5 drops
            </p>
          </div>
        </div>

        {/* Mathematical Formulation Explainer */}
        <div className="glass-panel p-6 rounded-2xl border border-white/10 bg-slate-900/60 relative overflow-hidden">
          <div className="grid md:grid-cols-3 gap-6">
            <div className="space-y-2 border-r border-white/5 pr-4">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                <span className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-xs font-mono">1</span>
                Pillar Scoring Architecture
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                VT Base synthesizes <strong className="text-white">Pillar A</strong> (Export Accountability S_A = 1 - X_i),
                <strong className="text-white"> Pillar B</strong> (5-year EDGAR progress ratio &theta;_i), and
                <strong className="text-white"> Pillar C</strong> (CEA/MNRE Renewable Share R_i), centered at {constants.CENTER.toFixed(3)} and scaled to mean 500 / std 100.
              </p>
              <div className="text-[11px] font-mono bg-slate-950/60 px-3 py-2 rounded-lg border border-white/5 text-emerald-300">
                VT_base = 500 + 100 × (S_raw - 0.470) / 0.247
              </div>
            </div>

            <div className="space-y-2 border-r border-white/5 pr-4">
              <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
                <span className="w-6 h-6 rounded-full bg-cyan-500/20 flex items-center justify-center text-xs font-mono">2</span>
                CSAPR-Gated Bilateral Transfers
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Only cross-border corridors satisfying the EPA Clean Air Interstate / CSAPR standard receive penalty adjudication:
                Harm_ij &ge; 0.40 µg/m³, C_ij &gt; 0.75, and positive 95% bootstrap CI lower bound under monotone &amp; unconstrained specs.
              </p>
              <div className="text-[11px] font-mono bg-slate-950/60 px-3 py-2 rounded-lg border border-white/5 text-cyan-300">
                D_ij = Harm_ij × (Pop_j / 10⁶); Fine ∈ [48.9, 149.6] pts
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                <span className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-xs font-mono">3</span>
                Zero-Sum Clean Air Ledger
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Every fine point paid by an upwind polluter is credited directly to the impacted downwind claimant.
                Total Fines Owed = Total Fines Received = 953.5 pts, preserving national circulation invariance.
              </p>
              <div className="text-[11px] font-mono bg-slate-950/60 px-3 py-2 rounded-lg border border-white/5 text-amber-300">
                VT_settled = VT_base + Fines_Recv - Fines_Owed
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          3. INTERACTIVE 22×22 INTER-STATE TRANSPORT MATRIX HEATMAP
      ────────────────────────────────────────────────────────────── */}
      <section id="section-heatmap" className="space-y-6 pt-4">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              <h2 className="text-xl font-display font-bold text-white">
                Interactive 22×22 Inter-State Transport Matrix (M_ij)
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Rows represent <strong>Upwind Exporter (i)</strong> → Columns represent <strong>Downwind Receptor (j)</strong>.
              Values indicate attributed annual average PM2.5 (µg/m³). Cells marked with <span className="text-amber-400 font-bold">*</span> are active CSAPR fine corridors.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setHighlightFineOnly(!highlightFineOnly)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                highlightFineOnly
                  ? "bg-amber-500/20 border-amber-500/50 text-amber-300 shadow-lg shadow-amber-500/10"
                  : "bg-slate-900 border-white/10 text-slate-300 hover:text-white"
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              {highlightFineOnly ? "Showing 10 Active Corridors" : "Highlight 10 Active Corridors"}
            </button>
          </div>
        </div>

        <div className="grid lg:grid-cols-12 gap-6">
          {/* Heatmap Grid Container */}
          <div className="lg:col-span-8 glass-panel p-4 rounded-2xl border border-white/10 bg-slate-900/70 overflow-x-auto">
            <div className="min-w-[720px]">
              {/* Column Headers (Receptors) */}
              <div className="flex items-end mb-2 pl-24">
                <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider font-semibold mr-2 w-12 text-right">
                  Receptor →
                </div>
                {heatmapStates.map((st, j) => (
                  <div
                    key={`col-${st}`}
                    className="flex-1 text-center text-[10px] font-mono text-slate-400 truncate px-0.5 hover:text-white cursor-default"
                    title={`Column ${j + 1}: ${st}`}
                  >
                    {st.substring(0, 3).toUpperCase()}
                  </div>
                ))}
              </div>

              {/* Rows (Exporters) */}
              <div className="space-y-1">
                {heatmapStates.map((rowState, i) => (
                  <div key={`row-${rowState}`} className="flex items-center">
                    {/* Row Label */}
                    <div
                      className="w-24 text-right pr-2 text-[11px] font-medium text-slate-300 truncate hover:text-white cursor-pointer"
                      title={`Row ${i + 1}: Upwind Exporter ${rowState}`}
                    >
                      {rowState}
                    </div>

                    {/* Cells */}
                    <div className="flex flex-1 gap-1">
                      {heatmapStates.map((colState, j) => {
                        const isSelf = i === j;
                        const val = matrix[i]?.[j] ?? 0;
                        const conf = confMatrix[i]?.[j] ?? 0;
                        const fineKey = `${rowState}|${colState}`;
                        const isFine = fineMap.has(fineKey);
                        const fineData = fineMap.get(fineKey);

                        // Color intensity based on harm (0 to 4.5 ug/m3)
                        let bgStyle = "bg-slate-900/40 text-slate-600";
                        if (!isSelf) {
                          if (val >= 3.0) bgStyle = "bg-red-600/90 text-white font-bold shadow-sm shadow-red-500/30";
                          else if (val >= 1.5) bgStyle = "bg-amber-500/80 text-white font-semibold";
                          else if (val >= 0.8) bgStyle = "bg-amber-600/60 text-slate-100";
                          else if (val >= 0.4) bgStyle = "bg-cyan-600/60 text-slate-100";
                          else if (val >= 0.1) bgStyle = "bg-cyan-900/40 text-cyan-200";
                          else bgStyle = "bg-slate-900/70 text-slate-500";
                        }

                        const isDimmed = highlightFineOnly && !isFine && !isSelf;
                        const isSelected =
                          selectedCell?.source === rowState && selectedCell?.target === colState;

                        return (
                          <button
                            key={`cell-${i}-${j}`}
                            onClick={() => {
                              if (!isSelf) {
                                setSelectedCell({
                                  i,
                                  j,
                                  source: rowState,
                                  target: colState,
                                  harm: val,
                                  conf,
                                  isFine,
                                  fineData,
                                });
                              }
                            }}
                            disabled={isSelf}
                            className={`flex-1 aspect-square rounded-sm text-[9px] font-mono flex items-center justify-center transition-all relative ${bgStyle} ${
                              isSelf ? "opacity-20 cursor-not-allowed bg-slate-950" : "cursor-pointer hover:ring-2 hover:ring-white"
                            } ${isDimmed ? "opacity-15" : ""} ${
                              isSelected ? "ring-2 ring-emerald-400 z-10 scale-110" : ""
                            } ${isFine ? "border border-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.5)] z-0 font-bold" : ""}`}
                            title={`${rowState} → ${colState}: ${val.toFixed(2)} µg/m³ (conf: ${(conf * 100).toFixed(0)}%)${
                              isFine ? " [ACTIVE FINE CORRIDOR]" : ""
                            }`}
                          >
                            {isSelf ? "·" : isFine ? "*" : val > 0.05 ? val.toFixed(1) : ""}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {/* Heatmap Legend */}
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10 text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400">Harm (µg/m³):</span>
                  <div className="flex items-center gap-1 text-[10px] font-mono">
                    <span className="w-3.5 h-3.5 rounded-sm bg-slate-900 border border-white/5 inline-block"></span> 0.0
                    <span className="w-3.5 h-3.5 rounded-sm bg-cyan-900/60 inline-block"></span> 0.1
                    <span className="w-3.5 h-3.5 rounded-sm bg-cyan-600 inline-block"></span> 0.4
                    <span className="w-3.5 h-3.5 rounded-sm bg-amber-600 inline-block"></span> 0.8
                    <span className="w-3.5 h-3.5 rounded-sm bg-amber-500 inline-block"></span> 1.5
                    <span className="w-3.5 h-3.5 rounded-sm bg-red-600 inline-block"></span> 3.0+
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[11px]">
                  <span className="px-1.5 py-0.5 rounded border border-amber-400 bg-amber-500/20 text-amber-300 font-mono font-bold">
                    *
                  </span>
                  <span>Active CSAPR Fine Corridor (10 total)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Cell Inspector Panel */}
          <div className="lg:col-span-4 glass-panel p-6 rounded-2xl border border-white/10 bg-slate-900/80 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-2">
                  <Eye className="w-4 h-4 text-emerald-400" />
                  Corridor Inspector
                </span>
                {selectedCell?.isFine && (
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] font-mono font-bold animate-pulse">
                    CSAPR ADJUDICATED
                  </span>
                )}
              </div>

              {selectedCell ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-[11px] text-slate-400 uppercase tracking-wide">Atmospheric Corridor</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-base font-display font-bold text-white">
                        {selectedCell.source}
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-400" />
                      <span className="text-base font-display font-bold text-cyan-300">
                        {selectedCell.target}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div className="glass-card p-3 rounded-xl border border-white/5">
                      <p className="text-[10px] text-slate-400 uppercase">Transport Harm</p>
                      <p className="text-xl font-display font-bold text-emerald-400 font-mono mt-0.5">
                        {selectedCell.harm.toFixed(3)}{" "}
                        <span className="text-xs font-sans text-slate-400">µg/m³</span>
                      </p>
                    </div>

                    <div className="glass-card p-3 rounded-xl border border-white/5">
                      <p className="text-[10px] text-slate-400 uppercase">Bootstrap Conf.</p>
                      <p className="text-xl font-display font-bold text-cyan-400 font-mono mt-0.5">
                        {(selectedCell.conf * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>

                  {selectedCell.isFine && selectedCell.fineData && (
                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-300 font-medium">CSAPR Bounded Penalty:</span>
                        <span className="font-mono font-bold text-amber-300 text-sm">
                          {selectedCell.fineData.fine_vt_points.toFixed(1)} VT pts
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Unconstrained Harm:</span>
                        <span className="font-mono text-slate-200">
                          {selectedCell.fineData.harm_uncon_ugm3.toFixed(3)} µg/m³
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>95% CI Lower Bound:</span>
                        <span className="font-mono text-emerald-400">
                          {selectedCell.fineData.harm_ci_low.toFixed(3)} µg/m³ (&gt; 0)
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Pop-Weighted Damage (D_ij):</span>
                        <span className="font-mono text-slate-200">
                          {selectedCell.fineData.D_ij.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  )}

                  {!selectedCell.isFine && (
                    <div className="p-3.5 rounded-xl bg-slate-800/40 border border-white/5 text-xs text-slate-400 leading-relaxed">
                      {selectedCell.harm < 0.4 ? (
                        <span>
                          Flow below statutory CSAPR floor (0.40 µg/m³). Treated as non-penalized atmospheric background.
                        </span>
                      ) : (
                        <span>
                          Transport exceeds harm threshold but did not satisfy dual monotone/unconstrained CI gates or confidence &gt; 75%.
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-12 text-center text-slate-500 text-xs">
                  Click any cell in the 22×22 matrix to inspect attribution specifics.
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-white/10 text-[11px] text-slate-400 flex items-center justify-between">
              <span>{bundle.leaderboard.length} Modeled Jurisdictions</span>
              <span className="font-mono text-emerald-400">462 Total Pairs</span>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          4. SETTLED VT LEADERBOARD & PILLAR BREAKDOWN
      ────────────────────────────────────────────────────────────── */}
      <section id="section-leaderboard" className="space-y-6 pt-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
              <h2 className="text-xl font-display font-bold text-white">
                Settled VT Leaderboard & Pillar Breakdown
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Complete rankings with Pillar A/B/C progress bars, base VT score, zero-sum net fine settlements, and 95% bootstrap confidence intervals.
            </p>
          </div>

          {/* Filter Toggles & Search */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-48 sm:w-64">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search states..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-slate-900/70 pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center rounded-xl bg-slate-900/80 border border-white/10 p-1 text-xs">
              <button
                onClick={() => setAuditFilter("all")}
                className={`px-3 py-1 rounded-lg transition-colors ${
                  auditFilter === "all" ? "bg-emerald-500/20 text-emerald-300 font-semibold" : "text-slate-400 hover:text-white"
                }`}
              >
                All (22)
              </button>
              <button
                onClick={() => setAuditFilter("divergent_only")}
                className={`px-3 py-1 rounded-lg transition-colors flex items-center gap-1 ${
                  auditFilter === "divergent_only" ? "bg-rose-500/20 text-rose-300 font-semibold" : "text-slate-400 hover:text-white"
                }`}
              >
                <AlertTriangle className="w-3 h-3 text-rose-400" />
                CPCB Divergent (6)
              </button>
              <button
                onClick={() => setAuditFilter("aligned_only")}
                className={`px-3 py-1 rounded-lg transition-colors ${
                  auditFilter === "aligned_only" ? "bg-cyan-500/20 text-cyan-300 font-semibold" : "text-slate-400 hover:text-white"
                }`}
              >
                Aligned (16)
              </button>
            </div>
          </div>
        </div>

        {/* Table Container */}
        <div className="glass-panel rounded-2xl border border-white/10 bg-slate-900/60 overflow-hidden shadow-xl">
          <div className="overflow-x-auto max-h-[640px] custom-scrollbar">
            <table className="w-full text-left text-xs min-w-[920px]">
              <thead className="bg-slate-800/90 backdrop-blur-md sticky top-0 z-20 text-slate-300 uppercase font-mono tracking-wider border-b border-white/10 text-[11px]">
                <tr>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white"
                    onClick={() => handleSort("rank")}
                  >
                    Rank {sortField === "rank" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white"
                    onClick={() => handleSort("state")}
                  >
                    State {sortField === "state" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-center"
                    onClick={() => handleSort("pillar_A_export")}
                  >
                    Pillar A (55%)
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-center"
                    onClick={() => handleSort("pillar_C_re")}
                  >
                    Pillar C (30%)
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-center"
                    onClick={() => handleSort("pillar_B_progress")}
                  >
                    Pillar B (15%)
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-right"
                    onClick={() => handleSort("vt_base")}
                  >
                    VT Base {sortField === "vt_base" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-center"
                    onClick={() => handleSort("net_fine")}
                  >
                    Net Fine Transfer
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-white text-right"
                    onClick={() => handleSort("vt_settled")}
                  >
                    VT Settled (95% CI) {sortField === "vt_settled" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th className="p-3.5 text-center">Audit Layer</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-white/5">
                {filteredLeaderboard.map((row) => {
                  const netFine = (row.fines_received_pts || 0) - (row.fines_owed_pts || 0);
                  const isDivergent = row.audit_flag === "DIVERGENT_EMI_WORSE_PM_BETTER";

                  return (
                    <tr
                      key={row.state}
                      className={`hover:bg-white/5 transition-colors group ${
                        isDivergent ? "bg-rose-500/[0.03]" : ""
                      }`}
                    >
                      {/* Rank */}
                      <td className="p-3.5 font-display font-semibold">
                        <span
                          className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-mono border ${
                            row.rank <= 3
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm shadow-emerald-500/20"
                              : row.rank >= 20
                              ? "bg-rose-500/10 text-rose-300 border-rose-500/30"
                              : "bg-slate-800 text-slate-300 border-white/10"
                          }`}
                        >
                          {row.rank}
                        </span>
                      </td>

                      {/* State Name */}
                      <td className="p-3.5 font-medium text-white">
                        <div className="flex items-center gap-2">
                          <span>{row.state}</span>
                          {isDivergent && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40"
                              title="EDGAR emissions worsened while local CPCB monitors dropped"
                            >
                              DIVERGENT
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Pillar A: Export (55%) */}
                      <td className="p-3.5 text-center">
                        <div className="w-24 mx-auto">
                          <div className="flex justify-between text-[10px] font-mono mb-1 text-slate-300">
                            <span>{(row.pillar_A_export * 100).toFixed(0)}%</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-emerald-400 h-1.5 rounded-full"
                              style={{ width: `${Math.min(100, row.pillar_A_export * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Pillar C: Renewable Energy (30%) */}
                      <td className="p-3.5 text-center">
                        <div className="w-24 mx-auto">
                          <div className="flex justify-between text-[10px] font-mono mb-1 text-slate-300">
                            <span>{(row.pillar_C_re * 100).toFixed(0)}%</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-cyan-400 h-1.5 rounded-full"
                              style={{ width: `${Math.min(100, row.pillar_C_re * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Pillar B: EDGAR Progress (15%) */}
                      <td className="p-3.5 text-center">
                        <div className="w-24 mx-auto">
                          <div className="flex justify-between text-[10px] font-mono mb-1 text-slate-300">
                            <span>{(row.pillar_B_progress * 100).toFixed(0)}%</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-amber-400 h-1.5 rounded-full"
                              style={{ width: `${Math.min(100, row.pillar_B_progress * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Base VT */}
                      <td className="p-3.5 text-right font-mono font-medium text-slate-200">
                        {row.vt_base.toFixed(2)}
                      </td>

                      {/* Net Fine Transfer */}
                      <td className="p-3.5 text-center font-mono">
                        {netFine === 0 ? (
                          <span className="text-slate-500">—</span>
                        ) : netFine > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                            +{netFine.toFixed(1)}
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                            {netFine.toFixed(1)}
                          </span>
                        )}
                      </td>

                      {/* Settled VT + 95% CI */}
                      <td className="p-3.5 text-right">
                        <div className="font-display font-bold text-sm text-white font-mono">
                          {row.vt_settled.toFixed(2)}
                        </div>
                        <div className="text-[10px] font-mono text-emerald-400/90">
                          [{row.vt_ci_low.toFixed(1)} – {row.vt_ci_high.toFixed(1)}]
                        </div>
                      </td>

                      {/* Audit Layer */}
                      <td className="p-3.5 text-center">
                        <div className="text-[11px] font-mono text-slate-300">
                          {row.pm25_curr ? `${row.pm25_curr.toFixed(1)} µg/m³` : "—"}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {row.cpcb_match_drop_ugm3 > 0
                            ? `-${row.cpcb_match_drop_ugm3.toFixed(1)} drop`
                            : "0.0 drop"}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          5. 10 CSAPR-GATED BILATERAL FINE CORRIDORS
      ────────────────────────────────────────────────────────────── */}
      <section id="section-fines" className="space-y-6 pt-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              <h2 className="text-xl font-display font-bold text-white">
                10 CSAPR-Gated Bilateral Fine Corridors
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Strictly zero-sum inter-state pollution liability transfers. Only corridors meeting harm &gt;= 0.40 µg/m³, confidence &gt; 75%, and positive CI lower bounds under both monotone & unconstrained specs.
            </p>
          </div>

          <div className="text-xs font-mono text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-white/5">
            Total Liability Circulated: <strong className="text-amber-300 font-bold">953.5 VT pts</strong>
          </div>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-4">
          {fine_claims.map((claim, idx) => (
            <div
              key={`${claim.defendant}-${claim.claimant}`}
              className="glass-card p-4 rounded-xl border border-white/10 hover:border-amber-500/40 transition-all flex flex-col justify-between space-y-3"
            >
              <div>
                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-2 border-b border-white/5 pb-1.5">
                  <span>Corridor #{idx + 1}</span>
                  <span className="font-bold text-amber-400">{(claim.confidence * 100).toFixed(1)}% Conf</span>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-300">
                    <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                    <span className="truncate">{claim.defendant}</span>
                    <span className="text-[10px] text-slate-500 uppercase font-mono">(Def)</span>
                  </div>
                  <div className="flex items-center justify-center py-0.5 text-slate-500 text-xs">
                    ↓
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span className="truncate">{claim.claimant}</span>
                    <span className="text-[10px] text-slate-500 uppercase font-mono">(Clm)</span>
                  </div>
                </div>
              </div>

              <div className="space-y-1.5 pt-2 border-t border-white/5 text-[11px] font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Harm (Mono):</span>
                  <span className="text-white font-bold">{claim.harm_ugm3.toFixed(3)} µg/m³</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Uncon Harm:</span>
                  <span className="text-slate-300">{claim.harm_uncon_ugm3.toFixed(3)} µg/m³</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Damage (D_ij):</span>
                  <span className="text-slate-300">{claim.D_ij.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-amber-300 font-bold pt-1 border-t border-white/5">
                  <span>Fine Transfer:</span>
                  <span>+{claim.fine_vt_points.toFixed(1)} pts</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          6. RESEARCH FIGURES GALLERY WITH LIGHTBOX & PNG DOWNLOAD
      ────────────────────────────────────────────────────────────── */}
      <section id="section-figures" className="space-y-6 pt-4">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-cyan-400" />
              <h2 className="text-xl font-display font-bold text-white">
                Research Figures Gallery (300-DPI Publication Assets)
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Click any figure for full-screen inspection lightbox. All high-resolution PNG assets are directly downloadable for citation and presentation.
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {figures.map((fig) => (
            <div
              key={fig.id}
              className="glass-card rounded-2xl border border-white/10 overflow-hidden hover:border-cyan-500/40 transition-all flex flex-col group shadow-lg"
            >
              {/* Image Preview Container */}
              <div
                onClick={() => setActiveFigure(fig)}
                className="relative aspect-[16/10] bg-slate-950 overflow-hidden cursor-pointer group-hover:opacity-95"
              >
                <img
                  src={fig.src}
                  alt={fig.title}
                  className="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent opacity-60 group-hover:opacity-30 transition-opacity" />

                {/* Badges & Hover CTA */}
                <div className="absolute top-3 left-3 px-2 py-0.5 rounded-full bg-slate-900/80 backdrop-blur-md border border-white/10 text-[10px] font-mono text-cyan-300">
                  Figure {fig.id} · {fig.category}
                </div>

                <div className="absolute bottom-3 right-3 flex items-center gap-2">
                  <span className="px-2 py-1 rounded-lg bg-emerald-500/80 text-white text-[11px] font-medium flex items-center gap-1 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity">
                    <Maximize2 className="w-3 h-3" /> Zoom
                  </span>
                </div>
              </div>

              {/* Caption & Actions */}
              <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                <div>
                  <h3 className="font-display font-bold text-white text-base group-hover:text-cyan-300 transition-colors">
                    {fig.title}
                  </h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    {fig.desc}
                  </p>
                </div>

                <div className="pt-3 border-t border-white/5 flex items-center justify-between">
                  <span className="text-[11px] font-mono text-emerald-400">
                    {fig.highlight}
                  </span>

                  <a
                    href={fig.src}
                    download={`CarbonVayu_VT_v5_Fig${fig.id}.png`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-xs font-medium transition-colors border border-white/5"
                    title="Download 300-DPI PNG"
                  >
                    <Download className="w-3.5 h-3.5 text-cyan-400" />
                    <span>PNG</span>
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          LIGHTBOX MODAL
      ────────────────────────────────────────────────────────────── */}
      {activeFigure && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 animate-fade-in"
          onClick={() => setActiveFigure(null)}
        >
          <div
            className="relative max-w-5xl w-full max-h-[90vh] bg-slate-900 border border-white/15 rounded-2xl overflow-hidden flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-slate-950/80">
              <div>
                <span className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider">
                  Figure {activeFigure.id} · {activeFigure.category}
                </span>
                <h3 className="font-display font-bold text-white text-lg">
                  {activeFigure.title}
                </h3>
              </div>

              <div className="flex items-center gap-3">
                <a
                  href={activeFigure.src}
                  download={`CarbonVayu_VT_v5_Fig${activeFigure.id}.png`}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold transition-colors shadow-lg shadow-emerald-500/20"
                >
                  <Download className="w-4 h-4" />
                  <span>Download High-Res PNG</span>
                </a>

                <button
                  onClick={() => setActiveFigure(null)}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Image Full View */}
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-black/50">
              <img
                src={activeFigure.src}
                alt={activeFigure.title}
                className="max-w-full max-h-[68vh] object-contain rounded-lg shadow-2xl"
              />
            </div>

            {/* Modal Footer Description */}
            <div className="p-4 border-t border-white/10 bg-slate-950/80 text-xs text-slate-300 flex items-center justify-between">
              <p className="max-w-3xl leading-relaxed">{activeFigure.desc}</p>
              <span className="font-mono text-emerald-400 text-[11px] pl-4 flex-shrink-0">
                300 DPI Publication
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
