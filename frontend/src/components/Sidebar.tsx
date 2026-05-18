import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Compass,
  Download,
  LayoutDashboard,
  MessagesSquare,
  Network,
  Telescope,
} from "lucide-react";
import { cn } from "@/lib/utils";

type NavItemDef = {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
};

// Order per spec §6.1
const NAV: NavItemDef[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/history", label: "History", icon: MessagesSquare },
  { to: "/insights", label: "Insights", icon: BarChart3 },
  { to: "/graph", label: "Knowledge Graph", icon: Network },
  { to: "/queries", label: "Queries", icon: Compass },
  { to: "/focus-lens", label: "Focus Lens", icon: Telescope },
  { to: "/export-guide", label: "Export Guide", icon: Download },
];

export function Sidebar() {
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-20 flex h-screen w-[232px] flex-col",
        "border-r border-hud-line bg-hud-deep/80 backdrop-blur-md",
      )}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-6 pt-7 pb-6">
        <div className="relative">
          <div className="h-9 w-9 rounded-md border border-hud-glow/60 bg-hud-panel shadow-glowSoft" />
          <div className="absolute inset-1 rounded-sm border border-hud-glow/40" />
          <div className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-hud-glow shadow-[0_0_8px_#00ffc8]" />
        </div>
        <div>
          <div className="font-display text-[15px] uppercase tracking-[0.22em] text-hud-text">
            AI Mirror
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
            v1.1 / kernel
          </div>
        </div>
      </div>

      <div className="mx-5 mb-4 h-px bg-gradient-to-r from-transparent via-hud-glow/30 to-transparent" />

      <nav className="flex-1 space-y-1 px-3">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn("nav-item font-display text-[12.5px] uppercase tracking-[0.18em]", {
                "is-active": isActive,
              })
            }
          >
            <item.icon className="h-4 w-4" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-6 pb-6 pt-3">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
          local · private · offline
        </div>
      </div>
    </aside>
  );
}
