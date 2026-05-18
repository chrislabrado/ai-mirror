/**
 * KnowledgeGraph page — force-directed, interactive, filterable KG explorer.
 *
 * Layout engine: d3-force (client-side simulation, frozen after convergence).
 * Interactivity: click-to-focus (dim non-neighbours), side-panel entity detail,
 *   text search highlight, kind filter chips, salience slider, edge-weight toggle.
 */
import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import {
  Loader2,
  Network,
  RotateCcw,
  SlidersHorizontal,
  X,
  ArrowLeftRight,
} from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "@/lib/api";
import type { KGGraph, KGNode } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EntityDetailPanel } from "@/components/EntityDetailPanel";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Colour + visual encoding helpers
// ---------------------------------------------------------------------------
const KIND_COLOURS: Record<string, string> = {
  concept: "#14f1d9",
  person:  "#00e5ff",
  tool:    "#7ad3ff",
  project: "#9ef7d3",
  belief:  "#ffb547",
  trait:   "#ffd9a5",
  source:  "#c4b5fd",
  topic:   "#86efac",
};
const FALLBACK_COLOUR = "#7f9bb3";

function kindColour(kind: string): string {
  return KIND_COLOURS[kind.toLowerCase()] ?? FALLBACK_COLOUR;
}

function hexToRgb(hex: string): string {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return "20,241,217";
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `${r},${g},${b}`;
}

/** Salience 0→1 maps node width 120→200 px. */
function salienceToWidth(salience: number): number {
  return 120 + salience * 80;
}

/** Weight 0→1 maps stroke-width 1.4→4.5 — bumped so edges are visibly thick. */
function weightToStroke(weight: number): number {
  return 1.4 + weight * 3.1;
}

// ---------------------------------------------------------------------------
// KG node data type
// ---------------------------------------------------------------------------
type KGNodeData = {
  label: string;
  kind: string;
  salience: number;
  dimmed: boolean;
  highlighted: boolean; // text-search match — pulsing border
};

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------
function KGNodeComponent({ data, selected }: NodeProps) {
  const { label, kind, salience, dimmed, highlighted } = data as KGNodeData;
  const colour = kindColour(kind);
  const glowAlpha = 0.12 + salience * 0.55;
  const borderAlpha = dimmed ? 0.08 : selected ? 0.95 : 0.4 + salience * 0.55;
  const nodeWidth = salienceToWidth(salience);

  return (
    <div
      style={{
        width: nodeWidth,
        opacity: dimmed ? 0.15 : 1,
        transition: "opacity 220ms ease",
        borderColor: highlighted
          ? `rgba(0,255,200,${borderAlpha})`
          : `rgba(${hexToRgb(colour)}, ${borderAlpha})`,
        boxShadow: highlighted
          ? `0 0 0 2px rgba(0,255,200,0.8), 0 0 24px rgba(0,255,200,0.55)`
          : selected
          ? `0 0 0 2px rgba(${hexToRgb(colour)},0.8), 0 0 28px rgba(${hexToRgb(colour)},0.5)`
          : `0 0 18px rgba(${hexToRgb(colour)}, ${glowAlpha})`,
        animation: highlighted ? "pulseGlow 1.5s ease-in-out infinite" : undefined,
      }}
      className="rounded-md border bg-hud-panel/85 px-3 py-2"
    >
      <div
        style={{ color: colour }}
        className="font-mono text-[9px] uppercase tracking-[0.25em] opacity-70"
      >
        {kind}
      </div>
      <div className="font-display text-[12px] uppercase tracking-[0.12em] text-hud-text leading-tight">
        {label}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// d3-force layout
// ---------------------------------------------------------------------------
interface D3Node extends SimulationNodeDatum {
  id: string;
  x: number;
  y: number;
}

interface D3Link extends SimulationLinkDatum<D3Node> {
  source: string | D3Node;
  target: string | D3Node;
}

/**
 * Force-directed layout tuned for "clustered but legible" at 30-500 nodes.
 *
 * Key design choices:
 * - Link force kept STRONG and SHORT so connected nodes hug each other into
 *   visible communities (the previous distance=180 + strength=0.4 produced
 *   evenly-spaced, structureless drift).
 * - Charge force is moderate so disconnected nodes don't shoot to the rim.
 * - Iterations bumped to 400 so the simulation actually converges instead
 *   of freezing mid-anneal.
 */
function runForceLayout(
  nodes: KGNode[],
  edges: { source_id: number; target_id: number; weight?: number }[],
  iterations = 400,
): Map<number, { x: number; y: number }> {
  // Seed with a deterministic ring so the same input always produces a
  // similar layout (random init causes the same graph to look different on
  // each refresh, which the user reads as "disorganised").
  const ringRadius = Math.max(220, nodes.length * 6);
  const simNodes: D3Node[] = nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    return {
      id: String(n.id),
      x: ringRadius * Math.cos(angle),
      y: ringRadius * Math.sin(angle),
    };
  });

  const simLinks: D3Link[] = edges.map((e) => ({
    source: String(e.source_id),
    target: String(e.target_id),
  }));

  const simulation = forceSimulation<D3Node>(simNodes)
    .force(
      "link",
      forceLink<D3Node, D3Link>(simLinks)
        .id((d) => d.id)
        .distance(140)
        .strength(0.9), // strong pull — connected nodes form visible clusters
    )
    .force("charge", forceManyBody<D3Node>().strength(-220)) // moderate repulsion
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide<D3Node>(70))
    .alphaDecay(0.01) // slower cool-down — gives clusters time to settle
    .stop();

  for (let i = 0; i < iterations; i++) {
    simulation.tick();
  }

  const positions = new Map<number, { x: number; y: number }>();
  for (const n of simNodes) {
    const orig = nodes.find((kn) => String(kn.id) === n.id);
    if (orig) {
      positions.set(orig.id, { x: n.x ?? 0, y: n.y ?? 0 });
    }
  }
  return positions;
}

// ---------------------------------------------------------------------------
// Build React Flow nodes + edges from graph data + filter state
// ---------------------------------------------------------------------------
function buildFlowElements(
  graph: KGGraph,
  positions: Map<number, { x: number; y: number }>,
  opts: {
    focusedId: number | null;
    neighbourIds: Set<number>;
    searchQuery: string;
    activeKinds: Set<string>;
    salienceMin: number;
    showLowWeightEdges: boolean;
    showIsolated: boolean;
  },
): { nodes: Node[]; edges: Edge[] } {
  const { focusedId, neighbourIds, searchQuery, activeKinds, salienceMin, showLowWeightEdges, showIsolated } = opts;
  const q = searchQuery.trim().toLowerCase();
  const hasFocus = focusedId !== null;

  // Pre-compute connected node ids so we can hide orphans by default.
  // LLM extraction often emits more entities than relationships, leaving
  // a long tail of unconnected nodes that drift around with nothing
  // pulling them and make the graph look noisy.
  const connectedIds = new Set<number>();
  for (const e of graph.edges) {
    if (!showLowWeightEdges && e.weight < 0.5) continue;
    connectedIds.add(e.source_id);
    connectedIds.add(e.target_id);
  }

  const visibleNodeIds = new Set<number>();

  const nodes: Node[] = graph.nodes
    .filter((n) => {
      if (activeKinds.size > 0 && !activeKinds.has(n.kind)) return false;
      if (n.salience < salienceMin) return false;
      if (!showIsolated && !connectedIds.has(n.id)) return false;
      return true;
    })
    .map((n) => {
      visibleNodeIds.add(n.id);
      const pos = positions.get(n.id) ?? { x: 0, y: 0 };
      const isSelected = n.id === focusedId;
      const isNeighbour = hasFocus && neighbourIds.has(n.id);
      const dimmed = hasFocus && !isSelected && !isNeighbour;
      const highlighted = q.length >= 2 && n.label.toLowerCase().includes(q);

      return {
        id: String(n.id),
        type: "kg",
        position: pos,
        selected: isSelected,
        data: {
          label: n.label,
          kind: n.kind,
          salience: n.salience,
          dimmed,
          highlighted,
        } satisfies KGNodeData,
      };
    });

  const EDGE_LABEL_STYLE: CSSProperties = {
    fill: "#14f1d9",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  };
  const EDGE_LABEL_BG: CSSProperties = {
    fill: "rgba(3,7,15,0.92)",
  };

  const edges: Edge[] = graph.edges
    .filter((e) => {
      if (!visibleNodeIds.has(e.source_id) || !visibleNodeIds.has(e.target_id)) return false;
      if (!showLowWeightEdges && e.weight < 0.5) return false;
      return true;
    })
    .map((e) => {
      const sourceId = e.source_id;
      const targetId = e.target_id;
      const isAdjacentToFocus =
        hasFocus && (sourceId === focusedId || targetId === focusedId);
      const dimEdge = hasFocus && !isAdjacentToFocus;
      // Bumped base opacity floor so weak edges remain legible — the previous
      // 0.25+w*0.5 scheme rendered low-weight edges nearly invisible against
      // the deep-navy background.
      const stroke = dimEdge
        ? "rgba(20,241,217,0.08)"
        : `rgba(20,241,217,${0.55 + e.weight * 0.45})`;

      return {
        id: `e-${e.id}`,
        source: String(e.source_id),
        target: String(e.target_id),
        label: e.predicate.replace(/_/g, " "),
        animated: e.weight >= 0.75 && !dimEdge,
        style: {
          stroke,
          strokeWidth: weightToStroke(e.weight),
          opacity: dimEdge ? 0.15 : 1,
          transition: "opacity 220ms ease, stroke 220ms ease",
        },
        labelStyle: dimEdge ? { ...EDGE_LABEL_STYLE, opacity: 0.15 } : EDGE_LABEL_STYLE,
        labelBgStyle: EDGE_LABEL_BG,
        type: "default",
      };
    });

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Limit options
// ---------------------------------------------------------------------------
const LIMIT_OPTIONS = [50, 100, 200, 400] as const;
type LimitOption = (typeof LIMIT_OPTIONS)[number];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------
const NODE_TYPES = { kg: KGNodeComponent };

export function KnowledgeGraphPage() {
  // ── Graph data state ──────────────────────────────────────────────────────
  const [rawGraph, setRawGraph] = useState<KGGraph>({ nodes: [], edges: [] });
  const [positions, setPositions] = useState<Map<number, { x: number; y: number }>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [limit, setLimit] = useState<LimitOption>(200);

  // ── Filter state ──────────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [activeKinds, setActiveKinds] = useState<Set<string>>(new Set());
  const [salienceMin, setSalienceMin] = useState(0);
  const [showLowWeightEdges, setShowLowWeightEdges] = useState(false);
  // Hide unconnected entities by default — the LLM often extracts more
  // entities than relationships, leaving orphans that float in the
  // canvas and obscure the cluster structure.
  const [showIsolated, setShowIsolated] = useState(false);

  // ── Interaction state ─────────────────────────────────────────────────────
  const [focusedEntityId, setFocusedEntityId] = useState<number | null>(null);
  const [selectedPanelId, setSelectedPanelId] = useState<number | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // ── React Flow state ──────────────────────────────────────────────────────
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const rfInstanceRef = useRef<ReactFlowInstance | null>(null);
  const onInit = useCallback((instance: ReactFlowInstance) => {
    rfInstanceRef.current = instance;
  }, []);
  const pendingFitRef = useRef(false);

  // ── Derived neighbour set for focus-mode ──────────────────────────────────
  const neighbourIds = useMemo<Set<number>>(() => {
    if (focusedEntityId === null) return new Set();
    const ids = new Set<number>();
    for (const e of rawGraph.edges) {
      if (e.source_id === focusedEntityId) ids.add(e.target_id);
      if (e.target_id === focusedEntityId) ids.add(e.source_id);
    }
    return ids;
  }, [focusedEntityId, rawGraph.edges]);

  // ── All distinct kinds in graph ───────────────────────────────────────────
  const allKinds = useMemo<string[]>(() => {
    return Array.from(new Set(rawGraph.nodes.map((n) => n.kind))).sort();
  }, [rawGraph.nodes]);

  // ── Re-build flow elements whenever filters/focus/data change ────────────
  useEffect(() => {
    const { nodes: nextNodes, edges: nextEdges } = buildFlowElements(rawGraph, positions, {
      focusedId: focusedEntityId,
      neighbourIds,
      searchQuery,
      activeKinds,
      salienceMin,
      showLowWeightEdges,
      showIsolated,
    });
    setNodes(nextNodes);
    setEdges(nextEdges);
  }, [
    rawGraph,
    positions,
    focusedEntityId,
    neighbourIds,
    searchQuery,
    activeKinds,
    salienceMin,
    showLowWeightEdges,
    showIsolated,
    setNodes,
    setEdges,
  ]);

  // ── Fit view after data fetch ─────────────────────────────────────────────
  useEffect(() => {
    if (!pendingFitRef.current) return;
    const id = requestAnimationFrame(() => {
      rfInstanceRef.current?.fitView({ padding: 0.15 });
      pendingFitRef.current = false;
    });
    return () => cancelAnimationFrame(id);
  }, [nodes]);

  // ── Fetch graph data ──────────────────────────────────────────────────────
  const fetchGraph = useCallback(
    async (focusValue: string, limitValue: number) => {
      setLoading(true);
      setError(null);
      try {
        const graph: KGGraph = await api.exploreGraph({
          focus: focusValue.trim() || undefined,
          limit: limitValue,
        });
        // Run force layout (synchronous, frozen after convergence)
        const pos = runForceLayout(graph.nodes, graph.edges, 250);
        setRawGraph(graph);
        setPositions(pos);
        pendingFitRef.current = true;
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Graph fetch failed.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // Initial load
  useEffect(() => {
    void fetchGraph("", 200);
  }, [fetchGraph]);

  // ── ESC → clear focus ────────────────────────────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setFocusedEntityId(null);
        setSelectedPanelId(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // ── Node click → focus + panel ───────────────────────────────────────────
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const id = parseInt(node.id, 10);
      if (focusedEntityId === id) {
        // Second click → deselect
        setFocusedEntityId(null);
        setSelectedPanelId(null);
      } else {
        setFocusedEntityId(id);
        setSelectedPanelId(id);
      }
    },
    [focusedEntityId],
  );

  // Click on background pane → clear focus
  const handlePaneClick = useCallback(() => {
    setFocusedEntityId(null);
    setSelectedPanelId(null);
  }, []);

  // ── Kind chip toggle ──────────────────────────────────────────────────────
  function toggleKind(kind: string) {
    setActiveKinds((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) {
        next.delete(kind);
      } else {
        next.add(kind);
      }
      return next;
    });
  }

  function resetFilters() {
    setSearchQuery("");
    setActiveKinds(new Set());
    setSalienceMin(0);
    setShowLowWeightEdges(false);
    setShowIsolated(false);
    setFocusedEntityId(null);
    setSelectedPanelId(null);
  }

  const isEmpty = rawGraph.nodes.length === 0 && !loading;
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    activeKinds.size > 0 ||
    salienceMin > 0 ||
    showLowWeightEdges ||
    showIsolated;

  return (
    <>
      {/* Main content — shifts left when panel is open */}
      <div
        className={cn(
          "space-y-6 transition-all duration-300",
          selectedPanelId !== null ? "mr-[380px]" : "",
        )}
      >
        {/* ── Heading ──────────────────────────────────────────────────────── */}
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Section 6.4 · Knowledge Graph Explorer
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Knowledge Graph
          </h1>
        </div>

        {/* ── Error banner ─────────────────────────────────────────────────── */}
        {error && (
          <Card className="border-hud-warn/40">
            <CardContent className="py-4 text-sm text-hud-warn">{error}</CardContent>
          </Card>
        )}

        {/* ── Engage bar ───────────────────────────────────────────────────── */}
        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <Network className="h-4 w-4 text-hud-glow" />
            <CardTitle>Graph Controls</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="text"
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void fetchGraph(focus, limit);
                }}
                placeholder="Focus on a concept, person, project…"
                className="min-w-[240px] flex-1 rounded-md border border-hud-line bg-hud-panel/40 px-4 py-2.5 font-mono text-[12px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow focus:outline-none"
              />
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value) as LimitOption)}
                className="rounded-md border border-hud-line bg-hud-panel/40 px-3 py-2.5 font-mono text-[12px] text-hud-text focus:border-hud-glow focus:outline-none"
              >
                {LIMIT_OPTIONS.map((l) => (
                  <option key={l} value={l}>
                    Limit {l}
                  </option>
                ))}
              </select>
              <button
                onClick={() => void fetchGraph(focus, limit)}
                disabled={loading}
                className="neon-btn flex items-center gap-2 rounded-md px-5 py-2.5 font-display text-[12px] uppercase tracking-[0.22em] disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Network className="h-3.5 w-3.5" />
                )}
                Engage
              </button>
              <button
                onClick={() => rfInstanceRef.current?.fitView({ padding: 0.15 })}
                className="neon-btn flex items-center gap-2 rounded-md px-4 py-2.5 font-display text-[12px] uppercase tracking-[0.22em]"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Re-fit
              </button>
              <button
                onClick={() => setFiltersOpen((v) => !v)}
                className={cn(
                  "neon-btn flex items-center gap-2 rounded-md px-4 py-2.5 font-display text-[12px] uppercase tracking-[0.22em]",
                  hasActiveFilters && "border-hud-glow/70 text-hud-glow",
                )}
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Filters
                {hasActiveFilters && (
                  <span className="ml-1 rounded-full bg-hud-glow/20 px-1.5 py-0.5 font-mono text-[9px] text-hud-glow">
                    ON
                  </span>
                )}
              </button>
            </div>

            {/* ── Filter panel (collapsible) ──────────────────────────────── */}
            {filtersOpen && (
              <div className="mt-4 space-y-4 rounded-md border border-hud-line bg-hud-panel/30 px-4 py-4">
                {/* Text search */}
                <div className="space-y-1.5">
                  <label className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                    Highlight search
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Type to highlight matching nodes…"
                      className="w-full rounded-md border border-hud-line bg-hud-panel/40 px-4 py-2 font-mono text-[12px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow focus:outline-none"
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-hud-textFaint hover:text-hud-text"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Kind chips */}
                {allKinds.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                      Entity kind — active chips are visible
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {allKinds.map((kind) => {
                        const colour = kindColour(kind);
                        const isActive = activeKinds.size === 0 || activeKinds.has(kind);
                        return (
                          <button
                            key={kind}
                            type="button"
                            onClick={() => toggleKind(kind)}
                            className={cn(
                              "flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] transition-all",
                              isActive
                                ? "bg-hud-panelHi"
                                : "opacity-35 hover:opacity-60",
                            )}
                            style={{
                              borderColor: isActive ? `${colour}66` : "rgba(20,241,217,0.15)",
                              color: isActive ? colour : "#7f9bb3",
                            }}
                          >
                            <span
                              className="h-1.5 w-1.5 rounded-full"
                              style={{ background: isActive ? colour : "#7f9bb3" }}
                            />
                            {kind}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Salience slider */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                      Min salience
                    </label>
                    <span className="font-mono text-[10px] text-hud-textDim">
                      {Math.round(salienceMin * 100)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={salienceMin}
                    onChange={(e) => setSalienceMin(parseFloat(e.target.value))}
                    className="w-full accent-hud-glow"
                  />
                </div>

                {/* Low-weight edge toggle */}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textDim">
                    Show low-weight edges (weight &lt; 0.5)
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowLowWeightEdges((v) => !v)}
                    className={cn(
                      "relative h-5 w-10 rounded-full border transition-colors",
                      showLowWeightEdges
                        ? "border-hud-glow/60 bg-hud-glow/20"
                        : "border-hud-line bg-hud-panel/40",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 h-4 w-4 rounded-full transition-transform",
                        showLowWeightEdges
                          ? "translate-x-5 bg-hud-glow"
                          : "translate-x-0.5 bg-hud-textFaint",
                      )}
                    />
                  </button>
                </div>

                {/* Show isolated entities toggle */}
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textDim">
                    Show unconnected entities
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowIsolated((v) => !v)}
                    className={cn(
                      "relative h-5 w-10 rounded-full border transition-colors",
                      showIsolated
                        ? "border-hud-glow/60 bg-hud-glow/20"
                        : "border-hud-line bg-hud-panel/40",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 h-4 w-4 rounded-full transition-transform",
                        showIsolated
                          ? "translate-x-5 bg-hud-glow"
                          : "translate-x-0.5 bg-hud-textFaint",
                      )}
                    />
                  </button>
                </div>

                {/* Reset */}
                {hasActiveFilters && (
                  <div className="border-t border-hud-line pt-3">
                    <button
                      type="button"
                      onClick={resetFilters}
                      className="font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textFaint underline decoration-hud-textFaint/40 hover:text-hud-textDim transition-colors"
                    >
                      Reset all filters
                    </button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Graph canvas ─────────────────────────────────────────────────── */}
        <Card className="overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-hud-glow" />
              <CardTitle>Entity Relationship Canvas</CardTitle>
            </div>
            {focusedEntityId !== null && (
              <div className="flex items-center gap-2">
                <ArrowLeftRight className="h-3 w-3 text-hud-textFaint" />
                <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-hud-textFaint">
                  Focus mode — ESC to clear
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setFocusedEntityId(null);
                    setSelectedPanelId(null);
                  }}
                  className="ml-1 rounded p-0.5 text-hud-textFaint hover:text-hud-text"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <div
              className={cn(
                "relative bg-hud-void transition-opacity duration-300",
                loading ? "opacity-60" : "opacity-100",
              )}
              style={{ height: 700, width: "100%" }}
            >
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={NODE_TYPES}
                onInit={onInit}
                onNodeClick={handleNodeClick}
                onPaneClick={handlePaneClick}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                minZoom={0.08}
                maxZoom={4}
                attributionPosition="bottom-right"
                nodesDraggable
                selectNodesOnDrag={false}
              >
                <Background
                  variant={BackgroundVariant.Dots}
                  color="rgba(20,241,217,0.15)"
                  gap={28}
                  size={1}
                />
                <Controls
                  style={{
                    background: "rgba(10,18,36,0.85)",
                    border: "1px solid rgba(20,241,217,0.22)",
                    color: "#dff5ff",
                  }}
                  className="[&_button]:border-hud-line [&_button]:bg-hud-panel [&_button]:text-hud-text [&_button:hover]:border-hud-glow/60 [&_button:hover]:bg-hud-panelHi"
                />
                <MiniMap
                  nodeColor={(node) => {
                    const kind = (node.data as KGNodeData | undefined)?.kind ?? "";
                    return kindColour(kind);
                  }}
                  maskColor="rgba(3,7,15,0.72)"
                  style={{
                    background: "rgba(10,18,36,0.85)",
                    border: "1px solid rgba(20,241,217,0.22)",
                  }}
                />
              </ReactFlow>

              {/* Empty state overlay */}
              {isEmpty && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                  <p className="max-w-sm text-center font-mono text-[12px] uppercase leading-relaxed tracking-[0.1em] text-hud-textFaint">
                    Knowledge graph is empty. Ingest conversations and run a Mirror analysis to
                    populate entities.
                  </p>
                  <Link
                    to="/"
                    className="neon-btn flex items-center gap-2 rounded-md px-5 py-2.5 font-display text-[12px] uppercase tracking-[0.22em]"
                  >
                    <Network className="h-3.5 w-3.5" />
                    Go to Dashboard
                  </Link>
                </div>
              )}

              {/* Loading badge */}
              {loading && (
                <div className="pointer-events-none absolute left-1/2 top-4 flex -translate-x-1/2 items-center gap-2 rounded-md border border-hud-glow/30 bg-hud-panel/90 px-4 py-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-hud-glow" />
                  <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-glow">
                    Computing layout…
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── Legend ───────────────────────────────────────────────────────── */}
        {allKinds.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Entity Types</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                {allKinds.map((kind) => (
                  <div key={kind} className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{
                        background: kindColour(kind),
                        boxShadow: `0 0 6px ${kindColour(kind)}`,
                      }}
                    />
                    <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-hud-textDim">
                      {kind}
                    </span>
                    <span className="font-mono text-[10px] text-hud-textFaint">
                      ×{rawGraph.nodes.filter((n) => n.kind === kind).length}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textFaint">
                Click a node to open entity detail and enter focus mode. ESC to clear. Drag nodes to reposition.
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* ── Entity detail side panel ─────────────────────────────────────── */}
      <EntityDetailPanel
        entityId={selectedPanelId}
        onClose={() => {
          setSelectedPanelId(null);
          setFocusedEntityId(null);
        }}
        onSelectEntity={(id) => {
          setSelectedPanelId(id);
          setFocusedEntityId(id);
        }}
      />
    </>
  );
}
