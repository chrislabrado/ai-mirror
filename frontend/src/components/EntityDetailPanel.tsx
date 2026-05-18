import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  BookOpen,
  MessageSquare,
  X,
  Loader2,
  AlertTriangle,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { EntityDetail, NeighbourEdge } from "@/types/api";

// ---------------------------------------------------------------------------
// Kind → colour mapping — shared with KnowledgeGraph
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

// ---------------------------------------------------------------------------
// Salience bar — narrow horizontal indicator
// ---------------------------------------------------------------------------
function SalienceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-hud-textFaint">
          Salience
        </span>
        <span className="font-mono text-[10px] text-hud-textDim">{pct}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-hud-line">
        <div
          className="h-1 rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, rgba(0,255,200,0.7), rgba(0,229,255,0.9))`,
            boxShadow: "0 0 6px rgba(0,255,200,0.5)",
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Neighbour row
// ---------------------------------------------------------------------------
function NeighbourRow({
  edge,
  direction,
  onSelectEntity,
}: {
  edge: NeighbourEdge;
  direction: "in" | "out";
  onSelectEntity: (id: number) => void;
}) {
  const colour = kindColour(edge.kind);
  return (
    <button
      type="button"
      onClick={() => onSelectEntity(edge.entity_id)}
      className="group flex w-full items-center gap-3 rounded-md border border-hud-line bg-hud-panel/40 px-3 py-2.5 text-left transition-colors hover:border-hud-glow/40 hover:bg-hud-panelHi"
    >
      {direction === "in" ? (
        <ArrowLeft className="h-3 w-3 shrink-0 text-hud-textFaint group-hover:text-hud-glow2" />
      ) : (
        <ArrowRight className="h-3 w-3 shrink-0 text-hud-textFaint group-hover:text-hud-glow2" />
      )}
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex items-center gap-2">
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: colour, boxShadow: `0 0 4px ${colour}` }}
          />
          <span className="truncate font-display text-[11px] uppercase tracking-[0.1em] text-hud-text group-hover:text-hud-glow">
            {edge.label}
          </span>
        </div>
        <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-hud-textFaint">
          {edge.predicate.replace(/_/g, " ")}
        </div>
      </div>
      <span
        className="shrink-0 rounded-sm border border-hud-line px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.15em]"
        style={{ color: colour, borderColor: `${colour}44` }}
      >
        {edge.kind}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Panel props
// ---------------------------------------------------------------------------
export interface EntityDetailPanelProps {
  entityId: number | null;
  onClose: () => void;
  onSelectEntity: (id: number) => void;
}

// ---------------------------------------------------------------------------
// Main panel component
// ---------------------------------------------------------------------------
export function EntityDetailPanel({
  entityId,
  onClose,
  onSelectEntity,
}: EntityDetailPanelProps) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (entityId === null) {
      setDetail(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getEntityDetail(entityId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load entity.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId]);

  // Panel is hidden when no entity selected
  const visible = entityId !== null;

  return (
    <div
      className={cn(
        "fixed right-0 top-0 z-40 flex h-screen w-[380px] flex-col border-l border-hud-line bg-hud-deep/95 backdrop-blur-md",
        "transition-transform duration-300 ease-in-out",
        visible ? "translate-x-0" : "translate-x-full",
      )}
      style={{ boxShadow: "-8px 0 40px rgba(0,0,0,0.5)" }}
      aria-hidden={!visible}
    >
      {/* Header */}
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-hud-line px-5 py-4">
        <div className="min-w-0 flex-1 space-y-1">
          {detail && (
            <>
              <div className="font-mono text-[9px] uppercase tracking-[0.4em] text-hud-textFaint">
                Entity Detail
              </div>
              <h2 className="font-display text-base uppercase tracking-[0.14em] text-hud-text leading-tight">
                {detail.label}
              </h2>
              <span
                className="inline-block rounded-sm border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.2em]"
                style={{
                  color: kindColour(detail.kind),
                  borderColor: `${kindColour(detail.kind)}55`,
                  background: `${kindColour(detail.kind)}10`,
                }}
              >
                {detail.kind}
              </span>
            </>
          )}
          {loading && (
            <div className="flex items-center gap-2 py-1">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-hud-glow" />
              <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textFaint">
                Loading…
              </span>
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 py-1">
              <AlertTriangle className="h-3.5 w-3.5 text-hud-warn" />
              <span className="font-mono text-[10px] text-hud-warn">{error}</span>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-0.5 shrink-0 rounded-md p-1.5 text-hud-textDim transition-colors hover:bg-hud-panel hover:text-hud-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-hud-glow"
          aria-label="Close entity detail"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Scrollable body */}
      {detail && !loading && (
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Salience bar */}
          <SalienceBar value={detail.salience} />

          {/* Description */}
          {detail.description && (
            <div className="rounded-md border border-hud-line bg-hud-panel/30 px-3 py-3">
              <p className="text-[12px] leading-relaxed text-hud-textDim">{detail.description}</p>
            </div>
          )}

          {/* Outgoing relationships */}
          {detail.outgoing.length > 0 && (
            <section className="space-y-2">
              <div className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                Points To &mdash; {detail.outgoing.length}
              </div>
              <div className="space-y-1.5">
                {detail.outgoing.map((edge) => (
                  <NeighbourRow
                    key={`out-${edge.entity_id}-${edge.predicate}`}
                    edge={edge}
                    direction="out"
                    onSelectEntity={onSelectEntity}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Incoming relationships */}
          {detail.incoming.length > 0 && (
            <section className="space-y-2">
              <div className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                Pointed At By &mdash; {detail.incoming.length}
              </div>
              <div className="space-y-1.5">
                {detail.incoming.map((edge) => (
                  <NeighbourRow
                    key={`in-${edge.entity_id}-${edge.predicate}`}
                    edge={edge}
                    direction="in"
                    onSelectEntity={onSelectEntity}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Evidence messages */}
          {detail.evidence_messages.length > 0 && (
            <section className="space-y-2">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-3 w-3 text-hud-textFaint" />
                <span className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                  Evidence &mdash; {detail.evidence_messages.length} message
                  {detail.evidence_messages.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="space-y-2">
                {detail.evidence_messages.map((msg) => (
                  <button
                    key={msg.message_id}
                    type="button"
                    onClick={() => navigate(`/history/${msg.conversation_id}`)}
                    className="group w-full rounded-md border border-hud-line bg-hud-panel/30 px-3 py-3 text-left transition-colors hover:border-hud-glow/40 hover:bg-hud-panelHi"
                  >
                    <p className="mb-2 font-mono text-[11px] leading-relaxed text-hud-textDim group-hover:text-hud-text line-clamp-4">
                      {msg.snippet}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="rounded-sm border border-hud-line bg-hud-panel/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.15em] text-hud-glow2"
                      >
                        {msg.source_slug}
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-hud-textFaint">
                        {msg.role}
                      </span>
                      {msg.conversation_title && (
                        <span className="min-w-0 flex-1 truncate font-mono text-[9px] text-hud-textFaint">
                          {msg.conversation_title}
                        </span>
                      )}
                      <span className="ml-auto shrink-0 font-mono text-[9px] text-hud-textFaint">
                        {fmtDate(msg.message_at)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Related reports */}
          {detail.related_reports.length > 0 && (
            <section className="space-y-2">
              <div className="flex items-center gap-2">
                <BookOpen className="h-3 w-3 text-hud-textFaint" />
                <span className="font-mono text-[9px] uppercase tracking-[0.35em] text-hud-textFaint">
                  Reports &mdash; {detail.related_reports.length}
                </span>
              </div>
              <div className="space-y-2">
                {detail.related_reports.map((rep) => (
                  <button
                    key={`${rep.report_id}-${rep.block_type}`}
                    type="button"
                    onClick={() => navigate(`/insights/reports/${rep.report_id}`)}
                    className="group w-full rounded-md border border-hud-line bg-hud-panel/30 px-3 py-3 text-left transition-colors hover:border-hud-glow/40 hover:bg-hud-panelHi"
                  >
                    {rep.block_heading && (
                      <p className="mb-1 font-display text-[10px] uppercase tracking-[0.14em] text-hud-accent group-hover:text-hud-glow">
                        {rep.block_heading}
                      </p>
                    )}
                    <p className="mb-2 font-mono text-[11px] leading-relaxed text-hud-textDim group-hover:text-hud-text line-clamp-3">
                      {rep.snippet}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="rounded-sm border border-hud-line bg-hud-panel/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.15em] text-hud-glow2">
                        {rep.report_kind.replace(/_/g, " ")}
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-hud-textFaint">
                        {rep.block_type.replace(/_/g, " ")}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Empty state: no evidence or reports */}
          {detail.evidence_messages.length === 0 && detail.related_reports.length === 0 && (
            <div className="rounded-md border border-hud-line bg-hud-panel/20 px-4 py-6 text-center">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textFaint">
                No evidence messages or reports reference this entity yet.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
