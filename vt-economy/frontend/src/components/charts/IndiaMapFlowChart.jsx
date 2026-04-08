import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { supabase } from "../../lib/supabase";

// ─── Name normaliser: map DB names → GeoJSON property names ──────────────────
const STATE_NAME_MAP = {
  "Andaman and Nicobar Islands": "Andaman & Nicobar Island",
  "Andaman & Nicobar Islands": "Andaman & Nicobar Island",
  "Jammu and Kashmir": "Jammu & Kashmir",
  "Dadra and Nagar Haveli": "Dadra & Nagar Haveli",
  "Dadra and Nagar Haveli and Daman and Diu": "Daman & Diu",
  "Delhi": "NCT of Delhi",
  "Uttarakhand": "Uttarakhand",
  "Odisha": "Odisha",
};

function normalise(name) {
  return (STATE_NAME_MAP[name] ?? name).toLowerCase().replace(/[^a-z]/g, "");
}

// ─── Color scale for VT balance ───────────────────────────────────────────────
function vtColor(value, extent) {
  const [lo, hi] = extent;
  const t = hi === lo ? 0.5 : (value - lo) / (hi - lo);
  return d3.interpolateRdYlGn(t);
}

// ─── Bezier control point for arcs ───────────────────────────────────────────
function arcPath(sx, sy, tx, ty, sag = 0.25) {
  const mx = (sx + tx) / 2;
  const my = (sy + ty) / 2;
  const dx = tx - sx;
  const dy = ty - sy;
  const norm = Math.sqrt(dx * dx + dy * dy) || 1;
  const cx = mx - (dy / norm) * sag * norm;
  const cy = my + (dx / norm) * sag * norm;
  return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`;
}

function periodScore(period) {
  const text = String(period ?? "").trim();
  if (!text) return Number.NEGATIVE_INFINITY;

  const parsedDate = Date.parse(text);
  if (!Number.isNaN(parsedDate)) return parsedDate;

  const numeric = Number(text.replace(/[^\d.-]/g, ""));
  if (Number.isFinite(numeric)) return numeric;

  return Number.NEGATIVE_INFINITY;
}

function selectLatestRelations(relations) {
  const rows = Array.isArray(relations) ? relations : [];
  const withPeriod = rows.filter((r) => String(r.period ?? "").trim() !== "");

  if (!withPeriod.length) {
    return { latestPeriod: null, latestRows: rows };
  }

  let latestPeriod = withPeriod[0].period;
  for (const relation of withPeriod.slice(1)) {
    const candidatePeriod = relation.period;
    const candidateScore = periodScore(candidatePeriod);
    const latestScore = periodScore(latestPeriod);

    if (
      candidateScore > latestScore ||
      (candidateScore === latestScore &&
        String(candidatePeriod).localeCompare(String(latestPeriod)) > 0)
    ) {
      latestPeriod = candidatePeriod;
    }
  }

  return {
    latestPeriod: String(latestPeriod),
    latestRows: rows.filter(
      (relation) => String(relation.period ?? "").trim() === String(latestPeriod),
    ),
  };
}

const INDIA_GEOJSON_SOURCES = [
  "/india_state.geojson",
  "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson",
];

async function loadIndiaGeoJson() {
  for (const url of INDIA_GEOJSON_SOURCES) {
    try {
      const res = await fetch(url);
      if (res.ok) return await res.json();
    } catch {
      // Try the next source.
    }
  }
  throw new Error("Failed to load India map geometry from all sources.");
}

export default function IndiaMapFlowChart() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const refreshTimerRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, content: null });
  const [flowFilter, setFlowFilter] = useState("all"); // all | fine | transport
  const [latestPeriodLabel, setLatestPeriodLabel] = useState("current");
  const [refreshVersion, setRefreshVersion] = useState(0);

  // Keep animation frame ref for cleanup
  const animFrameRef = useRef(null);
  const arcSelRef = useRef(null);

  useEffect(() => {
    const queueRefresh = () => {
      if (refreshTimerRef.current) return;
      refreshTimerRef.current = setTimeout(() => {
        refreshTimerRef.current = null;
        setRefreshVersion((v) => v + 1);
      }, 250);
    };

    const channel = supabase
      .channel("india-map-flow-live")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "states" },
        queueRefresh,
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "carbon_relations" },
        queueRefresh,
      )
      .subscribe();

    const pollInterval = setInterval(() => {
      setRefreshVersion((v) => v + 1);
    }, 30000);

    return () => {
      clearInterval(pollInterval);
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      supabase.removeChannel(channel);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const draw = async () => {
      setLoading(true);
      setError(null);

      try {
        // ── 1. Fetch GeoJSON ──────────────────────────────────────────────────
        const indiaGeo = await loadIndiaGeoJson();

        // ── 2. Fetch state + relation data from supabase ──────────────────────
        const [sr, rr] = await Promise.all([
          supabase.from("states").select("id, name, vt_balance, archetype, rank"),
          supabase
            .from("carbon_relations")
            .select("id, source_state_id, target_state_id, relation_type, vt_impact, status, period"),
        ]);
        if (sr.error) throw sr.error;
        if (rr.error) throw rr.error;

        const states = sr.data || [];
        const relations = rr.data || [];

        const { latestPeriod, latestRows } = selectLatestRelations(relations);
        if (!cancelled) {
          setLatestPeriodLabel(latestPeriod || "current");
        }

        if (!states.length) {
          throw new Error("No state records found in Supabase.");
        }

        if (cancelled) return;

        // ── 3. Build lookup maps ──────────────────────────────────────────────
        const stateByNorm = new Map(states.map((s) => [normalise(s.name), s]));

        // ── 4. Match GeoJSON features to DB states ────────────────────────────
        const featureStateMap = new Map(); // feature.properties.NAME_1 → db state
        indiaGeo.features.forEach((f) => {
          const geoName = f.properties.NAME_1 || f.properties.ST_NM || "";
          const norm = normalise(geoName);
          const match = stateByNorm.get(norm);
          if (match) featureStateMap.set(geoName, match);
        });

        // ── 5. SVG setup ───────────────────────────────────────────────────────
        const container = containerRef.current;
        if (!container) return;
        const W = container.clientWidth || 800;
        const H = Math.max(560, Math.min(window.innerHeight - 200, 700));

        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove();
        svg
          .attr("width", W)
          .attr("height", H)
          .attr("viewBox", `0 0 ${W} ${H}`)
          .style("background", "transparent");

        // ── 6. Projection centred on India ─────────────────────────────────────
        const projection = d3
          .geoMercator()
          .fitExtent([[24, 24], [W - 24, H - 24]], indiaGeo);

        const path = d3.geoPath().projection(projection);

        // ── 7. VT colour scale ─────────────────────────────────────────────────
        const vtValues = states.map((s) => Number(s.vt_balance) || 0);
        const vtExtent = vtValues.length ? [Math.min(...vtValues), Math.max(...vtValues)] : [0, 0];

        // ── 8. Gradient defs ───────────────────────────────────────────────────
        const defs = svg.append("defs");

        // Glow filter
        const glow = defs.append("filter").attr("id", "india-map-glow").attr("x", "-30%").attr("y", "-30%").attr("width", "160%").attr("height", "160%");
        glow.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "blur");
        const feMerge = glow.append("feMerge");
        feMerge.append("feMergeNode").attr("in", "blur");
        feMerge.append("feMergeNode").attr("in", "SourceGraphic");

        // ── 9. Draw states ─────────────────────────────────────────────────────
        const mapGroup = svg.append("g").attr("class", "india-map-group");

        mapGroup
          .selectAll("path.state-shape")
          .data(indiaGeo.features)
          .join("path")
          .attr("class", "state-shape")
          .attr("d", path)
          .attr("fill", (f) => {
            const geoName = f.properties.NAME_1 || f.properties.ST_NM || "";
            const dbState = featureStateMap.get(geoName);
            if (!dbState) return "#1e293b";
            return vtColor(Number(dbState.vt_balance) || 0, vtExtent);
          })
          .attr("stroke", "#0f172a")
          .attr("stroke-width", 0.8)
          .attr("opacity", 0.88)
          .style("cursor", "pointer")
          .on("mousemove", (event, f) => {
            const geoName = f.properties.NAME_1 || f.properties.ST_NM || "";
            const dbState = featureStateMap.get(geoName);
            const rect = container.getBoundingClientRect();
            setTooltip({
              visible: true,
              x: event.clientX - rect.left + 12,
              y: event.clientY - rect.top - 12,
              content: dbState
                ? {
                    name: dbState.name,
                    vt: Number(dbState.vt_balance).toFixed(1),
                    archetype: dbState.archetype,
                    rank: dbState.rank,
                  }
                : { name: geoName, vt: "N/A", archetype: "Unknown", rank: "—" },
            });
          })
          .on("mouseleave", () => {
            setTooltip({ visible: false, x: 0, y: 0, content: null });
          });

        // State name labels (for large states)
        const labelThresholdArea = 4000;
        mapGroup
          .selectAll("text.state-label")
          .data(indiaGeo.features.filter((f) => {
            const b = path.bounds(f);
            const w = b[1][0] - b[0][0];
            const h = b[1][1] - b[0][1];
            return w * h > labelThresholdArea;
          }))
          .join("text")
          .attr("class", "state-label")
          .attr("transform", (f) => {
            const c = path.centroid(f);
            return `translate(${c[0]},${c[1]})`;
          })
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "middle")
          .attr("font-size", 8)
          .attr("font-family", "Inter, system-ui, sans-serif")
          .attr("fill", "#f1f5f9")
          .attr("opacity", 0.75)
          .attr("pointer-events", "none")
          .text((f) => {
            const name = f.properties.NAME_1 || f.properties.ST_NM || "";
            // Abbreviate long names
            if (name.length > 10) return name.split(" ").map((w) => w[0]).join("");
            return name;
          });

        // ── 10. Compute centroids for each DB state ─────────────────────────
        const stateCentroid = new Map(); // db state id → [px, py]
        indiaGeo.features.forEach((f) => {
          const geoName = f.properties.NAME_1 || f.properties.ST_NM || "";
          const dbState = featureStateMap.get(geoName);
          if (dbState) {
            const c = path.centroid(f);
            if (!isNaN(c[0])) stateCentroid.set(String(dbState.id), c);
          }
        });

        // ── 11. Build flow arcs ────────────────────────────────────────────────
        const filteredRelations = (latestRows || []).filter((r) => {
          if (flowFilter === "fine") return r.relation_type === "fine";
          if (flowFilter === "transport") return r.relation_type === "transport";
          return true;
        });

        const arcs = filteredRelations
          .filter((r) => r.source_state_id !== r.target_state_id)
          .map((r) => {
            const src = stateCentroid.get(String(r.source_state_id));
            const tgt = stateCentroid.get(String(r.target_state_id));
            if (!src || !tgt) return null;
            return { ...r, sx: src[0], sy: src[1], tx: tgt[0], ty: tgt[1] };
          })
          .filter(Boolean);

        // Draw arcs
        const arcGroup = svg.append("g").attr("class", "arc-group");

        const FINE_COLOR = "#f97316";   // vivid orange
        const TRANSPORT_COLOR = "#38bdf8"; // vivid cyan

        const arcSel = arcGroup
          .selectAll("path.carbon-arc")
          .data(arcs)
          .join("path")
          .attr("class", "carbon-arc")
          .attr("d", (d) => arcPath(d.sx, d.sy, d.tx, d.ty, 0.3))
          .attr("fill", "none")
          .attr("stroke", (d) => (d.relation_type === "fine" ? FINE_COLOR : TRANSPORT_COLOR))
          .attr("stroke-width", (d) => {
            const abs = Math.abs(Number(d.vt_impact) || 0);
            return Math.max(0.5, Math.min(3, Math.log1p(abs) * 0.5));
          })
          .attr("stroke-dasharray", (d) => (d.relation_type === "fine" ? "5 4" : "0"))
          .attr("opacity", 0.55)
          .attr("marker-end", "url(#india-map-arrow)");

        arcSelRef.current = arcSel;

        // Arrowhead marker
        defs
          .append("marker")
          .attr("id", "india-map-arrow")
          .attr("viewBox", "0 -4 8 8")
          .attr("refX", 8)
          .attr("refY", 0)
          .attr("markerWidth", 5)
          .attr("markerHeight", 5)
          .attr("orient", "auto")
          .append("path")
          .attr("d", "M0,-4L8,0L0,4")
          .attr("fill", "#94a3b8");

        // ── 12. Animated dashes ───────────────────────────────────────────────
        let offset = 0;
        const animate = () => {
          offset -= 0.35;
          if (arcSelRef.current) {
            arcSelRef.current
              .filter((d) => d.relation_type === "fine")
              .attr("stroke-dashoffset", offset);
          }
          animFrameRef.current = requestAnimationFrame(animate);
        };
        animFrameRef.current = requestAnimationFrame(animate);

        // ── 13. Color legend ───────────────────────────────────────────────────
        const legendW = 140;
        const legendH = 12;
        const legendX = W - legendW - 16;
        const legendY = H - 50;

        const legendGroup = svg.append("g").attr("transform", `translate(${legendX},${legendY})`);

        const gradId = "vt-legend-grad";
        const linearGrad = defs
          .append("linearGradient")
          .attr("id", gradId)
          .attr("x1", "0%").attr("x2", "100%");

        for (let i = 0; i <= 10; i++) {
          linearGrad
            .append("stop")
            .attr("offset", `${i * 10}%`)
            .attr("stop-color", d3.interpolateRdYlGn(i / 10));
        }

        legendGroup
          .append("rect")
          .attr("width", legendW)
          .attr("height", legendH)
          .attr("rx", 3)
          .attr("fill", `url(#${gradId})`)
          .attr("stroke", "#334155")
          .attr("stroke-width", 0.5);

        legendGroup
          .append("text")
          .attr("x", 0).attr("y", -5)
          .attr("font-size", 9)
          .attr("fill", "#94a3b8")
          .attr("font-family", "Inter, sans-serif")
          .text(`Low VT (${vtExtent[0].toFixed(0)})`);

        legendGroup
          .append("text")
          .attr("x", legendW).attr("y", -5)
          .attr("font-size", 9)
          .attr("fill", "#94a3b8")
          .attr("font-family", "Inter, sans-serif")
          .attr("text-anchor", "end")
          .text(`High VT (${vtExtent[1].toFixed(0)})`);

      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to render map.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    draw();

    return () => {
      cancelled = true;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      arcSelRef.current = null;
    };
  }, [flowFilter, refreshVersion]);

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700 relative">
      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <label className="text-xs text-slate-300 flex items-center gap-2">
          <span>Flow type</span>
          <select
            className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-slate-100 text-xs"
            value={flowFilter}
            onChange={(e) => setFlowFilter(e.target.value)}
          >
            <option value="all">All flows</option>
            <option value="fine">Fine claims</option>
            <option value="transport">Transport</option>
          </select>
        </label>

        {/* Arc legend */}
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-6 h-px border-t-2 border-dashed" style={{ borderColor: "#f97316" }} />
            Fine claim
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-6 h-px border-t" style={{ borderColor: "#38bdf8" }} />
            Transport
          </span>
          <span className="ml-2 text-slate-500">(state fill = VT balance)</span>
        </div>

        <div className="ml-auto text-[11px] text-emerald-300/90">
          Live from DB | latest period: {latestPeriodLabel}
        </div>
      </div>

      {/* Map container */}
      <div
        ref={containerRef}
        className="relative w-full rounded-lg overflow-hidden border border-slate-700/80 bg-slate-900/80"
        style={{ height: "640px" }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
            <span className="animate-pulse">Loading India map…</span>
          </div>
        )}
        {!loading && error && (
          <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm px-6 text-center">
            {error}
          </div>
        )}

        <svg ref={svgRef} className="w-full h-full" />

        {/* Tooltip */}
        {tooltip.visible && tooltip.content && (
          <div
            className="absolute z-20 pointer-events-none rounded-lg border border-slate-600 bg-slate-900/95 px-3 py-2 text-xs text-slate-200 shadow-xl backdrop-blur-sm"
            style={{ left: tooltip.x, top: tooltip.y, minWidth: 160 }}
          >
            <div className="text-sm font-semibold text-white mb-1">{tooltip.content.name}</div>
            <div className="flex justify-between gap-4">
              <span className="text-slate-400">VT Balance</span>
              <span className="font-mono font-medium text-emerald-400">{tooltip.content.vt}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-slate-400">Archetype</span>
              <span>{tooltip.content.archetype || "—"}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-slate-400">Rank</span>
              <span>{tooltip.content.rank ?? "—"}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
