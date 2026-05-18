import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Calendar, Cpu, Loader2, Tag } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { SpeedometerGauge } from "@/components/SpeedometerGauge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { Evidence, ReportBlockOut, ReportResponse } from "@/types/api";

export function ReportViewerPage() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ? parseInt(id, 10) : NaN;

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNaN(reportId)) {
      setError("Invalid report ID.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getReport(reportId)
      .then((d) => {
        if (!cancelled) {
          setReport(d);
          setLoading(false);
        }
      })
      .catch((exc) => {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "Failed to load report.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  return (
    <div className="space-y-8">
      {/* Back link */}
      <Link
        to="/insights/reports"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textDim hover:text-hud-glow transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Reports
      </Link>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-hud-glow" />
        </div>
      )}

      {/* Error */}
      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {/* Report content */}
      {!loading && report && (
        <>
          {/* Heading area */}
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
                Report · #{report.report_id} · {report.kind}
              </div>
              <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
                {report.title}
              </h1>
            </div>
            <div className="rounded-md border border-hud-line bg-hud-panel/40 px-5 py-3 space-y-1.5">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-hud-textFaint">
                <Cpu className="h-3.5 w-3.5 text-hud-glow/70" />
                <span>{report.model_used ?? "—"}</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-hud-textFaint">
                <Calendar className="h-3.5 w-3.5 text-hud-glow/70" />
                <span>{fmtDate(report.created_at)}</span>
              </div>
            </div>
          </div>

          {/* Summary + gauges */}
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <div
                className={cn(
                  "grid gap-8",
                  report.gauges ? "grid-cols-1 lg:grid-cols-[1fr_auto]" : "grid-cols-1",
                )}
              >
                <div className="prose-hud text-[13px]">
                  <ReactMarkdown>{report.summary}</ReactMarkdown>
                </div>
                {report.gauges && (
                  <div className="grid grid-cols-3 items-end gap-5">
                    <SpeedometerGauge
                      label="Thought Clarity"
                      value={report.gauges.thought_clarity}
                    />
                    <SpeedometerGauge
                      label="Self-Reflection Depth"
                      value={report.gauges.self_reflection_depth}
                    />
                    <SpeedometerGauge
                      label="Aptitude Balance"
                      value={report.gauges.aptitude_balance}
                    />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Blocks */}
          {report.blocks.length > 0 && (
            <div className="space-y-4">
              {report.blocks.map((block) => (
                <BlockCard key={block.id} block={block} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Block card ─────────────────────────────────────────────────────────────────

function BlockCard({ block }: { block: ReportBlockOut }) {
  const hasEvidence = Array.isArray(block.evidence) && block.evidence.length > 0;

  return (
    <Card>
      <CardContent className="pt-5 pb-5 space-y-3">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-[10px] tabular-nums rounded-sm border border-hud-line bg-hud-panel/60 px-2 py-0.5 text-hud-textFaint">
            {String(block.position).padStart(2, "0")}
          </span>
          <span className="font-display text-[11px] uppercase tracking-[0.18em] text-hud-glow">
            {block.block_type}
          </span>
          {block.heading && (
            <span className="font-display text-[14px] tracking-[0.05em] text-hud-text">
              {block.heading}
            </span>
          )}
        </div>

        {/* Body */}
        <div className="prose-hud text-[13px]">
          <ReactMarkdown>{block.body_markdown}</ReactMarkdown>
        </div>

        {/* Evidence accordion */}
        {hasEvidence && (
          <Accordion type="single" collapsible>
            <AccordionItem value="evidence" className="border-hud-line/40">
              <AccordionTrigger className="text-[11px]">
                <span className="flex items-center gap-2">
                  <Tag className="h-3.5 w-3.5 text-hud-glow/70" />
                  Evidence ({block.evidence!.length})
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2 pt-1">
                  {block.evidence!.map((ev, i) => (
                    <EvidenceTile key={i} evidence={ev} />
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
}

// ── Evidence tile ──────────────────────────────────────────────────────────────

function EvidenceTile({ evidence }: { evidence: Evidence }) {
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/30 px-4 py-3 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {evidence.source_slug && (
          <span className="rounded-sm border border-hud-glow/40 bg-hud-glow/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-hud-glow">
            {evidence.source_slug}
          </span>
        )}
        <span
          className={cn(
            "rounded-sm border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em]",
            evidence.source_slug
              ? "border-hud-line text-hud-textFaint"
              : "border-hud-line text-hud-textFaint",
          )}
        >
          {/* role derived from message context; not exposed directly on Evidence */}
          msg
        </span>
        {evidence.message_at && (
          <span className="font-mono text-[9px] text-hud-textFaint">
            {fmtDate(evidence.message_at)}
          </span>
        )}
      </div>
      <p className="font-sans text-[12px] leading-relaxed text-hud-textDim">{evidence.snippet}</p>
    </div>
  );
}
