import * as Dialog from "@radix-ui/react-dialog";
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import { Download, ExternalLink, X } from "lucide-react";

import { cn, fmtDate } from "@/lib/utils";
import { SpeedometerGauge } from "@/components/SpeedometerGauge";
import type { ReportResponse } from "@/types/api";

export interface ReportResultModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  report: ReportResponse | null;
  /** When true, show a "Download .md" button. */
  downloadable?: boolean;
  /** Fired when the user clicks the download button. */
  onDownload?: () => void;
}

const KIND_LABELS: Record<string, string> = {
  full_mirror: "Full Mirror Analysis",
  advanced_abstract: "Advanced Abstract Analysis",
  focus_lens: "Focus Lens",
  deep_dive: "Deep Dive",
};

export function ReportResultModal({
  open,
  onOpenChange,
  report,
  downloadable,
  onDownload,
}: ReportResultModalProps) {
  const navigate = useNavigate();
  if (!report) return null;

  const kindLabel = KIND_LABELS[report.kind] ?? report.kind;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-hud-void/85 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />
        <Dialog.Content
          className={cn(
            "!fixed left-1/2 top-1/2 z-50 w-full max-w-[1040px] -translate-x-1/2 -translate-y-1/2",
            "flex max-h-[90vh] flex-col",
            "holo-panel rounded-lg",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          )}
        >
          {/* Header */}
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-hud-line px-7 py-5">
            <div className="space-y-1 min-w-0">
              <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
                {kindLabel} · Report #{report.report_id} ·{" "}
                {report.model_used ?? "no model"}
              </div>
              <Dialog.Title className="font-display text-xl uppercase tracking-[0.14em] text-hud-text">
                {report.title}
              </Dialog.Title>
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
                {fmtDate(report.created_at)}
              </div>
            </div>
            <Dialog.Close
              className="mt-0.5 shrink-0 rounded-md p-1.5 text-hud-textDim transition-colors hover:bg-hud-panel hover:text-hud-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-hud-glow"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-7 py-6 space-y-6">
            {/* Executive summary + gauges */}
            <section className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_auto]">
              <div className="space-y-2">
                <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
                  Executive Summary
                </div>
                <p className="whitespace-pre-line font-sans text-[14px] leading-relaxed text-hud-text">
                  {report.summary || "(no summary returned)"}
                </p>
              </div>
              {report.gauges && (
                <div className="grid grid-cols-3 items-end gap-5">
                  <SpeedometerGauge
                    label="Thought Clarity"
                    value={report.gauges.thought_clarity}
                    size={132}
                  />
                  <SpeedometerGauge
                    label="Self-Reflection Depth"
                    value={report.gauges.self_reflection_depth}
                    size={132}
                  />
                  <SpeedometerGauge
                    label="Aptitude Balance"
                    value={report.gauges.aptitude_balance}
                    size={132}
                  />
                </div>
              )}
            </section>

            {/* Blocks */}
            {report.blocks.length > 0 && (
              <section className="space-y-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
                  {report.blocks.length} section
                  {report.blocks.length !== 1 ? "s" : ""}
                </div>
                {report.blocks
                  .slice()
                  .sort((a, b) => a.position - b.position)
                  .map((block) => (
                    <div
                      key={block.id}
                      className="rounded-md border border-hud-line bg-hud-panel/40 px-5 py-4"
                    >
                      <div className="flex items-baseline gap-3 mb-2">
                        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-glow">
                          {block.block_type.replace(/_/g, " ")}
                        </span>
                        {block.heading && (
                          <span className="font-display text-[13px] uppercase tracking-[0.14em] text-hud-text">
                            {block.heading}
                          </span>
                        )}
                      </div>
                      <div className="prose-hud text-[13px]">
                        <ReactMarkdown>{block.body_markdown}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
              </section>
            )}
          </div>

          {/* Footer */}
          <div className="flex shrink-0 items-center justify-between gap-3 border-t border-hud-line px-7 py-4">
            <button
              type="button"
              onClick={() => {
                onOpenChange(false);
                navigate(`/insights/reports/${report.report_id}`);
              }}
              className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textDim hover:text-hud-text transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open full viewer
            </button>
            <div className="flex items-center gap-3">
              {downloadable && onDownload && (
                <button
                  type="button"
                  onClick={onDownload}
                  className="neon-btn inline-flex items-center gap-2 rounded-md px-5 py-2 font-display text-[11px] uppercase tracking-[0.22em]"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download .md report
                </button>
              )}
              <Dialog.Close className="font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textFaint hover:text-hud-textDim transition-colors">
                Close
              </Dialog.Close>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
