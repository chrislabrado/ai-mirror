import { useFable } from "@/lib/fable";
import { cn } from "@/lib/utils";

/**
 * HUD switch for Fable model routing. Persisted in localStorage
 * (`ai-mirror.fable`); every report / focus-lens / temporal POST reads it.
 */
export function FableToggle({ className }: { className?: string }) {
  const [fable, setFable] = useFable();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={fable}
      aria-label="Toggle Fable model routing"
      onClick={() => setFable(!fable)}
      className={cn(
        "group flex items-center gap-2.5 rounded-md border px-2.5 py-1 transition-all duration-200",
        fable
          ? "border-hud-glow/60 bg-hud-glow/5 shadow-glowSoft"
          : "border-hud-line bg-transparent hover:border-hud-glow/40",
        className,
      )}
    >
      <span
        className={cn(
          "font-display text-[10px] uppercase tracking-[0.3em] transition-colors",
          fable ? "text-hud-glow" : "text-hud-textFaint group-hover:text-hud-textDim",
        )}
      >
        Fable
      </span>
      <span
        className={cn(
          "relative h-3.5 w-7 rounded-full border transition-colors duration-200",
          fable ? "border-hud-glow/70 bg-hud-glow/15" : "border-hud-line bg-hud-panel/60",
        )}
      >
        <span
          className={cn(
            "absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full transition-all duration-200",
            fable
              ? "left-[calc(100%-0.625rem)] bg-hud-glow shadow-[0_0_8px_#00ffc8]"
              : "left-0.5 bg-hud-textFaint",
          )}
        />
      </span>
    </button>
  );
}
