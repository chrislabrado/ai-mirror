import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  Loader2,
  RotateCcw,
  Search,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import type { ConversationListItem, SourceStat } from "@/types/api";

const LIMIT = 50;

export function HistoryPage() {
  const navigate = useNavigate();

  // Filter state
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");

  // Debounced query actually sent to API
  const [activeQ, setActiveQ] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Data state
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sources, setSources] = useState<SourceStat[]>([]);

  // Async state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load sources list once from dashboard summary for stable filter options
  useEffect(() => {
    api
      .dashboardSummary()
      .then((s) => setSources(s.sources.slice().sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => {
        // Non-fatal: fall back to sources derived from loaded items
      });
  }, []);

  // Debounce the search input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setActiveQ(q);
      setOffset(0);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q]);

  // Reset offset when source filter changes
  useEffect(() => {
    setOffset(0);
  }, [source]);

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listConversations({
        q: activeQ || undefined,
        source: source || undefined,
        limit: LIMIT,
        offset,
      });
      setItems(result.items);
      setTotal(result.total);

      // Supplement sources from results if dashboard call failed
      setSources((prev) => {
        if (prev.length > 0) return prev;
        const seen = new Map<string, SourceStat>();
        for (const item of result.items) {
          if (!seen.has(item.source_slug)) {
            seen.set(item.source_slug, {
              slug: item.source_slug,
              name: item.source_name,
              conversations: 0,
            });
          }
        }
        return Array.from(seen.values()).sort((a, b) => a.name.localeCompare(b.name));
      });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load conversations.");
    } finally {
      setLoading(false);
    }
  }, [activeQ, source, offset]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleReset = () => {
    setQ("");
    setActiveQ("");
    setSource("");
    setOffset(0);
  };

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + LIMIT, total);
  const canPrev = offset > 0;
  const canNext = offset + LIMIT < total;

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
          Section 6.4 · Conversation Browser
        </div>
        <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
          History
        </h1>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-5">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search input */}
            <div className="relative flex-1 min-w-[180px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-hud-textFaint" />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search titles..."
                className="h-9 w-full rounded-md border border-hud-line bg-hud-panel/40 pl-8 pr-3 font-mono text-[13px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors"
              />
            </div>

            {/* Source filter */}
            <div className="relative">
              <Filter className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-hud-textFaint" />
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="h-9 appearance-none rounded-md border border-hud-line bg-hud-panel/40 pl-8 pr-7 font-mono text-[13px] text-hud-text focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors cursor-pointer"
              >
                <option value="">All sources</option>
                {sources.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Reset */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              className="gap-1.5 font-mono"
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {/* Conversations table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Conversations</CardTitle>
            {loading && (
              <span className="flex items-center gap-1.5 font-mono text-[11px] text-hud-textFaint">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="px-0 pb-0 pt-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-hud-line/60">
                  <th className="px-6 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Source
                  </th>
                  <th className="px-4 py-3 text-right font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Messages
                  </th>
                  <th className="px-4 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Started
                  </th>
                  <th className="px-6 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody>
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-16 text-center">
                      <p className="font-mono text-[13px] text-hud-textDim">
                        No conversations match. Try a wider search, or ingest more data.
                      </p>
                    </td>
                  </tr>
                )}
                {items.map((item, idx) => (
                  <ConversationRow
                    key={item.id}
                    item={item}
                    isLast={idx === items.length - 1}
                    onClick={() => navigate(`/history/${item.id}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination footer */}
          {total > 0 && (
            <div className="flex items-center justify-between border-t border-hud-line/60 px-6 py-3">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-hud-textFaint">
                Showing {pageStart}–{pageEnd} of {total.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset((o) => o - LIMIT)}
                  disabled={!canPrev || loading}
                  className="gap-1 font-mono"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset((o) => o + LIMIT)}
                  disabled={!canNext || loading}
                  className="gap-1 font-mono"
                >
                  Next
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Row component ──────────────────────────────────────────────────────────────

interface ConversationRowProps {
  item: ConversationListItem;
  isLast: boolean;
  onClick: () => void;
}

function ConversationRow({ item, isLast, onClick }: ConversationRowProps) {
  return (
    <tr
      onClick={onClick}
      className={`cursor-pointer transition-colors duration-150 hover:bg-hud-glow/5 ${
        isLast ? "" : "border-b border-hud-line/40"
      }`}
    >
      <td className="px-6 py-3.5">
        <Link
          to={`/history/${item.id}`}
          onClick={(e) => e.stopPropagation()}
          className="font-sans text-[13px] text-hud-text hover:text-hud-glow transition-colors"
        >
          {item.title ?? "(untitled)"}
        </Link>
      </td>
      <td className="px-4 py-3.5">
        <span className="inline-flex items-center rounded-sm border border-hud-line bg-hud-panel/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-hud-textDim">
          {item.source_name}
        </span>
      </td>
      <td className="px-4 py-3.5 text-right font-mono text-[12px] text-hud-textDim">
        {item.message_count.toLocaleString()}
      </td>
      <td className="px-4 py-3.5 font-mono text-[11px] text-hud-textFaint">
        {fmtDate(item.started_at)}
      </td>
      <td className="px-6 py-3.5 font-mono text-[11px] text-hud-textFaint">
        {fmtDate(item.updated_at)}
      </td>
    </tr>
  );
}
