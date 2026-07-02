import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Compass,
  Globe2,
  MessagesSquare,
  RefreshCw,
  Search,
  Telescope,
  TrendingUp,
  UploadCloud,
} from "lucide-react";

import { ActionButton } from "@/components/ActionButton";
import { HoloPanel } from "@/components/HoloPanel";
import { IngestDropzone } from "@/components/IngestDropzone";
import { RemotePullControl } from "@/components/RemotePullControl";
import { ReportResultModal } from "@/components/ReportResultModal";
import { TrajectorySparklines } from "@/components/TrajectorySparklines";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import type { DashboardSummary, ReportResponse, TrajectoryMetric } from "@/types/api";

type Loading = null | "full" | "abstract" | "meta" | "refresh";

export function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [loading, setLoading] = useState<Loading>(null);
  const [resultReport, setResultReport] = useState<ReportResponse | null>(null);
  const [resultDownloadable, setResultDownloadable] = useState(false);
  const [trajectories, setTrajectories] = useState<TrajectoryMetric[]>([]);
  const [lastReportPlaceholder, setLastReportPlaceholder] = useState(false);

  const refresh = async () => {
    try {
      setError(null);
      const data = await api.dashboardSummary();
      setSummary(data);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to reach backend.");
    }
    // Honesty check: if the latest report ran without a model, its bullets are
    // placeholder text, not insight — tag it as such.
    try {
      const reports = await api.listReports({ limit: 1 });
      setLastReportPlaceholder(reports.items.length > 0 && reports.items[0].model_used === null);
    } catch {
      setLastReportPlaceholder(false);
    }
  };

  const loadTrajectories = async () => {
    try {
      setTrajectories(await api.listTrajectories());
    } catch {
      // No temporal data yet — the panel shows its empty state.
      setTrajectories([]);
    }
  };

  useEffect(() => {
    refresh();
    loadTrajectories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runFullMirror = async () => {
    setLoading("full");
    try {
      const report = await api.fullMirror();
      setResultReport(report);
      setResultDownloadable(true);
      // Auto-trigger the .md download — this is the original spec
      // deliverable. The modal stays open so the user can also read it
      // on-screen.
      try {
        await api.downloadReportMarkdown(report.report_id);
      } catch (exc) {
        // Download failure is non-fatal; the modal still renders.
        console.error("Markdown download failed", exc);
      }
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Full Mirror run failed.");
    } finally {
      setLoading(null);
    }
  };

  const runAdvancedAbstract = async () => {
    setLoading("abstract");
    try {
      const report = await api.advancedAbstract();
      setResultReport(report);
      setResultDownloadable(false);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Advanced Abstract run failed.");
    } finally {
      setLoading(null);
    }
  };

  const runMetaAnalysis = async () => {
    setLoading("meta");
    setMetaError(null);
    try {
      const report = await api.metaAnalysis();
      navigate(`/insights/reports/${report.report_id}`);
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 400) {
        // Typically "needs at least two prior runs to compare".
        setMetaError(exc.detail || "Meta-analysis needs at least two prior report runs to compare.");
      } else {
        setError(exc instanceof Error ? exc.message : "Meta-Analysis run failed.");
      }
    } finally {
      setLoading(null);
    }
  };

  const handleManualDownload = async () => {
    if (!resultReport) return;
    try {
      await api.downloadReportMarkdown(resultReport.report_id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Download failed.");
    }
  };

  const refreshInsights = async () => {
    setLoading("refresh");
    try {
      await api.temporalRefresh();
      await api.synthesizeTrajectories();
      await loadTrajectories();
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Insight refresh failed.");
    } finally {
      setLoading(null);
    }
  };

  const totals = summary && (
    <div className="grid grid-cols-3 gap-4 font-mono text-[11px] uppercase tracking-[0.22em] text-hud-textDim">
      <Stat label="Conversations" value={summary.total_conversations} />
      <Stat label="Messages" value={summary.total_messages} />
      <Stat label="Sources" value={summary.sources.length} />
    </div>
  );

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div className="flex items-end justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
            Codified Self-Reflection · Local · Private
          </div>
          <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
            Dashboard
          </h1>
        </div>
        {totals}
      </div>

      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {/* Top-right holographic LAST MIRROR RUN panel + gauges */}
      <HoloPanel
        lastRunAt={summary?.last_run_at ?? null}
        bullets={summary?.bullets ?? []}
        gauges={summary?.gauges ?? null}
        notAnalyzed={lastReportPlaceholder}
      />

      {/* Spec §6.1: large neon-bordered action buttons in a row (now six) */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <ActionButton
          icon={Search}
          title="Full Mirror Analysis"
          subtitle="Comprehensive report"
          loading={loading === "full"}
          onClick={runFullMirror}
        />
        <ActionButton
          icon={Globe2}
          title="Advanced Abstract"
          subtitle="Meta-pattern synthesis"
          loading={loading === "abstract"}
          onClick={runAdvancedAbstract}
        />
        <ActionButton
          icon={Compass}
          title="Meta-Analysis"
          subtitle="Compare prior runs"
          loading={loading === "meta"}
          onClick={runMetaAnalysis}
        />
        <ActionButton
          icon={MessagesSquare}
          title="Talk to My History"
          subtitle="Persistent GraphRAG chat"
          onClick={() => navigate("/queries")}
        />
        <ActionButton
          icon={Telescope}
          title="Focus Lens"
          subtitle="Targeted inquiry"
          onClick={() => navigate("/focus-lens")}
        />
        <ActionButton
          icon={RefreshCw}
          title="Refresh Insights"
          subtitle="Rebuild temporal model"
          loading={loading === "refresh"}
          onClick={refreshInsights}
        />
      </div>

      {/* Meta-analysis precondition failure — readable, not a stack trace */}
      {metaError && (
        <div className="rounded-md border border-hud-warn/40 bg-hud-warn/5 px-4 py-3 font-mono text-[12px] text-hud-warn">
          Meta-Analysis unavailable: {metaError}
        </div>
      )}

      {/* Temporal trajectories — observed solid, extrapolated dashed + SYNTHETIC */}
      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <TrendingUp className="h-4 w-4 text-hud-glow" />
          <CardTitle>Trajectories</CardTitle>
        </CardHeader>
        <CardContent>
          {trajectories.length === 0 ? (
            <p className="py-6 text-center font-mono text-[12px] uppercase tracking-[0.2em] text-hud-textFaint">
              No temporal data — run Refresh Insights
            </p>
          ) : (
            <TrajectorySparklines metrics={trajectories} maxMetrics={6} />
          )}
        </CardContent>
      </Card>

      {/* Ingest dropzone + local connector pull */}
      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <UploadCloud className="h-4 w-4 text-hud-glow" />
          <CardTitle>Ingest Conversations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
            <IngestDropzone onIngestComplete={refresh} />
            <RemotePullControl onComplete={refresh} />
          </div>
        </CardContent>
      </Card>

      {/* Result modal — opens automatically after Full Mirror / Advanced Abstract.
          Full Mirror runs also auto-trigger a .md download alongside. */}
      <ReportResultModal
        open={resultReport !== null}
        onOpenChange={(next) => {
          if (!next) setResultReport(null);
        }}
        report={resultReport}
        downloadable={resultDownloadable}
        onDownload={resultDownloadable ? handleManualDownload : undefined}
      />

      {/* Source breakdown */}
      {summary && summary.sources.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <Compass className="h-4 w-4 text-hud-glow" />
            <CardTitle>Ingested Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              {summary.sources.map((s) => (
                <div
                  key={s.slug}
                  className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3"
                >
                  <div className="font-display text-[11px] uppercase tracking-[0.2em] text-hud-textDim">
                    {s.name}
                  </div>
                  <div className="mt-1 font-mono text-lg text-hud-glow">
                    {s.conversations}
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-hud-textFaint">
                    conversations
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3 text-right">
      <div className="text-[10px] tracking-[0.25em] text-hud-textFaint">{label}</div>
      <div className="mt-1 font-display text-base normal-case text-hud-text">
        {value.toLocaleString()}
      </div>
    </div>
  );
}
