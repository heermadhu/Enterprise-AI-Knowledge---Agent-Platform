export interface Citation {
  filename: string;
  page: number | null;
  snippet: string;
  score: number;
  document_id: number;
  chunk_index: number;
}

export interface DocumentRecord {
  id: number;
  filename: string;
  content_type: string;
  file_size: number;
  status: string;
  page_count: number;
  chunk_count: number;
  uploaded_at: string;
}

export interface ConversationRecord {
  id: number;
  title: string;
  created_at: string;
  message_count: number;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  metadata: {
    citations?: Citation[];
    selected_tools?: string[];
    sql?: string | null;
  };
  created_at: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  selected_tools: string[];
  sql: string | null;
  total_latency_ms: number;
  retrieval_latency_ms: number;
  llm_latency_ms: number;
  token_usage: number | null;
  conversation_id: number;
  request_id: string;
}

export interface DatabaseOverview {
  customers: number;
  products: number;
  orders: number;
  sales: number;
  recognized_revenue: string;
  monthly_revenue: { month: string; revenue: string }[];
}

export interface MonitoringSummary {
  requests: number;
  errors: number;
  average_latency_ms: number;
  retrieved_chunks: number;
  token_usage: number;
}

export interface MonitoringRequest {
  request_id: string;
  timestamp: string;
  status_code: number;
  query: string;
  selected_tools: string[];
  retrieval_latency_ms: number;
  llm_latency_ms: number;
  total_latency_ms: number;
  retrieved_chunks: number;
  token_usage: number | null;
  error: string | null;
}

export interface EvaluationMetrics {
  answer_correctness: number | null;
  retrieval_relevance: number | null;
  citation_correctness: number | null;
  sql_correctness: number | null;
  tool_selection_correctness?: number | null;
  average_latency_ms: number | null;
  average_token_usage?: number | null;
}

export interface EvaluationRun {
  id: number;
  status: string;
  total_cases: number;
  started_at: string;
  finished_at: string | null;
  summary: EvaluationMetrics;
}

export interface EvaluationCase {
  id: string;
  category: string;
  question: string;
}

export interface EvaluationResult {
  case_id: string;
  category: string;
  question: string;
  answer: string;
  answer_correctness: number | null;
  retrieval_relevance: number | null;
  citation_correctness: number | null;
  sql_correctness: number | null;
  tool_selection_correctness: number | null;
  latency_ms: number;
  token_usage: number | null;
  citations: Citation[];
  selected_tools: string[];
}

export interface EvaluationRunDetail {
  id: number;
  status: string;
  total_cases: number;
  summary: EvaluationMetrics;
  results: EvaluationResult[];
}

export interface PlatformSettings {
  app_name: string;
  environment: string;
  database: string;
  llm: { provider: string; model: string | null; configured: boolean };
  embeddings: { provider: string; model: string; configured: boolean };
  vector_store: string;
  max_upload_mb: number;
  chunk_size: number;
  chunk_overlap: number;
  rate_limit: { requests: number; window_seconds: number };
  allowed_file_types: string[];
}
