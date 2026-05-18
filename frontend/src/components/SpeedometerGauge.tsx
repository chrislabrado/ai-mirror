import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface SpeedometerGaugeProps {
  label: string;
  /** Value in [0, 1] */
  value: number | null;
  size?: number;
  className?: string;
}

/**
 * Semi-circular SVG gauge with neon-teal sweep, tick marks, and animated needle.
 * Spec §6.1: three gauges — Thought Clarity, Self-Reflection Depth, Aptitude Balance.
 */
export function SpeedometerGauge({ label, value, size = 168, className }: SpeedometerGaugeProps) {
  const [animated, setAnimated] = useState(0);
  const target = value == null ? 0 : Math.min(1, Math.max(0, value));

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const from = animated;
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimated(from + (target - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  // Geometry: upper-semicircle gauge.
  // Pivot is `cy`; the arc curves UP through (cx, cy - r).
  // In SVG the y-axis points DOWN, so we subtract sin(angle) instead of
  // adding it — that way frac=0 sits at (cx-r, cy), frac=0.5 sits at
  // (cx, cy-r), frac=1 sits at (cx+r, cy).
  const cx = size / 2;
  const cy = size * 0.78; // pivot near the bottom so the smile-arc fits the viewBox
  const r = size * 0.42;
  const start = Math.PI; // 180°
  const end = 0; // 0°
  const angle = start + (end - start) * animated;
  const needleX = cx + Math.cos(angle) * (r - 8);
  const needleY = cy - Math.sin(angle) * (r - 8);

  const arc = (frac: number) => {
    const a = start + (end - start) * frac;
    return { x: cx + Math.cos(a) * r, y: cy - Math.sin(a) * r };
  };
  const sweepEnd = arc(animated);
  const fullEnd = arc(1);

  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = start + (end - start) * (i / 10);
    const r1 = r + 2;
    const r2 = r + 10;
    return {
      x1: cx + Math.cos(a) * r1,
      y1: cy - Math.sin(a) * r1,
      x2: cx + Math.cos(a) * r2,
      y2: cy - Math.sin(a) * r2,
      strong: i % 5 === 0,
    };
  });

  const display = value == null ? "—" : Math.round(animated * 100).toString();

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <svg width={size} height={size * 0.88} viewBox={`0 0 ${size} ${size * 0.88}`}>
        <defs>
          <linearGradient id={`gradient-${label}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#00e5ff" />
            <stop offset="60%" stopColor="#14f1d9" />
            <stop offset="100%" stopColor="#00ffc8" />
          </linearGradient>
          <filter id={`glow-${label}`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Track. Sweep flag 0 makes the arc curve up (counter-clockwise in SVG). */}
        <path
          d={`M ${arc(0).x} ${arc(0).y} A ${r} ${r} 0 0 0 ${fullEnd.x} ${fullEnd.y}`}
          stroke="rgba(20,241,217,0.12)"
          strokeWidth={6}
          fill="none"
          strokeLinecap="round"
        />
        {/* Sweep — filled portion up to the current value. */}
        <path
          d={`M ${arc(0).x} ${arc(0).y} A ${r} ${r} 0 0 0 ${sweepEnd.x} ${sweepEnd.y}`}
          stroke={`url(#gradient-${label})`}
          strokeWidth={6}
          fill="none"
          strokeLinecap="round"
          filter={`url(#glow-${label})`}
        />
        {/* Tick marks */}
        {ticks.map((t, i) => (
          <line
            key={i}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke={t.strong ? "#14f1d9" : "rgba(20,241,217,0.35)"}
            strokeWidth={t.strong ? 1.4 : 0.8}
          />
        ))}
        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke="#dff5ff"
          strokeWidth={1.6}
          strokeLinecap="round"
          filter={`url(#glow-${label})`}
        />
        <circle cx={cx} cy={cy} r={4.5} fill="#00ffc8" filter={`url(#glow-${label})`} />
        <circle cx={cx} cy={cy} r={1.8} fill="#03070f" />

        {/* Value sits centred inside the upper arc. */}
        <text
          x={cx}
          y={cy - size * 0.18}
          textAnchor="middle"
          className="font-display fill-hud-text"
          style={{ fontSize: size * 0.16, letterSpacing: "0.04em" }}
        >
          {display}
        </text>
      </svg>
      <div className="mt-1 text-center">
        <div className="font-display text-[10.5px] uppercase tracking-[0.22em] text-hud-textDim">
          {label}
        </div>
      </div>
    </div>
  );
}
