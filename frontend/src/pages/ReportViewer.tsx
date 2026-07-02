import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Calendar, Cpu, Loader2, ShieldAlert, Tag } from "lucide-react";
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
import { blockClaims, blockCritique, blockGrounding, isCritiqueBlock, reportGrounding } from "@/lib/claims";
import { cn, fmtDate } from "@/lib/utils";
import type {
  Claim,
  ClaimEvidence,
  Critique,
  Evidence,
  GroundingStats,
  ReportBlockOut,
  ReportResponse,
} from "@/types/api";

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

  const grounding = report ? reportGrounding(report.blocks) : null;

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
              {grounding && <GroundingStatsRow grounding={grounding} className="mt-3" />}
              {report.model_used === null && (
                <span
                  className="mt-3 inline-block rounded-sm border border-hud-line px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.18em] text-hud-textFaint"
                  title="Generated without a model — content is placeholder, not insight."
                >
                  Not analyzed — placeholder
                </span>
              )}
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

// ── Report-level grounding stats ───────────────────────────────────────────────

function GroundingStatsRow({
  grounding,
  className,
}: {
  grounding: GroundingStats;
  className?: string;
}) {
  const pct = Math.round(Math.min(1, Math.max(0, grounding.grounding_ratio)) * 100);
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.18em]",
        className,
      )}
    >
      <span className="rounded-sm border border-hud-glow/40 bg-hud-glow/5 px-2 py-0.5 text-hud-glow">
        Grounding {pct}%
      </span>
      <span className="text-hud-textDim">
        {grounding.grounded_claims}/{grounding.total_claims} claims grounded
      </span>
      <span className="text-hud-textDim">
        {grounding.verified_evidence}/{grounding.total_evidence} evidence verified
      </span>
    </div>
  );
}

// ── Block card ─────────────────────────────────────────────────────────────────

function BlockCard({ block }: { block: ReportBlockOut }) {
  const critique = isCritiqueBlock(block) ? blockCritique(block) : null;
  if (critique) {
    return <CritiquePanel block={block} critique={critique} grounding={blockGrounding(block)} />;
  }

  const claims = blockClaims(block);
  const hasClaims = claims.length > 0;
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

        {/* Claims — first-class, above the prose */}
        {hasClaims && (
          <div className="space-y-2">
            {claims.map((claim, i) => (
              <ClaimRow key={i} claim={claim} />
            ))}
          </div>
        )}

        {/* Body — collapses behind a PROSE accordion when claims carry the signal */}
        {hasClaims ? (
          <Accordion type="single" collapsible>
            <AccordionItem value="prose" className="border-hud-line/40">
              <AccordionTrigger className="text-[11px]">Prose</AccordionTrigger>
              <AccordionContent>
                <div className="prose-hud text-[13px] pt-1">
                  <ReactMarkdown>{block.body_markdown}</ReactMarkdown>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : (
          <div className="prose-hud text-[13px]">
            <ReactMarkdown>{block.body_markdown}</ReactMarkdown>
          </div>
        )}

        {/* Legacy evidence accordion */}
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

// ── Claim row ──────────────────────────────────────────────────────────────────

function ClaimRow({ claim }: { claim: Claim }) {
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/30 px-4 py-3 space-y-2">
      <div className="flex items-start gap-3">
        <div className="flex shrink-0 flex-col items-start gap-1 pt-0.5">
          <ConfidenceBadge confidence={claim.confidence} />
          {claim.ungrounded && (
            <span
              className="rounded-sm border border-hud-warn/70 bg-transparent px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-hud-warn"
              title="No verified evidence supports this claim."
            >
              Ungrounded
            </span>
          )}
        </div>
        <p className="text-[13.5px] leading-relaxed text-hud-text">{claim.claim}</p>
      </div>

      {/* Evidence chips — verified link to the source conversation, unverified struck through */}
      {claim.evidence.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pl-1">
          {claim.evidence.map((ev, i) => (
            <EvidenceChip key={i} evidence={ev} />
          ))}
        </div>
      )}

      {/* Counter-evidence — visible, not hidden */}
      {claim.counter_evidence && (
        <div className="ml-3 border-l-2 border-hud-warn/50 pl-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-hud-warn">
            counter:
          </span>{" "}
          <span className="text-[12.5px] leading-relaxed text-hud-textDim">
            {claim.counter_evidence}
          </span>
        </div>
      )}

      {/* Critique annotations */}
      {claim.annotations && claim.annotations.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pl-1">
          {claim.annotations.map((a, i) => (
            <span
              key={i}
              title={a.note}
              className="inline-flex items-center gap-1 rounded-sm border border-hud-warn/50 bg-hud-warn/5 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-hud-warn"
            >
              <AlertTriangle className="h-2.5 w-2.5" />
              {a.issue} · {a.severity}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: Claim["confidence"] }) {
  const styles: Record<Claim["confidence"], string> = {
    high: "border-hud-glow/70 bg-hud-glow/10 text-hud-glow shadow-[0_0_10px_rgba(0,255,200,0.25)]",
    medium: "border-hud-accent/40 bg-hud-accent/5 text-hud-accent/80",
    low: "border-hud-line bg-transparent text-hud-textFaint",
  };
  const labels: Record<Claim["confidence"], string> = { high: "High", medium: "Med", low: "Low" };
  return (
    <span
      className={cn(
        "rounded-sm border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em]",
        styles[confidence] ?? styles.low,
      )}
    >
      {labels[confidence] ?? confidence}
    </span>
  );
}

function EvidenceChip({ evidence }: { evidence: ClaimEvidence }) {
  const label = [
    evidence.source_slug ?? `msg #${evidence.message_id}`,
    evidence.message_at ? fmtDate(evidence.message_at) : null,
  ]
    .filter(Boolean)
    .join(" · ");

  if (evidence.verified && evidence.conversation_id != null) {
    return (
      <Link
        to={`/history/${evidence.conversation_id}`}
        title={evidence.quote}
        className="rounded-sm border border-hud-glow/40 bg-hud-glow/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-hud-glow transition-colors hover:border-hud-glow hover:bg-hud-glow/10"
      >
        {label}
      </Link>
    );
  }
  if (evidence.verified) {
    return (
      <span
        title={evidence.quote}
        className="rounded-sm border border-hud-glow/40 bg-hud-glow/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-hud-glow"
      >
        {label}
      </span>
    );
  }
  return (
    <span
      title={`unverified — quote not found in source: ${evidence.quote}`}
      className="rounded-sm border border-hud-line px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-hud-textFaint line-through decoration-hud-warn/60"
    >
      {label} · unverified
    </span>
  );
}

// ── Adversarial review (critique block) ────────────────────────────────────────

function CritiquePanel({
  block,
  critique,
  grounding,
}: {
  block: ReportBlockOut;
  critique: Critique;
  grounding: GroundingStats | null;
}) {
  return (
    <Card className="relative border-hud-warn/30">
      {/* Warn-colour corner brackets */}
      <span className="pointer-events-none absolute -left-px -top-px z-10 h-4 w-4 border-l border-t border-hud-warn/80" />
      <span className="pointer-events-none absolute -right-px -top-px z-10 h-4 w-4 border-r border-t border-hud-warn/80" />
      <span className="pointer-events-none absolute -bottom-px -left-px z-10 h-4 w-4 border-b border-l border-hud-warn/80" />
      <span className="pointer-events-none absolute -bottom-px -right-px z-10 h-4 w-4 border-b border-r border-hud-warn/80" />

      <CardContent className="pt-5 pb-5 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <ShieldAlert className="h-4 w-4 text-hud-warn" />
          <span className="font-display text-[12px] uppercase tracking-[0.28em] text-hud-warn">
            Adversarial Review
          </span>
          {block.heading && (
            <span className="font-display text-[13px] tracking-[0.05em] text-hud-text">
              {block.heading}
            </span>
          )}
        </div>

        {/* Score chips */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ScoreChip
            label="Sycophancy"
            value={critique.sycophancy_score}
            hint="Lower is better — how much the analysis flatters instead of reports."
          />
          <ScoreChip
            label="Balance"
            value={critique.balance_score}
            hint="Higher is better — strengths and weaknesses weighed evenly."
          />
        </div>

        {/* Grounding ratio bar */}
        {grounding && <GroundingBar grounding={grounding} />}

        {/* Overall verdict */}
        {critique.overall && (
          <p className="text-[13px] leading-relaxed text-hud-text">{critique.overall}</p>
        )}

        {/* Standing objections */}
        {critique.verdicts.length > 0 && (
          <div className="space-y-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-hud-textFaint">
              Standing objections ({critique.verdicts.length})
            </div>
            {critique.verdicts.map((v, i) => (
              <div
                key={i}
                className="rounded-md border border-hud-warn/25 bg-hud-warn/[0.03] px-4 py-2.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("font-mono text-[9px] uppercase tracking-[0.16em] rounded-sm border px-1.5 py-0.5", severityClass(v.severity))}>
                    {v.severity}
                  </span>
                  <span className="font-display text-[11px] uppercase tracking-[0.14em] text-hud-text">
                    {v.target}
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-hud-warn">
                    {v.issue}
                  </span>
                </div>
                {v.note && (
                  <p className="mt-1 text-[12px] leading-relaxed text-hud-textDim">{v.note}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Prose body, if any, stays available */}
        {block.body_markdown.trim() && (
          <Accordion type="single" collapsible>
            <AccordionItem value="prose" className="border-hud-line/40">
              <AccordionTrigger className="text-[11px]">Prose</AccordionTrigger>
              <AccordionContent>
                <div className="prose-hud text-[13px] pt-1">
                  <ReactMarkdown>{block.body_markdown}</ReactMarkdown>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
}

function severityClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case "critical":
    case "high":
      return "border-red-400/60 text-red-400";
    case "medium":
    case "moderate":
      return "border-hud-warn/60 text-hud-warn";
    default:
      return "border-hud-line text-hud-textDim";
  }
}

/** Normalise a score into [0,1] for the bar; the raw number is shown verbatim. */
function normaliseScore(value: number): number {
  const v = value > 1 ? value / 10 : value;
  return Math.min(1, Math.max(0, v));
}

function ScoreChip({ label, value, hint }: { label: string; value: number; hint: string }) {
  const frac = normaliseScore(value);
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3" title={hint}>
      <div className="flex items-baseline justify-between">
        <span className="font-display text-[10px] uppercase tracking-[0.22em] text-hud-textDim">
          {label}
        </span>
        <span className="font-mono text-[14px] tabular-nums text-hud-text">
          {Number.isFinite(value) ? value.toFixed(2) : "—"}
        </span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-hud-line/50">
        <div
          className="h-full rounded-full bg-hud-warn/80"
          style={{ width: `${Math.round(frac * 100)}%` }}
        />
      </div>
    </div>
  );
}

function GroundingBar({ grounding }: { grounding: GroundingStats }) {
  const frac = Math.min(1, Math.max(0, grounding.grounding_ratio));
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3">
      <div className="flex items-baseline justify-between">
        <span className="font-display text-[10px] uppercase tracking-[0.22em] text-hud-textDim">
          Grounding
        </span>
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-hud-textDim">
          {grounding.grounded_claims}/{grounding.total_claims} claims ·{" "}
          {grounding.verified_evidence}/{grounding.total_evidence} evidence verified
        </span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-hud-line/50">
        <div
          className="h-full rounded-full bg-hud-glow shadow-[0_0_8px_rgba(0,255,200,0.5)]"
          style={{ width: `${Math.round(frac * 100)}%` }}
        />
      </div>
    </div>
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
