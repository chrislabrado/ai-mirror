import { getFable } from "@/lib/fable";
import type {
  ChatHistoryResponse,
  ChatMessage,
  ConversationDetail,
  ConversationListResponse,
  DashboardSummary,
  DeepDiveRequest,
  DeepDiveResponse,
  EntityDetail,
  ExportGuide,
  FocusLensRequest,
  FocusLensResponse,
  GraphPath,
  IngestResponse,
  InsightsAggregated,
  KGGraph,
  MetaAnalysisRequest,
  RemoteIngestRequest,
  ReportListResponse,
  ReportResponse,
  TemporalEpoch,
  TemporalRefreshRequest,
  TemporalRefreshResponse,
  TrajectoryMetric,
} from "@/types/api";

// Default: backend on port 8000 of whatever host is serving the UI
// (works for localhost and LAN access alike). Override with VITE_API_BASE_URL.
const RAW_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  (typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "");
const BASE = RAW_BASE.replace(/\/$/, "");

/** Error carrying the HTTP status + a human-readable detail extracted from the body. */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, statusText: string, detail: string) {
    super(`API ${status} ${statusText}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extractDetail(text: string): string {
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === "object") {
      const detail = (parsed as Record<string, unknown>).detail;
      if (typeof detail === "string") return detail;
    }
  } catch {
    // Not JSON — fall through to raw text.
  }
  return text;
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined = init?.body ?? undefined;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const resp = await fetch(`${BASE}${path}`, { ...init, headers: { ...headers, ...init?.headers }, body });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new ApiError(resp.status, resp.statusText, extractDetail(text) || path);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/**
 * Tolerant list unwrap — some endpoints return a bare array, others wrap it
 * ({trajectories: [...]}, {epochs: [...]}, {items: [...]}). Accept all.
 */
function unwrapList<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    const rec = data as Record<string, unknown>;
    for (const key of keys) {
      if (Array.isArray(rec[key])) return rec[key] as T[];
    }
    for (const value of Object.values(rec)) {
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request<{ status: string; version: string }>("/healthz"),
  dashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
  exportGuide: () => request<ExportGuide>("/export-guide"),
  fullMirror: (payload: { notes?: string; fable?: boolean | null } = {}) =>
    request<ReportResponse>("/reports/full-mirror", {
      method: "POST",
      json: { fable: getFable(), ...payload },
    }),
  advancedAbstract: (payload: { notes?: string; fable?: boolean | null } = {}) =>
    request<ReportResponse>("/reports/advanced-abstract", {
      method: "POST",
      json: { fable: getFable(), ...payload },
    }),
  metaAnalysis: (payload: MetaAnalysisRequest = {}) =>
    request<ReportResponse>("/reports/meta-analysis", {
      method: "POST",
      json: { fable: getFable(), ...payload },
    }),
  focusLens: (payload: FocusLensRequest) =>
    request<FocusLensResponse>("/focus-lens", {
      method: "POST",
      json: { fable: getFable(), ...payload },
    }),
  chatHistory: (payload: { session_id?: string; messages: ChatMessage[]; top_k?: number }) =>
    request<ChatHistoryResponse>("/chat/history", { method: "POST", json: payload }),
  ingest: async (file: File, source: string = "auto", label?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", source);
    if (label) fd.append("label", label);
    return request<IngestResponse>("/ingest", { method: "POST", body: fd });
  },
  ingestRemote: (payload: RemoteIngestRequest) =>
    request<IngestResponse>("/ingest/remote", { method: "POST", json: payload }),

  // Temporal
  temporalEpochs: async (): Promise<TemporalEpoch[]> =>
    unwrapList<TemporalEpoch>(await request<unknown>("/temporal/epochs"), ["epochs"]),
  temporalRefresh: (payload: TemporalRefreshRequest = {}) =>
    request<TemporalRefreshResponse>("/temporal/refresh", {
      method: "POST",
      json: { fable: getFable(), ...payload },
    }),
  synthesizeTrajectories: async (
    payload: { fable?: boolean | null } = {},
  ): Promise<TrajectoryMetric[]> =>
    unwrapList<TrajectoryMetric>(
      await request<unknown>("/temporal/trajectories", {
        method: "POST",
        json: { fable: getFable(), ...payload },
      }),
      ["trajectories", "items", "metrics"],
    ),
  listTrajectories: async (): Promise<TrajectoryMetric[]> =>
    unwrapList<TrajectoryMetric>(await request<unknown>("/temporal/trajectories"), [
      "trajectories",
      "items",
      "metrics",
    ]),

  // History
  listConversations: (params: { q?: string; source?: string; limit?: number; offset?: number } = {}) =>
    request<ConversationListResponse>(`/history/conversations${qs(params)}`),
  getConversation: (id: number) =>
    request<ConversationDetail>(`/history/conversations/${id}`),

  // Reports
  listReports: (params: { kind?: string; limit?: number; offset?: number } = {}) =>
    request<ReportListResponse>(`/reports${qs(params)}`),
  getReport: (id: number) => request<ReportResponse>(`/reports/${id}`),
  reportMarkdownUrl: (id: number): string => `${BASE}/reports/${id}/markdown`,
  downloadReportMarkdown: async (id: number): Promise<void> => {
    const resp = await fetch(`${BASE}/reports/${id}/markdown`);
    if (!resp.ok) {
      throw new Error(`Download failed: ${resp.status} ${resp.statusText}`);
    }
    const blob = await resp.blob();
    const disposition = resp.headers.get("content-disposition") ?? "";
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/);
    const filename = filenameMatch?.[1] ?? `ai-mirror-report-${id}.md`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // Knowledge graph
  exploreGraph: (params: { focus?: string; limit?: number } = {}) =>
    request<KGGraph>(`/graph/explore${qs(params)}`),
  getEntityDetail: (id: number) =>
    request<EntityDetail>(`/graph/node/${id}`),
  getGraphPath: (params: { from: number; to: number; max_hops?: number }) =>
    request<GraphPath>(`/graph/path${qs({ from: params.from, to: params.to, max_hops: params.max_hops ?? 4 })}`),

  // Insights
  insightsAggregated: () => request<InsightsAggregated>("/insights/aggregated"),
  insightsDeepDive: (payload: DeepDiveRequest) =>
    request<DeepDiveResponse>("/insights/deep-dive", { method: "POST", json: payload }),
};
