// Mirrors backend Pydantic schemas (app/schemas/*.py)

export interface GaugeSet {
  thought_clarity: number;
  self_reflection_depth: number;
  aptitude_balance: number;
}

export interface SourceStat {
  slug: string;
  name: string;
  conversations: number;
}

export interface DashboardSummary {
  last_run_at: string | null;
  last_run_kind: string | null;
  bullets: string[];
  gauges: GaugeSet | null;
  total_conversations: number;
  total_messages: number;
  sources: SourceStat[];
}

export interface Evidence {
  message_id: number | null;
  conversation_id: number | null;
  snippet: string;
  source_slug: string | null;
  message_at: string | null;
}

export interface ReportBlockOut {
  id: number;
  block_type: string;
  heading: string | null;
  position: number;
  body_markdown: string;
  structured?: Record<string, unknown> | null;
  evidence?: Evidence[] | null;
}

export interface ReportResponse {
  report_id: number;
  kind: string;
  title: string;
  summary: string;
  gauges: GaugeSet | null;
  blocks: ReportBlockOut[];
  model_used: string | null;
  created_at: string;
}

export interface FocusLensRequest {
  query: string;
  date_from?: string | null;
  date_to?: string | null;
  sources?: string[] | null;
  max_evidence?: number;
}

export interface FocusLensResponse {
  report_id: number;
  title: string;
  summary: string;
  blocks: ReportBlockOut[];
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatHistoryResponse {
  session_id: string;
  reply: string;
  evidence: Evidence[];
  model_used: string | null;
}

export interface ExportStep { n: number; text: string }
export interface ExportPlatform {
  slug: string;
  name: string;
  icon: string;
  summary: string;
  steps: ExportStep[];
  output_formats: string[];
  notes: string[];
  docs_url: string | null;
}
export interface ExportGuide {
  version: string;
  last_updated: string;
  intro: string;
  footer_note: string;
  platforms: ExportPlatform[];
}

export interface IngestResponse {
  job_id: number;
  source: string;
  filename: string;
  status: string;
  conversations_imported: number;
  messages_imported: number;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

// --- History ---
export interface ConversationListItem {
  id: number;
  source_slug: string;
  source_name: string;
  title: string | null;
  message_count: number;
  started_at: string | null;
  updated_at: string;
}

export interface MessageOut {
  id: number;
  sequence: number;
  role: string;
  content: string;
  message_at: string | null;
}

export interface ConversationDetail {
  id: number;
  source_slug: string;
  source_name: string;
  title: string | null;
  summary: string | null;
  message_count: number;
  started_at: string | null;
  ended_at: string | null;
  messages: MessageOut[];
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  total: number;
}

// --- Reports list ---
export interface ReportListItem {
  id: number;
  kind: string;
  title: string;
  summary: string | null;
  model_used: string | null;
  created_at: string;
}

export interface ReportListResponse {
  items: ReportListItem[];
  total: number;
}

// --- Knowledge graph ---
export interface KGNode {
  id: number;
  label: string;
  kind: string;
  salience: number;
}

export interface KGEdge {
  id: number;
  source_id: number;
  target_id: number;
  predicate: string;
  weight: number;
}

export interface KGGraph {
  nodes: KGNode[];
  edges: KGEdge[];
}

// --- Knowledge graph detail ---
export interface NeighbourEdge {
  entity_id: number;
  label: string;
  kind: string;
  predicate: string;
  weight: number;
}

export interface EvidenceMessage {
  message_id: number;
  conversation_id: number;
  conversation_title: string | null;
  source_slug: string;
  role: string;
  snippet: string;
  message_at: string | null;
}

export interface RelatedReport {
  report_id: number;
  report_kind: string;
  block_type: string;
  block_heading: string | null;
  snippet: string;
}

export interface EntityDetail {
  id: number;
  label: string;
  kind: string;
  salience: number;
  description: string | null;
  incoming: NeighbourEdge[];
  outgoing: NeighbourEdge[];
  evidence_messages: EvidenceMessage[];
  related_reports: RelatedReport[];
}

export interface GraphPath {
  nodes: KGNode[];
  edges: KGEdge[];
}

// --- Insights ---
export interface AggregatedBlock {
  block_type: string;
  heading: string | null;
  occurrence_count: number;
  sample_body: string;
  latest_report_id: number;
  latest_created_at: string;
}

export interface InsightsAggregated {
  total_reports: number;
  total_blocks: number;
  blocks: AggregatedBlock[];
}

// --- Deep Dive ---
export interface DeepDiveRequest {
  block_type: string;
  focus_question?: string;
  sources?: string[];
}

export interface DeepDiveResponse {
  block_type: string;
  heading: string;
  body_markdown: string;
  evidence: Evidence[];
  source_report_id: number | null;
  model_used: string | null;
  duration_seconds: number;
  created_at: string;
}
