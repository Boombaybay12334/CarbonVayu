import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { supabase } from "../../lib/supabase";

const ARCHETYPE_COLORS = {
  F: "#1D9E75",
  I: "#D85A30",
  M: "#7F77DD",
};

const LINK_COLORS = {
  fine: "#E24B4A",
  transport: "#888780",
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function nodeRadius(node) {
  return clamp(6 + node.vt / 100, 6, 18);
}

function getLinkSourceId(link) {
  return typeof link.source === "object" ? link.source.id : link.source;
}

function getLinkTargetId(link) {
  return typeof link.target === "object" ? link.target.id : link.target;
}

function linkThickness(link) {
  return clamp(Math.log1p(Math.abs(link.impact ?? 0)) * 0.8, 0.5, 4);
}

function linkBaseOpacity(link) {
  return link.type === "transport" ? 0.5 : 0.9;
}

function linkColor(link) {
  return link.type === "fine" ? LINK_COLORS.fine : LINK_COLORS.transport;
}

function seedNodePositions(nodes, width, height) {
  if (!nodes.length) return;

  const radius = Math.max(80, Math.min(width, height) * 0.22);
  const centerX = width / 2;
  const centerY = height / 2;

  nodes.forEach((node, index) => {
    const theta = (2 * Math.PI * index) / nodes.length;
    node.x = centerX + Math.cos(theta) * radius;
    node.y = centerY + Math.sin(theta) * radius;
    node.vx = 0;
    node.vy = 0;
  });
}

export default function CarbonFlowMap() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);
  const dashTimerRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const svgSelectionRef = useRef(null);
  const zoomScaleRef = useRef(1);
  const linkTypeFilterRef = useRef("all");
  const archetypeFilterRef = useRef("all");
  const alwaysShowLabelsRef = useRef(false);
  const applyFiltersRef = useRef(() => {});
  const applyLabelVisibilityRef = useRef(() => {});
  const graphDataRef = useRef({
    nodes: [],
    links: [],
    nodeById: new Map(),
    adjacency: new Map(),
    nodeSelection: null,
    linkSelection: null,
    labelSelection: null,
  });

  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [hasData, setHasData] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [linkTypeFilter, setLinkTypeFilter] = useState("all");
  const [archetypeFilter, setArchetypeFilter] = useState("all");
  const [alwaysShowLabels, setAlwaysShowLabels] = useState(false);
  const [graphStats, setGraphStats] = useState({ states: 0, relations: 0, links: 0 });
  const [graphHeight, setGraphHeight] = useState(() => {
    if (typeof window === "undefined") return 640;
    return Math.max(560, Math.min(window.innerHeight - 180, 860));
  });

  useEffect(() => {
    let isUnmounted = false;

    const resolveGraphHeight = () => {
      const viewportHeight = window.innerHeight - 180;
      return Math.max(560, Math.min(viewportHeight, 860));
    };

    const getGraphDimensions = () => {
      const width = containerRef.current?.clientWidth || 900;
      const height = resolveGraphHeight();
      return { width, height };
    };

    const isNodeVisible = (node) => {
      return archetypeFilterRef.current === "all" || node.archetype === archetypeFilterRef.current;
    };

    const isLinkVisible = (link) => {
      const sourceId = getLinkSourceId(link);
      const targetId = getLinkTargetId(link);
      const sourceNode = graphDataRef.current.nodeById.get(sourceId);
      const targetNode = graphDataRef.current.nodeById.get(targetId);

      const matchesLinkType =
        linkTypeFilterRef.current === "all" || link.type === linkTypeFilterRef.current;
      const matchesArchetype =
        (!sourceNode || isNodeVisible(sourceNode)) && (!targetNode || isNodeVisible(targetNode));

      return matchesLinkType && matchesArchetype;
    };

    const buildSelectedNodeDetails = (node) => {
      const outgoingFineCount = graphDataRef.current.links.filter((link) => {
        return getLinkSourceId(link) === node.id && link.type === "fine";
      }).length;

      const incomingTransportCount = graphDataRef.current.links.filter((link) => {
        return getLinkTargetId(link) === node.id && link.type === "transport";
      }).length;

      return {
        id: node.id,
        name: node.name,
        vt: node.vt,
        archetype: node.archetype,
        rank: node.rank ?? "N/A",
        outgoingFineCount,
        incomingTransportCount,
      };
    };

    const initializeGraph = (nodes, links) => {
      const { width, height } = getGraphDimensions();
      setGraphHeight(height);
      seedNodePositions(nodes, width, height);

      const svg = d3
        .select(svgRef.current)
        .attr("width", "100%")
        .attr("height", height)
        .attr("viewBox", `0 0 ${width} ${height}`)
        .style("cursor", "grab");

      svgSelectionRef.current = svg;

      svg.selectAll("*").remove();

      svg.on("click", () => {
        setSelectedNode(null);
      });

      const defs = svg.append("defs");
      defs
        .append("marker")
        .attr("id", "carbon-flow-arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 16)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "#CBD5E1");

      const zoomLayer = svg.append("g").attr("class", "carbon-flow-zoom-layer");
      const linkLayer = zoomLayer.append("g").attr("class", "carbon-flow-links");
      const nodeLayer = zoomLayer.append("g").attr("class", "carbon-flow-nodes");
      const labelLayer = zoomLayer.append("g").attr("class", "carbon-flow-labels");

      const linkSelection = linkLayer
        .selectAll("line")
        .data(links)
        .join("line")
        .attr("stroke", (d) => linkColor(d))
        .attr("stroke-width", (d) => Math.max(d.type === "fine" ? 2 : 1, linkThickness(d)))
        .attr("stroke-dasharray", (d) => (d.type === "fine" ? "6 3" : null))
        .attr("marker-end", "url(#carbon-flow-arrow)");

      const nodeSelection = nodeLayer
        .selectAll("circle")
        .data(nodes)
        .join("circle")
        .attr("r", (d) => nodeRadius(d))
        .attr("fill", (d) => ARCHETYPE_COLORS[d.archetype] || "#64748b")
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 2)
        .style("cursor", "pointer");

      const labelSelection = labelLayer
        .selectAll("text")
        .data(nodes)
        .join("text")
        .text((d) => d.name)
        .attr("font-size", 10)
        .attr("fill", "#e2e8f0")
        .attr("text-anchor", "middle")
        .attr("pointer-events", "none")
        .attr("dy", (d) => nodeRadius(d) + 12)
        .attr("data-filter-visible", "1");

      const adjacency = new Map();
      links.forEach((link) => {
        const sourceId = getLinkSourceId(link);
        const targetId = getLinkTargetId(link);

        if (!adjacency.has(sourceId)) adjacency.set(sourceId, new Set());
        if (!adjacency.has(targetId)) adjacency.set(targetId, new Set());

        adjacency.get(sourceId).add(targetId);
        adjacency.get(targetId).add(sourceId);
      });

      const restoreOpacity = () => {
        applyFiltersRef.current();
      };

      nodeSelection
        .on("mouseover", (_event, hoveredNode) => {
          const connectedNodes = adjacency.get(hoveredNode.id) || new Set();

          nodeSelection.attr("opacity", (nodeDatum) => {
            if (!isNodeVisible(nodeDatum)) return 0;
            if (nodeDatum.id === hoveredNode.id || connectedNodes.has(nodeDatum.id)) return 1;
            return 0.15;
          });

          linkSelection.attr("opacity", (linkDatum) => {
            if (!isLinkVisible(linkDatum)) return 0;
            const sourceId = getLinkSourceId(linkDatum);
            const targetId = getLinkTargetId(linkDatum);
            if (sourceId === hoveredNode.id || targetId === hoveredNode.id) {
              return linkBaseOpacity(linkDatum);
            }
            return 0.15;
          });

          labelSelection.attr("opacity", (labelDatum) => {
            if (!isNodeVisible(labelDatum)) return 0;
            const labelsAllowed = alwaysShowLabelsRef.current || zoomScaleRef.current >= 1.2;
            if (!labelsAllowed) return 0;
            if (labelDatum.id === hoveredNode.id || connectedNodes.has(labelDatum.id)) return 1;
            return 0.15;
          });
        })
        .on("mouseout", restoreOpacity)
        .on("click", (event, nodeDatum) => {
          event.stopPropagation();
          setSelectedNode(buildSelectedNodeDetails(nodeDatum));
        });

      const dragBehavior = d3
        .drag()
        .on("start", (event, d) => {
          if (!event.active) {
            simulationRef.current?.alphaTarget(0.3).restart();
          }
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) {
            simulationRef.current?.alphaTarget(0);
          }
          d.fx = null;
          d.fy = null;
        });

      nodeSelection.call(dragBehavior);

      const renderScene = () => {
        linkSelection
          .attr("x1", (d) => d.source.x)
          .attr("y1", (d) => d.source.y)
          .attr("x2", (d) => d.target.x)
          .attr("y2", (d) => d.target.y);

        nodeSelection.attr("cx", (d) => d.x).attr("cy", (d) => d.y);

        labelSelection.attr("x", (d) => d.x).attr("y", (d) => d.y);
      };

      const simulation = d3
        .forceSimulation(nodes)
        .force("link", d3.forceLink(links).id((d) => d.id).distance(80).strength(0.3))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius((d) => nodeRadius(d) + 8))
        .on("tick", renderScene);

      // Force a first paint immediately so nodes are visible even before the first timer tick.
      renderScene();

      simulationRef.current = simulation;

      const zoomBehavior = d3
        .zoom()
        .scaleExtent([0.3, 4])
        .on("start", () => {
          svg.style("cursor", "grabbing");
        })
        .on("zoom", (event) => {
          zoomLayer.attr("transform", event.transform);
          zoomScaleRef.current = event.transform.k;
          applyLabelVisibilityRef.current();
        })
        .on("end", () => {
          svg.style("cursor", "grab");
        });

      zoomBehaviorRef.current = zoomBehavior;

      svg.call(zoomBehavior);
      svg.call(zoomBehavior.transform, d3.zoomIdentity);

      const pendingFineLinks = linkSelection.filter(
        (d) => d.type === "fine" && d.status === "fine_pending",
      );

      if (dashTimerRef.current) {
        dashTimerRef.current.stop();
      }

      dashTimerRef.current = d3.timer((elapsed) => {
        pendingFineLinks.attr("stroke-dashoffset", -elapsed / 35);
      });

      applyLabelVisibilityRef.current = () => {
        const labelsAllowed = alwaysShowLabelsRef.current || zoomScaleRef.current >= 1.2;

        labelSelection.attr("opacity", function () {
          const isVisibleByFilter = d3.select(this).attr("data-filter-visible") === "1";
          return labelsAllowed && isVisibleByFilter ? 1 : 0;
        });
      };

      applyFiltersRef.current = () => {
        nodeSelection
          .attr("display", (d) => (isNodeVisible(d) ? null : "none"))
          .attr("opacity", (d) => (isNodeVisible(d) ? 1 : 0));

        linkSelection
          .attr("display", (d) => (isLinkVisible(d) ? null : "none"))
          .attr("opacity", (d) => (isLinkVisible(d) ? linkBaseOpacity(d) : 0));

        labelSelection
          .attr("display", (d) => (isNodeVisible(d) ? null : "none"))
          .attr("data-filter-visible", (d) => (isNodeVisible(d) ? "1" : "0"));

        applyLabelVisibilityRef.current();
      };

      graphDataRef.current = {
        ...graphDataRef.current,
        nodes,
        links,
        nodeById: new Map(nodes.map((node) => [node.id, node])),
        adjacency,
        nodeSelection,
        linkSelection,
        labelSelection,
      };

      applyFiltersRef.current();
    };

    const loadData = async () => {
      setLoading(true);
      setFetchError(null);

      try {
        const [statesRes, relationsRes] = await Promise.all([
          supabase.from("states").select("id, name, vt_balance, archetype, rank"),
          supabase
            .from("carbon_relations")
            .select("id, source_state_id, target_state_id, relation_type, vt_impact, status, period"),
        ]);

        if (statesRes.error) throw statesRes.error;
        if (relationsRes.error) throw relationsRes.error;

        const states = statesRes.data || [];
        const relations = relationsRes.data || [];

        setGraphStats({ states: states.length, relations: relations.length, links: 0 });

        if (states.length === 0) {
          setHasData(false);
          return;
        }

        const nodes = states.map((s) => ({
          id: String(s.id),
          name: s.name,
          vt: Number(s.vt_balance ?? 0),
          archetype: s.archetype,
          rank: s.rank,
        }));

        const nodeIds = new Set(nodes.map((node) => String(node.id)));
        const links = relations
          .filter((r) => r.source_state_id !== r.target_state_id)
          .filter(
            (r) =>
              nodeIds.has(String(r.source_state_id)) && nodeIds.has(String(r.target_state_id)),
          )
          .map((r) => ({
            source: String(r.source_state_id),
            target: String(r.target_state_id),
            type: r.relation_type,
            impact: Number(r.vt_impact ?? 0),
            status: r.status,
            period: r.period,
          }));

        setGraphStats({ states: states.length, relations: relations.length, links: links.length });

        if (isUnmounted) return;

        setHasData(true);
        initializeGraph(nodes, links);
      } catch (error) {
        if (!isUnmounted) {
          setFetchError(error.message || "Failed to load carbon flow graph data.");
          setHasData(false);
        }
      } finally {
        if (!isUnmounted) {
          setLoading(false);
        }
      }
    };

    const handleResize = () => {
      if (!svgRef.current) return;

      const { width, height } = getGraphDimensions();
      setGraphHeight(height);

      const svg = d3.select(svgRef.current);
      svg.attr("height", height).attr("viewBox", `0 0 ${width} ${height}`);

      if (simulationRef.current) {
        simulationRef.current.force("center", d3.forceCenter(width / 2, height / 2));
        simulationRef.current.alpha(0.35).restart();

        requestAnimationFrame(() => {
          if (svgSelectionRef.current && zoomBehaviorRef.current) {
            svgSelectionRef.current.call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
          }
        });
      }
    };

    loadData();
    window.addEventListener("resize", handleResize);

    return () => {
      isUnmounted = true;
      window.removeEventListener("resize", handleResize);

      if (dashTimerRef.current) {
        dashTimerRef.current.stop();
      }

      if (simulationRef.current) {
        simulationRef.current.stop();
      }

      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
    };
  }, []);

  useEffect(() => {
    linkTypeFilterRef.current = linkTypeFilter;
    archetypeFilterRef.current = archetypeFilter;
    alwaysShowLabelsRef.current = alwaysShowLabels;
    applyFiltersRef.current();
  }, [linkTypeFilter, archetypeFilter, alwaysShowLabels]);

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-xs text-slate-300 flex items-center gap-2">
          <span>Link type</span>
          <select
            className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-slate-100"
            value={linkTypeFilter}
            onChange={(event) => setLinkTypeFilter(event.target.value)}
          >
            <option value="all">All</option>
            <option value="fine">Fine only</option>
            <option value="transport">Transport only</option>
          </select>
        </label>

        <label className="text-xs text-slate-300 flex items-center gap-2">
          <span>Archetype</span>
          <select
            className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-slate-100"
            value={archetypeFilter}
            onChange={(event) => setArchetypeFilter(event.target.value)}
          >
            <option value="all">All</option>
            <option value="F">F</option>
            <option value="I">I</option>
            <option value="M">M</option>
          </select>
        </label>

        <label className="text-xs text-slate-300 flex items-center gap-2">
          <input
            type="checkbox"
            checked={alwaysShowLabels}
            onChange={(event) => setAlwaysShowLabels(event.target.checked)}
          />
          <span>Always show labels</span>
        </label>
      </div>

      <div
        ref={containerRef}
        className="relative w-full overflow-hidden rounded-lg border border-slate-700/80 bg-slate-900/80"
        style={{ height: `${graphHeight}px` }}
      >
        {loading ? (
          <div className="absolute inset-0 grid place-items-center text-slate-300">Loading graph...</div>
        ) : null}

        {!loading && fetchError ? (
          <div className="absolute inset-0 grid place-items-center text-red-300 px-4 text-center">
            {fetchError}
          </div>
        ) : null}

        {!loading && !fetchError && !hasData ? (
          <div className="absolute inset-0 grid place-items-center text-slate-300 px-4 text-center">
            No state data found. Run the pipeline and upload first.
          </div>
        ) : null}

        {hasData ? <svg ref={svgRef} className="h-full w-full" /> : null}

        {!loading && hasData ? (
          <div className="absolute left-3 top-3 rounded-md bg-slate-900/90 border border-slate-700 px-3 py-2 text-[11px] text-slate-200 space-y-1 pointer-events-none">
            <div className="font-semibold text-slate-100">Legend</div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#1D9E75" }} />
              <span>Forest (F)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#D85A30" }} />
              <span>Industrial (I)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#7F77DD" }} />
              <span>Mixed (M)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-px w-6 border-t-2 border-dashed" style={{ borderColor: "#E24B4A" }} />
              <span>Fine claim</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-px w-6 border-t" style={{ borderColor: "#888780" }} />
              <span>Transport</span>
            </div>
          </div>
        ) : null}

        {!loading && hasData ? (
          <div className="absolute right-3 bottom-3 rounded-md bg-slate-900/80 border border-slate-700 px-2 py-1 text-[11px] text-slate-300 pointer-events-none">
            {`States ${graphStats.states} | Relations ${graphStats.relations} | Links ${graphStats.links}`}
          </div>
        ) : null}

        {!loading && hasData && selectedNode ? (
          <aside className="absolute right-3 top-3 w-60 rounded-md bg-slate-900/95 border border-slate-700 p-3 text-xs text-slate-200 space-y-2">
            <div className="text-sm font-semibold text-slate-100">{selectedNode.name}</div>
            <div className="flex justify-between">
              <span className="text-slate-400">VT balance</span>
              <span>{selectedNode.vt.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Archetype</span>
              <span>{selectedNode.archetype || "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Rank</span>
              <span>{selectedNode.rank ?? "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Outgoing fine</span>
              <span>{selectedNode.outgoingFineCount}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Incoming transport</span>
              <span>{selectedNode.incomingTransportCount}</span>
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
