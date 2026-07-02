import { useState } from "react";
import { HardDriveDownload, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { IngestResponse } from "@/types/api";

const CONNECTORS = [
  { value: "claude_code", label: "Claude Code" },
  { value: "openclaw", label: "OpenClaw" },
] as const;

type Connector = (typeof CONNECTORS)[number]["value"];

interface RemotePullControlProps {
  onComplete?: () => void;
}

/** Compact control that pulls conversations straight off local connectors. */
export function RemotePullControl({ onComplete }: RemotePullControlProps) {
  const [connector, setConnector] = useState<Connector>("claude_code");
  const [limit, setLimit] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pull = async () => {
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const parsedLimit = limit.trim() === "" ? undefined : parseInt(limit, 10);
      const resp = await api.ingestRemote({
        connector,
        limit: parsedLimit !== undefined && Number.isFinite(parsedLimit) ? parsedLimit : undefined,
      });
      setResult(resp);
      onComplete?.();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Remote pull failed.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border border-hud-line bg-hud-panel/30 px-4 py-4">
      <div className="flex items-center gap-2">
        <HardDriveDownload className="h-4 w-4 text-hud-glow" />
        <span className="font-display text-[11px] uppercase tracking-[0.24em] text-hud-textDim">
          Pull From This Machine
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
          Connector
        </label>
        <select
          value={connector}
          onChange={(e) => setConnector(e.target.value as Connector)}
          disabled={pending}
          className="h-8 appearance-none rounded-md border border-hud-line bg-hud-panel/40 px-3 font-mono text-[12px] text-hud-text focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors cursor-pointer disabled:opacity-50"
        >
          {CONNECTORS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="font-mono text-[10px] uppercase tracking-[0.3em] text-hud-textFaint">
          Limit
        </label>
        <input
          type="number"
          min={1}
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          placeholder="all"
          disabled={pending}
          className="h-8 w-24 rounded-md border border-hud-line bg-hud-panel/40 px-3 font-mono text-[12px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow/60 focus:outline-none focus:ring-1 focus:ring-hud-glow/30 transition-colors disabled:opacity-50"
        />
        <Button size="sm" onClick={pull} disabled={pending} className="ml-auto gap-1.5">
          {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {pending ? "Pulling" : "Pull"}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-hud-warn/40 bg-hud-warn/5 px-3 py-2 font-mono text-[11px] text-hud-warn">
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-hud-glow/25 bg-hud-glow/5 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em]">
          <span className="text-hud-textFaint">{result.source}</span>
          <span>
            <span className="text-hud-glow">{result.conversations_imported.toLocaleString()}</span>
            <span className="ml-1.5 text-hud-textFaint">convs</span>
          </span>
          <span>
            <span className="text-hud-glow">{result.messages_imported.toLocaleString()}</span>
            <span className="ml-1.5 text-hud-textFaint">msgs</span>
          </span>
        </div>
      )}
    </div>
  );
}
