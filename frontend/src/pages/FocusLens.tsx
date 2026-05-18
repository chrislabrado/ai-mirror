import { useState } from "react";
import { Loader2, Telescope } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { FocusLensResponse } from "@/types/api";

export function FocusLensPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<FocusLensResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 3) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.focusLens({ query });
      setResult(r);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Focus Lens query failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
          Section 6.3 · Selective Natural-Language Analysis
        </div>
        <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
          Focus Lens
        </h1>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <Telescope className="h-4 w-4 text-hud-glow" />
          <CardTitle>Targeted Query</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. How has my thinking about systems design changed since January?"
              rows={3}
              className="resize-none rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3 font-mono text-[13px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="neon-btn self-start rounded-md px-5 py-2.5 font-display text-[12px] uppercase tracking-[0.22em] disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Engage Focus Lens"}
            </button>
          </form>
          {error && <div className="mt-3 text-sm text-hud-warn">{error}</div>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>{result.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="text-[14px] leading-relaxed text-hud-text">{result.summary}</p>
            {result.blocks.map((b) => (
              <div key={b.id} className="prose-hud">
                <ReactMarkdown>{b.body_markdown}</ReactMarkdown>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
