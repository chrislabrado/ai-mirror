import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { ReportListItem } from "@/types/api";

const LIMIT = 50;

const KIND_OPTIONS = [
  { value: "", label: "All" },
  { value: "full_mirror", label: "Full Mirror" },
  { value: "advanced_abstract", label: "Advanced Abstract" },
  { value: "focus_lens", label: "Focus Lens" },
] as const;

function kindBadgeClass(kind: string): string {
  switch (kind) {
    case "full_mirror":
      return "border-hud-glow/60 text-hud-glow bg-hud-glow/8";
    case "advanced_abstract":
      return "border-hud-glow2/60 text-hud-glow2 bg-hud-glow2/8";
    case "focus_lens":
      return "border-hud-warn/60 text-hud-warn bg-hud-warn/8";
    default:
      return "border-hud-line text-hud-textDim";
  }
}

function kindLabel(kind: string): string {
  switch (kind) {
    case "full_mirror":
      return "Full Mirror";
    case "advanced_abstract":
      return "Adv. Abstract";
    case "focus_lens":
      return "Focus Lens";
    default:
      return kind;
  }
}

export function ReportsListPage() {
  const navigate = useNavigate();
  const [kindFilter, setKindFilter] = useState("");
  const [items, setItems] = useState<ReportListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset pagination when filter changes
  useEffect(() => {
    setOffset(0);
  }, [kindFilter]);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listReports({
        kind: kindFilter || undefined,
        limit: LIMIT,
        offset,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }, [kindFilter, offset]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + LIMIT, total);
  const canPrev = offset > 0;
  const canNext = offset + LIMIT < total;

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Section 6.4 · Insights Hub
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Reports
          </h1>
        </div>
        <Link
          to="/insights"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textDim hover:text-hud-glow transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Insights
        </Link>
      </div>

      {/* Filter row */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
              Kind
            </span>
            <select
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              className="h-8 appearance-none rounded-md border border-hud-line bg-hud-panel/40 px-3 font-mono text-[12px] text-hud-text focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors cursor-pointer"
            >
              {KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>All Reports</CardTitle>
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
                    Kind
                  </th>
                  <th className="px-4 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
                    Model
                  </th>
                </tr>
              </thead>
              <tbody>
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-16 text-center">
                      <p className="font-mono text-[13px] text-hud-textDim">
                        No reports found. Run an analysis to generate reports.
                      </p>
                    </td>
                  </tr>
                )}
                {items.map((item, idx) => (
                  <ReportRow
                    key={item.id}
                    item={item}
                    isLast={idx === items.length - 1}
                    onClick={() => navigate(`/insights/reports/${item.id}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
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

// ── Row ────────────────────────────────────────────────────────────────────────

interface ReportRowProps {
  item: ReportListItem;
  isLast: boolean;
  onClick: () => void;
}

function ReportRow({ item, isLast, onClick }: ReportRowProps) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "cursor-pointer transition-colors duration-150 hover:bg-hud-glow/5",
        !isLast && "border-b border-hud-line/40",
      )}
    >
      <td className="px-6 py-3.5">
        <span
          className={cn(
            "inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em]",
            kindBadgeClass(item.kind),
          )}
        >
          {kindLabel(item.kind)}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <Link
          to={`/insights/reports/${item.id}`}
          onClick={(e) => e.stopPropagation()}
          className="flex items-center gap-2 font-sans text-[13px] text-hud-text hover:text-hud-glow transition-colors"
        >
          <FileText className="h-3.5 w-3.5 shrink-0 text-hud-textFaint" />
          {item.title}
        </Link>
      </td>
      <td className="px-4 py-3.5 font-mono text-[11px] text-hud-textFaint">
        {fmtDate(item.created_at)}
      </td>
      <td className="px-6 py-3.5 font-mono text-[11px] text-hud-textFaint">
        {item.model_used ?? "—"}
      </td>
    </tr>
  );
}
