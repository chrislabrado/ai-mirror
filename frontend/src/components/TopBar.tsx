import { useEffect, useState } from "react";
import { Circle } from "lucide-react";
import { FableToggle } from "@/components/FableToggle";
import { api } from "@/lib/api";

export function TopBar() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        const h = await api.health();
        if (!alive) return;
        setOnline(true);
        setVersion(h.version);
      } catch {
        if (!alive) return;
        setOnline(false);
      }
    };
    ping();
    const t = setInterval(ping, 15_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const colour = online == null ? "text-hud-textFaint" : online ? "text-hud-glow" : "text-hud-warn";
  const label = online == null ? "CONNECTING" : online ? "ONLINE" : "OFFLINE";

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-hud-line/60 bg-hud-deep/60 px-8 backdrop-blur-md">
      <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-hud-textFaint">
        {new Date().toLocaleDateString(undefined, {
          weekday: "short",
          year: "numeric",
          month: "short",
          day: "2-digit",
        })}
      </div>
      <div className="flex items-center gap-5">
        <FableToggle />
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.3em]">
          <Circle className={`h-2 w-2 fill-current ${colour}`} />
          <span className={colour}>{label}</span>
          {version && <span className="text-hud-textFaint">· kernel {version}</span>}
        </div>
      </div>
    </header>
  );
}
