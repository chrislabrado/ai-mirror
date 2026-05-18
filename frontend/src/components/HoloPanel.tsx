import { Activity } from "lucide-react";
import { SpeedometerGauge } from "@/components/SpeedometerGauge";
import { Card } from "@/components/ui/card";
import { fmtDate } from "@/lib/utils";
import type { GaugeSet } from "@/types/api";

interface HoloPanelProps {
  lastRunAt: string | null;
  bullets: string[];
  gauges: GaugeSet | null;
}

/** Top-right holographic LAST MIRROR RUN panel + three semi-circular gauges. */
export function HoloPanel({ lastRunAt, bullets, gauges }: HoloPanelProps) {
  const safeBullets = (bullets ?? []).slice(0, 5);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-hud-line/60 px-7 py-4">
        <div className="flex items-center gap-3">
          <Activity className="h-4 w-4 text-hud-glow" />
          <span className="font-display text-[11px] uppercase tracking-[0.32em] text-hud-textDim">
            Last Mirror Run
          </span>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
          {fmtDate(lastRunAt)}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 px-8 py-7 lg:grid-cols-[1fr_auto]">
        <ul className="space-y-2.5">
          {safeBullets.length === 0 ? (
            <li className="font-mono text-[12px] uppercase tracking-[0.2em] text-hud-textFaint">
              No analysis yet. Ingest a conversation export to begin.
            </li>
          ) : (
            safeBullets.map((b, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-hud-glow shadow-[0_0_8px_#00ffc8]" />
                <span className="text-[14px] leading-relaxed text-hud-text">{b}</span>
              </li>
            ))
          )}
        </ul>

        <div className="grid grid-cols-3 items-end gap-5">
          <SpeedometerGauge label="Thought Clarity" value={gauges?.thought_clarity ?? null} />
          <SpeedometerGauge
            label="Self-Reflection Depth"
            value={gauges?.self_reflection_depth ?? null}
          />
          <SpeedometerGauge label="Aptitude Balance" value={gauges?.aptitude_balance ?? null} />
        </div>
      </div>
    </Card>
  );
}
