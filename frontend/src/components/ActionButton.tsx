import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionButtonProps {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  loading?: boolean;
  onClick?: () => void;
  className?: string;
}

/** Large neon-bordered HUD action button (spec §6.1 — five across the dashboard). */
export function ActionButton({
  icon: Icon,
  title,
  subtitle,
  loading,
  onClick,
  className,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={cn(
        "neon-btn group relative flex h-full min-h-[150px] flex-col items-center justify-center gap-3 rounded-lg px-5 py-6 text-center",
        "disabled:cursor-wait",
        // Active analyses get a pulsing teal border + brighter background so it
        // is impossible to confuse "nothing happened" with "request in flight".
        loading &&
          "animate-pulse-glow !border-hud-glow !bg-hud-glow/10 !shadow-[0_0_28px_rgba(0,255,200,0.35)]",
        className,
      )}
    >
      {/* corner accents */}
      <span className="pointer-events-none absolute left-1.5 top-1.5 h-2.5 w-2.5 border-l border-t border-hud-glow/70" />
      <span className="pointer-events-none absolute right-1.5 top-1.5 h-2.5 w-2.5 border-r border-t border-hud-glow/70" />
      <span className="pointer-events-none absolute left-1.5 bottom-1.5 h-2.5 w-2.5 border-l border-b border-hud-glow/70" />
      <span className="pointer-events-none absolute right-1.5 bottom-1.5 h-2.5 w-2.5 border-r border-b border-hud-glow/70" />

      <div
        className={cn(
          "grid h-12 w-12 place-items-center rounded-md border bg-hud-panel/70 transition-all",
          loading
            ? "border-hud-glow shadow-glow"
            : "border-hud-glow/40 shadow-glowSoft group-hover:border-hud-glow group-hover:shadow-glow",
        )}
      >
        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-hud-glow" />
        ) : (
          <Icon className="h-5 w-5 text-hud-glow" />
        )}
      </div>
      <div className="space-y-1">
        <div className="font-display text-[12.5px] uppercase tracking-[0.22em] text-hud-text">
          {title}
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
          {loading ? "Running… (~1-2 min)" : subtitle}
        </div>
      </div>
    </button>
  );
}
