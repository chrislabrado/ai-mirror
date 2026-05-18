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
  ReportListResponse,
  ReportResponse,
} from "@/types/api";

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const BASE = RAW_BASE.replace(/\/$/, "");

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined = init?.body;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const resp = await fetch(`${BASE}${path}`, { ...init, headers: { ...headers, ...init?.headers }, body });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status} ${resp.statusText}: ${text || path}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
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
  fullMirror: (payload: { notes?: string } = {}) =>
    request<ReportResponse>("/reports/full-mirror", { method: "POST", json: payload }),
  advancedAbstract: (payload: { notes?: string } = {}) =>
    request<ReportResponse>("/reports/advanced-abstract", { method: "POST", json: payload }),
  focusLens: (payload: FocusLensRequest) =>
    request<FocusLensResponse>("/focus-lens", { method: "POST", json: payload }),
  chatHistory: (payload: { session_id?: string; messages: ChatMessage[]; top_k?: number }) =>
    request<ChatHistoryResponse>("/chat/history", { method: "POST", json: payload }),
  ingest: async (file: File, source: string = "auto", label?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", source);
    if (label) fd.append("label", label);
    return request<IngestResponse>("/ingest", { method: "POST", body: fd });
  },

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
