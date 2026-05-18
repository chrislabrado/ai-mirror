import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, Layers, Loader2, Telescope } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Card, CardContent } from "@/components/ui/card";
import { DeepDiveModal } from "@/components/DeepDiveModal";
import { api } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { AggregatedBlock, InsightsAggregated } from "@/types/api";

interface ActiveBlock {
  blockType: string;
  heading: string;
  sampleBody?: string;
}

export function InsightsPage() {
  const [data, setData] = useState<InsightsAggregated | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeBlock, setActiveBlock] = useState<ActiveBlock | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .insightsAggregated()
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((exc) => {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "Failed to load insights.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const avgBlocks =
    data && data.total_reports > 0
      ? (data.total_blocks / data.total_reports).toFixed(1)
      : "—";

  function openBlock(block: AggregatedBlock) {
    setActiveBlock({
      blockType: block.block_type,
      heading: block.heading ?? block.block_type,
      sampleBody: block.sample_body,
    });
  }

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Section 6.4 · Insights Hub
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Insights
          </h1>
        </div>

        <Link
          to="/insights/reports"
          className="neon-btn inline-flex items-center gap-2 rounded-md px-4 py-2 font-display text-[11px] uppercase tracking-[0.22em]"
        >
          View all reports
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {/* Summary strip */}
      {data && (
        <div className="grid grid-cols-3 gap-4 font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textDim">
          <InsightStat label="Total Reports" value={data.total_reports.toLocaleString()} />
          <InsightStat label="Total Blocks" value={data.total_blocks.toLocaleString()} />
          <InsightStat label="Avg Blocks / Report" value={String(avgBlocks)} />
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-hud-glow" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!loading && !error && data && data.blocks.length === 0 && (
        <div className="flex items-center justify-center py-24">
          <p className="font-mono text-[13px] uppercase tracking-[0.2em] text-hud-textFaint">
            No insights yet — run a Full Mirror or Advanced Abstract analysis to populate blocks.
          </p>
        </div>
      )}

      {/* Blocks list */}
      {!loading && data && data.blocks.length > 0 && (
        <div className="space-y-4">
          {data.blocks.map((block, i) => (
            <BlockCard key={i} block={block} onOpenDeepDive={() => openBlock(block)} />
          ))}
        </div>
      )}

      {/* Deep Dive Modal */}
      <DeepDiveModal
        open={activeBlock !== null}
        onOpenChange={(open) => { if (!open) setActiveBlock(null); }}
        blockType={activeBlock?.blockType ?? ""}
        blockHeading={activeBlock?.heading ?? ""}
        sampleBody={activeBlock?.sampleBody}
      />
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function InsightStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3">
      <div className="text-[10px] tracking-[0.25em] text-hud-textFaint">{label}</div>
      <div className="mt-1 font-display text-base normal-case text-hud-text">{value}</div>
    </div>
  );
}

function BlockCard({
  block,
  onOpenDeepDive,
}: {
  block: AggregatedBlock;
  onOpenDeepDive: () => void;
}) {
  return (
    <Card
      role="button"
      tabIndex={0}
      aria-label={`Deep dive into ${block.heading ?? block.block_type}`}
      onClick={onOpenDeepDive}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpenDeepDive(); }}
      className={cn(
        "cursor-pointer transition-colors duration-200",
        "hover:border-hud-glow/60",
      )}
    >
      <CardContent className="pt-5 pb-5 space-y-3">
        {/* Header row */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Layers className="h-3.5 w-3.5 shrink-0 text-hud-glow/70" />
            <span className="font-display text-[11px] uppercase tracking-[0.18em] text-hud-glow">
              {block.block_type}
            </span>
          </div>
          <span className="shrink-0 rounded-sm border border-hud-line bg-hud-panel/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-hud-textDim">
            &times;{block.occurrence_count}
          </span>
        </div>

        {/* Block heading */}
        {block.heading && (
          <h3 className="font-display text-[15px] tracking-[0.06em] text-hud-text">
            {block.heading}
          </h3>
        )}

        {/* Sample body */}
        <div className="prose-hud text-[13px]">
          <ReactMarkdown>{block.sample_body}</ReactMarkdown>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
            <BarChart3 className="h-3 w-3" />
            <span>Most recent &rarr;</span>
            <Link
              to={`/insights/reports/${block.latest_report_id}`}
              className="text-hud-glow2 hover:text-hud-glow transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              Report #{block.latest_report_id}
            </Link>
            <span>&middot;</span>
            <span>{fmtDate(block.latest_created_at)}</span>
          </div>

          {/* Deep Dive pill */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOpenDeepDive(); }}
            className={cn(
              "neon-btn inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5",
              "font-display text-[10px] uppercase tracking-[0.22em]",
            )}
            aria-label={`Run deep dive on ${block.heading ?? block.block_type}`}
          >
            <Telescope className="h-3 w-3" />
            Deep Dive
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
