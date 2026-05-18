import { Outlet } from "react-router-dom";
import { DataGridOverlay } from "@/components/DataGridOverlay";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";

export function Layout() {
  return (
    <div className="min-h-screen text-hud-text">
      <DataGridOverlay />
      <Sidebar />
      <div className="relative z-10 ml-[232px]">
        <TopBar />
        {/* Spec §1: generous 32 px padding, calm breathing room, perfect symmetry */}
        <main className="px-8 py-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
