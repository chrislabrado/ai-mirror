import { ABSTRACTION_METRIC, type TrajectoryMetric, type TrajectoryPoint } from "@/types/api";
import { cn } from "@/lib/utils";

/**
 * Hand-rolled SVG sparkline grid for temporal trajectories.
 * Observed points: solid teal polyline. Extrapolated points: dashed amber
 * continuation with a translucent confidence band and a SYNTHETIC tag —
 * observed vs synthetic data must never be visually confusable.
 */

interface TrajectorySparklinesProps {
  metrics: TrajectoryMetric[];
  maxMetrics?: number;
  className?: string;
}

export function prettyMetricName(metric: string): string {
  return metric.replace(/_/g, " ").trim();
}

export function TrajectorySparklines({ metrics, maxMetrics, className }: TrajectorySparklinesProps) {
  const displayable = metrics
    .filter((m) => m.metric !== ABSTRACTION_METRIC && m.series.length > 0)
    .slice(0, maxMetrics ?? metrics.length);

  if (displayable.length === 0) return null;

  return (
    <div className={cn("grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3", className)}>
      {displayable.map((m) => (
        <SparklineCard key={m.metric} metric={m} />
      ))}
    </div>
  );
}

// ── Single metric card ─────────────────────────────────────────────────────────

function SparklineCard({ metric }: { metric: TrajectoryMetric }) {
  const series = metric.series;
  const hasSynthetic = series.some((p) => p.kind === "extrapolated");
  const lastObserved = [...series].reverse().find((p) => p.kind === "observed") ?? null;

  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 pb-3 pt-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-display text-[10.5px] uppercase tracking-[0.22em] text-hud-textDim">
          {prettyMetricName(metric.metric)}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {lastObserved && (
            <span className="font-mono text-[12px] tabular-nums text-hud-glow">
              {fmtValue(lastObserved.value)}
            </span>
          )}
          {hasSynthetic && <SyntheticTag />}
        </span>
      </div>
      <Sparkline series={series} className="mt-2" />
      <div className="mt-1 flex justify-between font-mono text-[9px] uppercase tracking-[0.14em] text-hud-textFaint">
        <span>{series[0].epoch}</span>
        <span>{series[series.length - 1].epoch}</span>
      </div>
    </div>
  );
}

export function SyntheticTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "rounded-sm border border-dashed border-hud-warn/60 bg-transparent px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.18em] text-hud-warn",
        className,
      )}
      title="Extrapolated by the model — not observed data"
    >
      Synthetic
    </span>
  );
}

function fmtValue(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString();
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(2);
}

// ── SVG sparkline ──────────────────────────────────────────────────────────────

const W = 260;
const H = 72;
const PAD = 6;

function Sparkline({ series, className }: { series: TrajectoryPoint[]; className?: string }) {
  // Y-scale over values AND confidence bounds so the band never clips.
  const values: number[] = [];
  for (const p of series) {
    if (Number.isFinite(p.value)) values.push(p.value);
    if (p.ci_low != null && Number.isFinite(p.ci_low)) values.push(p.ci_low);
    if (p.ci_high != null && Number.isFinite(p.ci_high)) values.push(p.ci_high);
  }
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    min = 0;
    max = 1;
  }
  if (max - min < 1e-9) {
    // Flat series — centre the line.
    min -= 1;
    max += 1;
  }

  const x = (i: number) =>
    series.length <= 1 ? W / 2 : PAD + (i / (series.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - ((v - min) / (max - min)) * (H - 2 * PAD);

  const observed: { i: number; p: TrajectoryPoint }[] = [];
  const extrapolated: { i: number; p: TrajectoryPoint }[] = [];
  series.forEach((p, i) => (p.kind === "observed" ? observed : extrapolated).push({ i, p }));

  const observedPts = observed.map(({ i, p }) => `${x(i)},${y(p.value)}`).join(" ");

  // The dashed line continues from the last observed point so there is no gap.
  const anchor = observed.length > 0 ? observed[observed.length - 1] : null;
  const extraLine = extrapolated.length > 0 ? (anchor ? [anchor, ...extrapolated] : extrapolated) : [];
  const extraPts = extraLine.map(({ i, p }) => `${x(i)},${y(p.value)}`).join(" ");

  // Confidence band across extrapolated points (anchored at the last observed value).
  const banded = extrapolated.filter(({ p }) => p.ci_low != null && p.ci_high != null);
  let bandPath = "";
  if (banded.length > 0) {
    const upper = banded.map(({ i, p }) => `${x(i)},${y(p.ci_high as number)}`);
    const lower = [...banded].reverse().map(({ i, p }) => `${x(i)},${y(p.ci_low as number)}`);
    const anchorPt = anchor ? [`${x(anchor.i)},${y(anchor.p.value)}`] : [];
    bandPath = `M ${[...anchorPt, ...upper, ...lower, ...anchorPt].join(" L ")} Z`;
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={cn("h-[72px] w-full", className)}
      preserveAspectRatio="none"
      role="img"
      aria-label="Trajectory sparkline"
    >
      {/* Confidence band — translucent warn tint under the synthetic segment */}
      {bandPath && <path d={bandPath} fill="rgba(255,181,71,0.12)" stroke="none" />}

      {/* Observed — solid teal */}
      {observed.length > 1 && (
        <polyline
          points={observedPts}
          fill="none"
          stroke="#14f1d9"
          strokeWidth={1.6}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}
      {observed.map(({ i, p }) => (
        <circle key={`o-${i}`} cx={x(i)} cy={y(p.value)} r={1.8} fill="#00ffc8" />
      ))}

      {/* Extrapolated — dashed amber continuation */}
      {extraLine.length > 1 && (
        <polyline
          points={extraPts}
          fill="none"
          stroke="#ffb547"
          strokeWidth={1.4}
          strokeDasharray="4 3"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}
      {extrapolated.map(({ i, p }) => (
        <circle
          key={`e-${i}`}
          cx={x(i)}
          cy={y(p.value)}
          r={1.8}
          fill="none"
          stroke="#ffb547"
          strokeWidth={1}
        />
      ))}
    </svg>
  );
}
