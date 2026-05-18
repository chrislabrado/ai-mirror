import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, UploadCloud } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { IngestResponse } from "@/types/api";

const SOURCES = [
  { value: "auto", label: "Auto-detect" },
  { value: "chatgpt", label: "ChatGPT" },
  { value: "claude", label: "Claude" },
  { value: "grok", label: "Grok" },
  { value: "gemini", label: "Gemini" },
  { value: "perplexity", label: "Perplexity" },
  { value: "local", label: "Local" },
] as const;

const ACCEPTED_FORMATS = ".json, .zip, .md, .markdown";

interface IngestResult {
  filename: string;
  source: string;
  conversations_imported: number;
  messages_imported: number;
}

interface IngestDropzoneProps {
  onIngestComplete?: () => void;
}

export function IngestDropzone({ onIngestComplete }: IngestDropzoneProps) {
  const [source, setSource] = useState<string>("auto");
  const [pending, setPending] = useState(false);
  const [results, setResults] = useState<IngestResult[]>([]);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    setPending(true);
    setIngestError(null);
    setResults([]);

    const accumulated: IngestResult[] = [];

    try {
      for (const file of acceptedFiles) {
        const resp: IngestResponse = await api.ingest(file, source);
        accumulated.push({
          filename: resp.filename,
          source: resp.source,
          conversations_imported: resp.conversations_imported,
          messages_imported: resp.messages_imported,
        });
      }
      setResults(accumulated);
      onIngestComplete?.();
    } catch (exc) {
      setIngestError(exc instanceof Error ? exc.message : "Ingest failed.");
    } finally {
      setPending(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/json": [".json"],
      "application/zip": [".zip"],
      "application/x-zip-compressed": [".zip"],
      "text/markdown": [".md", ".markdown"],
      "text/plain": [".md", ".markdown"],
    },
    disabled: pending,
    multiple: true,
  });

  return (
    <div className="space-y-3">
      {/* Source selector */}
      <div className="flex items-center gap-3">
        <label className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint whitespace-nowrap">
          Source
        </label>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          disabled={pending}
          className="h-8 appearance-none rounded-md border border-hud-line bg-hud-panel/40 px-3 font-mono text-[12px] text-hud-text focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors cursor-pointer disabled:opacity-50"
        >
          {SOURCES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-all duration-200",
          "border-hud-line bg-hud-panel/30",
          isDragActive && "border-hud-glow bg-hud-glow/5 shadow-[0_0_32px_rgba(0,255,200,0.18)]",
          pending && "cursor-wait opacity-60",
        )}
      >
        <input {...getInputProps()} />

        {pending ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-hud-glow" />
            <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-hud-textDim">
              Ingesting&hellip;
            </span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 px-6 text-center">
            <UploadCloud
              className={cn(
                "h-8 w-8 transition-colors",
                isDragActive ? "text-hud-glow" : "text-hud-textFaint",
              )}
            />
            <div className="space-y-1">
              <p className="font-display text-[13px] uppercase tracking-[0.2em] text-hud-text">
                Drop conversation export here, or click to browse
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textFaint">
                Accepted formats: {ACCEPTED_FORMATS}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {ingestError && (
        <div className="rounded-md border border-hud-warn/40 bg-hud-warn/5 px-4 py-2 font-mono text-[12px] text-hud-warn">
          {ingestError}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((r, i) => (
            <Card key={i} className="border-hud-glow/25">
              <CardContent className="pt-4 pb-4">
                <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1">
                  <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textDim">
                    {r.filename}
                    <span className="ml-2 rounded-sm border border-hud-line px-1.5 py-0.5 text-[9px] text-hud-textFaint">
                      {r.source}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 font-mono text-[11px] uppercase tracking-[0.2em]">
                    <span>
                      <span className="text-hud-glow">
                        {r.conversations_imported.toLocaleString()}
                      </span>
                      <span className="ml-1.5 text-hud-textFaint">convs</span>
                    </span>
                    <span>
                      <span className="text-hud-glow">
                        {r.messages_imported.toLocaleString()}
                      </span>
                      <span className="ml-1.5 text-hud-textFaint">msgs</span>
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
