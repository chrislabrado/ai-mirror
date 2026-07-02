import { useEffect, useState } from "react";
import { Loader2, RefreshCw, Sparkles, TrendingUp } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { SyntheticTag, TrajectorySparklines } from "@/components/TrajectorySparklines";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ABSTRACTION_METRIC,
  type TemporalEpoch,
  type TrajectoryMetric,
} from "@/types/api";

type Busy = null | "refresh" | "synthesize";

export function TrajectoriesPage() {
  const [trajectories, setTrajectories] = useState<TrajectoryMetric[]>([]);
  const [epochs, setEpochs] = useState<TemporalEpoch[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const load = async () => {
    const [traj, eps] = await Promise.allSettled([api.listTrajectories(), api.temporalEpochs()]);
    setTrajectories(traj.status === "fulfilled" ? traj.value : []);
    setEpochs(eps.status === "fulfilled" ? eps.value : []);
  };

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  const runRefresh = async () => {
    setBusy("refresh");
    setError(null);
    setStatus(null);
    try {
      const r = await api.temporalRefresh();
      setStatus(
        `Refreshed: ${r.epochs_profiled}/${r.epochs_total} epochs profiled in ${r.duration_seconds.toFixed(1)}s`,
      );
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Temporal refresh failed.");
    } finally {
      setBusy(null);
    }
  };

  const runSynthesize = async () => {
    setBusy("synthesize");
    setError(null);
    setStatus(null);
    try {
      await api.synthesizeTrajectories();
      await load();
      setStatus("Trajectories synthesized.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Trajectory synthesis failed.");
    } finally {
      setBusy(null);
    }
  };

  const abstraction = trajectories.find((t) => t.metric === ABSTRACTION_METRIC) ?? null;
  const metrics = trajectories.filter((t) => t.metric !== ABSTRACTION_METRIC);

  return (
    <div className="space-y-8">
      {/* Page heading + actions */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Temporal Model · Observed vs Synthetic
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Trajectories
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={runRefresh}
            disabled={busy !== null}
            className="gap-1.5 font-mono"
          >
            {busy === "refresh" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={runSynthesize}
            disabled={busy !== null}
            className="gap-1.5 font-mono"
          >
            {busy === "synthesize" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Synthesize
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}
      {status && (
        <div className="rounded-md border border-hud-glow/30 bg-hud-glow/5 px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.18em] text-hud-glow">
          {status}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-hud-glow" />
        </div>
      )}

      {!loading && (
        <>
          {/* Sparkline grid (shared with Dashboard) */}
          <Card>
            <CardHeader className="flex flex-row items-center gap-2">
              <TrendingUp className="h-4 w-4 text-hud-glow" />
              <CardTitle>Metric Trajectories</CardTitle>
            </CardHeader>
            <CardContent>
              {metrics.length === 0 ? (
                <p className="py-6 text-center font-mono text-[12px] uppercase tracking-[0.2em] text-hud-textFaint">
                  No temporal data — run Refresh, then Synthesize
                </p>
              ) : (
                <TrajectorySparklines metrics={metrics} />
              )}
            </CardContent>
          </Card>

          {/* Abstraction narrative */}
          {abstraction && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Abstraction</CardTitle>
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-hud-textFaint">
                  {abstraction.model_used ?? "model unknown"}
                </span>
              </CardHeader>
              <CardContent className="space-y-4">
                {abstraction.narrative ? (
                  <div className="prose-hud text-[13px]">
                    <ReactMarkdown>{abstraction.narrative}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="font-mono text-[12px] uppercase tracking-[0.2em] text-hud-textFaint">
                    No narrative synthesized.
                  </p>
                )}
                {abstraction.assumptions && abstraction.assumptions.length > 0 && (
                  <div className="rounded-md border border-hud-warn/25 bg-hud-warn/[0.03] px-4 py-3">
                    <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-hud-warn">
                      Assumptions
                    </div>
                    <ul className="mt-2 space-y-1.5">
                      {abstraction.assumptions.map((a, i) => (
                        <li key={i} className="flex items-start gap-2 text-[12.5px] text-hud-textDim">
                          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-hud-warn/70" />
                          {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Epoch table */}
          <EpochTable epochs={epochs} trajectories={metrics} />
        </>
      )}
    </div>
  );
}

// ── Epoch table ────────────────────────────────────────────────────────────────

const COLUMNS = [
  "Epoch",
  "Convs",
  "Msgs",
  "Q-Ratio",
  "Avg Chars",
  "Sophistication",
  "Delegation",
  "Valence",
  "Themes",
] as const;

/** Column keys extrapolated metrics can map onto (tolerant name match). */
type SyntheticCol = "convs" | "msgs" | "qratio" | "avgchars" | "sophistication" | "delegation" | "valence";

function metricColumn(metric: string): SyntheticCol | null {
  const m = metric.toLowerCase();
  if (m.includes("conversation")) return "convs";
  if (m.includes("message") || m === "msgs") return "msgs";
  if (m.includes("question")) return "qratio";
  if (m.includes("char")) return "avgchars";
  if (m.includes("sophistication")) return "sophistication";
  if (m.includes("delegation")) return "delegation";
  if (m.includes("valence")) return "valence";
  return null;
}

function fmtCell(v: number | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString();
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(2);
}

function EpochTable({
  epochs,
  trajectories,
}: {
  epochs: TemporalEpoch[];
  trajectories: TrajectoryMetric[];
}) {
  // Extrapolated future epochs come from the trajectory series — epochs the
  // temporal model never observed. Rendered as clearly-marked SYNTHETIC rows.
  const observedEpochs = new Set(epochs.map((e) => e.epoch));
  const synthetic = new Map<string, Partial<Record<SyntheticCol, number>>>();
  for (const t of trajectories) {
    const col = metricColumn(t.metric);
    if (!col) continue;
    for (const p of t.series) {
      if (p.kind !== "extrapolated" || observedEpochs.has(p.epoch)) continue;
      const row = synthetic.get(p.epoch) ?? {};
      row[col] = p.value;
      synthetic.set(p.epoch, row);
    }
  }
  const syntheticRows = [...synthetic.entries()].sort(([a], [b]) => a.localeCompare(b));

  if (epochs.length === 0 && syntheticRows.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Epochs</CardTitle>
      </CardHeader>
      <CardContent className="px-0 pb-0 pt-0">
        <div className="overflow-x-auto pb-2">
          <table className="w-full">
            <thead>
              <tr className="border-b border-hud-line/60">
                {COLUMNS.map((c, i) => (
                  <th
                    key={c}
                    className={cn(
                      "py-3 text-left font-display text-[10px] uppercase tracking-[0.18em] text-hud-textFaint",
                      i === 0 ? "px-6" : "px-4",
                    )}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {epochs.map((e) => (
                <tr key={e.epoch} className="border-b border-hud-line/40">
                  <td className="px-6 py-3 font-mono text-[12px] text-hud-text">{e.epoch}</td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.stats.conversations)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.stats.messages)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.stats.question_ratio)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.stats.avg_user_msg_chars)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.profile?.sophistication)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.profile?.delegation)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-textDim">
                    {fmtCell(e.profile?.valence)}
                  </td>
                  <td className="px-4 py-3">
                    {e.profile && e.profile.themes.length > 0 ? (
                      <div className="flex max-w-[320px] flex-wrap gap-1">
                        {e.profile.themes.slice(0, 5).map((t) => (
                          <span
                            key={t}
                            className="rounded-sm border border-hud-glow/30 bg-hud-glow/5 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-hud-accent"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="font-mono text-[11px] text-hud-textFaint">—</span>
                    )}
                  </td>
                </tr>
              ))}

              {syntheticRows.map(([epoch, row]) => (
                <tr
                  key={epoch}
                  className="border-b border-dashed border-hud-warn/40 bg-hud-warn/[0.04]"
                >
                  <td className="px-6 py-3">
                    <span className="flex items-center gap-2 font-mono text-[12px] text-hud-warn">
                      {epoch}
                      <SyntheticTag />
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.convs)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.msgs)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.qratio)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.avgchars)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.sophistication)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.delegation)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] tabular-nums text-hud-warn/80">
                    {fmtCell(row.valence)}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-hud-warn/60">extrapolated</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {syntheticRows.length > 0 && (
          <div className="border-t border-hud-line/40 px-6 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-hud-textFaint">
            Amber dashed rows are model extrapolations, not observed data.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
