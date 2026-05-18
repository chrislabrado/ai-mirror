import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import ReactMarkdown from "react-markdown";
import { Loader2, X, Telescope } from "lucide-react";

import { api } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { DeepDiveResponse } from "@/types/api";


/** Trim a long sample body to its first N sentences for the modal preview. */
function firstSentences(text: string, max = 3): string {
  const clean = text.trim();
  if (!clean) return "";
  // Strip markdown-ish leading hashes/bullets if present.
  const stripped = clean.replace(/^#+\s.*\n+/m, "").trim();
  const parts = stripped.match(/[^.!?]+[.!?]+(?:\s|$)/g) ?? [stripped];
  const picked = parts.slice(0, max).join("").trim();
  return picked || stripped.slice(0, 480);
}

export interface DeepDiveModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  blockType: string;
  blockHeading: string;
  sampleBody?: string;
}

export function DeepDiveModal({
  open,
  onOpenChange,
  blockType,
  blockHeading,
  sampleBody,
}: DeepDiveModalProps) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DeepDiveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setQuestion("");
    setLoading(false);
    setResult(null);
    setError(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function runDeepDive() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.insightsDeepDive({
        block_type: blockType,
        focus_question: question.trim() || undefined,
      });
      setResult(response);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        {/* Backdrop */}
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-hud-void/85 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />

        {/* Content panel.
            NB: `holo-panel` sets `position: relative` (it's defined in
            index.css *after* @tailwind utilities, so it wins the cascade
            and clobbers Tailwind's `fixed`). Use the !important variant
            of `fixed` to keep the dialog viewport-centred. */}
        <Dialog.Content
          className={cn(
            "!fixed left-1/2 top-1/2 z-50 w-full max-w-[920px] -translate-x-1/2 -translate-y-1/2",
            "flex max-h-[85vh] flex-col",
            "holo-panel rounded-lg",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          )}
        >
          {/* Header */}
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-hud-line px-6 py-5">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Telescope className="h-3.5 w-3.5 text-hud-glow/70" />
                <span className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
                  Deep Dive · {blockType}
                </span>
              </div>
              <Dialog.Title className="font-display text-xl uppercase tracking-[0.14em] text-hud-text">
                {blockHeading}
              </Dialog.Title>
            </div>

            <Dialog.Close
              className={cn(
                "mt-0.5 shrink-0 rounded-md p-1.5 text-hud-textDim transition-colors",
                "hover:bg-hud-panel hover:text-hud-text",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-hud-glow",
              )}
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">

            {/* Inline summary — 2-4 sentences from the most recent block of
                this type. Always visible; no collapse. */}
            {sampleBody && !result && (
              <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3 space-y-2">
                <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
                  Summary
                </div>
                <p className="font-sans text-[13.5px] leading-relaxed text-hud-text">
                  {firstSentences(sampleBody, 4)}
                </p>
              </div>
            )}

            {/* Focus question input */}
            {!result && !loading && (
              <div className="space-y-2">
                <label
                  htmlFor="deep-dive-question"
                  className="block font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textDim"
                >
                  Focus question (optional)
                </label>
                <input
                  id="deep-dive-question"
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") runDeepDive(); }}
                  placeholder="e.g. How does this manifest in technical work?"
                  className={cn(
                    "w-full rounded-md border border-hud-line bg-hud-panel/60 px-4 py-2.5",
                    "font-mono text-[13px] text-hud-text placeholder:text-hud-textFaint",
                    "transition-colors focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/40",
                  )}
                />
              </div>
            )}

            {/* Loading state */}
            {loading && (
              <div className="flex flex-col items-center justify-center gap-4 py-16">
                <Loader2 className="h-7 w-7 animate-spin text-hud-glow" />
                <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-hud-textDim">
                  Analysing through the lens of {blockHeading}&hellip;
                </p>
              </div>
            )}

            {/* Error state */}
            {error && !loading && (
              <div className="rounded-md border border-hud-warn/40 bg-hud-warn/5 px-4 py-4 space-y-3">
                <p className="font-mono text-[12px] text-hud-warn">{error}</p>
                <button
                  type="button"
                  onClick={runDeepDive}
                  className="neon-btn inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-[10px] uppercase tracking-[0.22em]"
                >
                  Try again
                </button>
              </div>
            )}

            {/* Result */}
            {result && !loading && (
              <div className="space-y-5">
                {/* Sub-heading from response */}
                <h3 className="font-display text-[15px] uppercase tracking-[0.12em] text-hud-accent">
                  {result.heading}
                </h3>

                {/* Metadata line */}
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
                  {result.duration_seconds.toFixed(1)}s
                  {result.model_used && (
                    <> &middot; {result.model_used}</>
                  )}
                  {" "}&middot; {fmtDate(result.created_at)}
                </div>

                {/* Markdown body */}
                <div className="prose-hud text-[13px]">
                  <ReactMarkdown>{result.body_markdown}</ReactMarkdown>
                </div>

                {/* Evidence */}
                {result.evidence.length > 0 && (
                  <div className="space-y-3">
                    <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
                      Evidence &mdash; {result.evidence.length} source{result.evidence.length !== 1 ? "s" : ""}
                    </div>
                    <div className="space-y-2">
                      {result.evidence.map((ev, idx) => (
                        <div
                          key={idx}
                          className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3 space-y-1.5"
                        >
                          <p className="font-mono text-[12px] leading-relaxed text-hud-textDim">
                            {ev.snippet.length > 300
                              ? `${ev.snippet.slice(0, 300)}…`
                              : ev.snippet}
                          </p>
                          <div className="flex flex-wrap items-center gap-3">
                            {ev.source_slug && (
                              <span className="rounded-sm border border-hud-line bg-hud-panel/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-hud-glow2">
                                {ev.source_slug}
                              </span>
                            )}
                            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-hud-textFaint">
                              {fmtDate(ev.message_at)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Run again option */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => { setResult(null); setError(null); }}
                    className="font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textFaint underline decoration-hud-textFaint/40 hover:text-hud-textDim transition-colors"
                  >
                    Run again with a different question
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer action bar — only visible before result */}
          {!result && !loading && (
            <div className="flex shrink-0 items-center justify-end gap-3 border-t border-hud-line px-6 py-4">
              <Dialog.Close
                className="font-mono text-[10px] uppercase tracking-[0.28em] text-hud-textFaint hover:text-hud-textDim transition-colors"
              >
                Cancel
              </Dialog.Close>
              <button
                type="button"
                onClick={runDeepDive}
                className="neon-btn inline-flex items-center gap-2 rounded-md px-5 py-2 font-display text-[11px] uppercase tracking-[0.22em]"
              >
                <Telescope className="h-3.5 w-3.5" />
                Run Deep Dive
              </button>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
