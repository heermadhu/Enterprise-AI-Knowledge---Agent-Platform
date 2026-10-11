import { lazy, Suspense, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  FileText,
  FlaskConical,
  Files,
  Layers3,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { api } from "./api";
import type {
  ChatResponse,
  Citation,
  ConversationRecord,
  DatabaseOverview,
  DocumentRecord,
  EvaluationCase,
  EvaluationRun,
  EvaluationRunDetail,
  EvaluationResult,
  MonitoringRequest,
  MonitoringSummary,
  PlatformSettings,
  StoredMessage,
} from "./types";

const RevenueTrendChart = lazy(() => import("./Charts").then((module) => ({ default: module.RevenueTrendChart })));
const MonthlyRevenueChart = lazy(() => import("./Charts").then((module) => ({ default: module.MonthlyRevenueChart })));
const EvaluationTrendChart = lazy(() => import("./Charts").then((module) => ({ default: module.EvaluationTrendChart })));
const MarkdownAnswer = lazy(() => import("./MarkdownAnswer"));

const toolLabels: Record<string, string> = {
  document_search: "Document search",
  database_query: "Business data",
  calculator: "Calculator",
  document_metadata_search: "Document catalog",
};

function PageHeading({ eyebrow, title, description, action }: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
      {action && <div className="heading-action">{action}</div>}
    </div>
  );
}

function MetricCard({ label, value, detail, icon: Icon, accent = "blue" }: {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  accent?: string;
}) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${accent}`}><Icon size={17} /></div>
      <div className="metric-label">{label}</div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-detail">{detail}</span>
    </article>
  );
}

function ErrorBanner({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-banner" role="alert"><CircleHelp size={16} /><span>{message}</span>{retry && <button onClick={retry}>Retry</button>}</div>;
}

function LoadingState({ label = "Loading workspace data…" }: { label?: string }) {
  return <div className="loading-state"><span className="spinner" />{label}</div>;
}

export function DashboardView({ onAsk, onSearch }: { onAsk: (prompt: string) => void; onSearch: (query?: string) => void }) {
  const [overview, setOverview] = useState<DatabaseOverview | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [monitoring, setMonitoring] = useState<MonitoringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [db, docs, monitor] = await Promise.all([
        api<DatabaseOverview>("/api/database/overview"),
        api<DocumentRecord[]>("/api/documents"),
        api<MonitoringSummary>("/api/monitoring/summary"),
      ]);
      setOverview(db);
      setDocuments(docs);
      setMonitoring(monitor);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const chartData = overview?.monthly_revenue.map((row) => ({
    month: new Date(`${row.month}T12:00:00`).toLocaleDateString(undefined, { month: "short" }),
    revenue: Number(row.revenue),
  })) ?? [];

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow={`${new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase()} · NOVATECH WORKSPACE`}
        title={`${greeting()}, team.`}
        description="Your company knowledge, business data, and AI agents in one place."
        action={<button className="button button-primary" onClick={() => onAsk("")}><Sparkles size={16} />Ask Nova <ArrowRight size={15} /></button>}
      />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {loading && <LoadingState />}
      {!loading && overview && monitoring && (
        <>
          <section className="metric-grid" aria-label="Workspace metrics">
            <MetricCard label="Recognized revenue" value={formatCurrency(Number(overview.recognized_revenue))} detail="Full-year 2025 ledger" icon={ArrowUpRight} accent="blue" />
            <MetricCard label="Customers" value={overview.customers.toLocaleString()} detail="In the business database" icon={Users} accent="violet" />
            <MetricCard label="Indexed documents" value={documents.length.toLocaleString()} detail={`${documents.reduce((sum, doc) => sum + doc.chunk_count, 0).toLocaleString()} searchable passages`} icon={Layers3} accent="teal" />
            <MetricCard label="Agent requests" value={monitoring.requests.toLocaleString()} detail={`${monitoring.errors.toLocaleString()} recorded errors`} icon={Activity} accent="amber" />
          </section>

          <section className="dashboard-grid">
            <article className="panel revenue-panel">
              <div className="panel-heading">
                <div><div className="panel-title">Revenue overview</div><div className="panel-subtitle">Monthly recognized revenue · USD</div></div>
                <span className="panel-pill"><span className="pill-dot" /> Live from database</span>
              </div>
              {chartData.length ? (
                <div className="chart-wrap revenue-chart">
                  <Suspense fallback={<div className="loading-row"><span className="spinner" />Rendering chart…</div>}><RevenueTrendChart data={chartData} /></Suspense>
                </div>
              ) : <div className="empty-inline">No monthly revenue rows are available.</div>}
              <div className="chart-footnote"><span>2025 dataset</span><span>Source: monthly_revenue</span></div>
            </article>

            <article className="panel activity-panel">
              <div className="panel-heading"><div><div className="panel-title">Platform activity</div><div className="panel-subtitle">Observed across this workspace</div></div><Activity size={17} className="muted-icon" /></div>
              <div className="activity-stat"><strong>{monitoring.average_latency_ms ? `${monitoring.average_latency_ms.toLocaleString()} ms` : "—"}</strong><span>Average response time</span></div>
              <div className="activity-row"><span><span className="activity-dot blue-dot" />Requests processed</span><strong>{monitoring.requests.toLocaleString()}</strong></div>
              <div className="activity-row"><span><span className="activity-dot green-dot" />Evidence chunks retrieved</span><strong>{monitoring.retrieved_chunks.toLocaleString()}</strong></div>
              <div className="activity-row"><span><span className="activity-dot amber-dot" />LLM tokens recorded</span><strong>{monitoring.token_usage.toLocaleString()}</strong></div>
              <button className="text-link" onClick={() => onSearch("Q3 2025 revenue")}>Search business knowledge <ArrowRight size={14} /></button>
            </article>
          </section>

          <section className="dashboard-grid lower-grid">
            <article className="panel">
              <div className="panel-heading"><div><div className="panel-title">Recent documents</div><div className="panel-subtitle">Indexed sources available to Nova</div></div><button className="subtle-button" onClick={() => onSearch()}>View all <ArrowRight size={14} /></button></div>
              {documents.length ? <div className="recent-doc-list">
                {documents.slice(0, 5).map((doc) => <div className="recent-doc" key={doc.id}><div className="file-icon"><FileText size={16} /></div><div className="recent-doc-copy"><strong>{doc.filename}</strong><span>{doc.chunk_count} passages · {formatBytes(doc.file_size)}</span></div><span className="status-badge"><span />Indexed</span></div>)}
              </div> : <div className="empty-inline">Upload a report or policy to make it searchable.</div>}
            </article>
            <article className="panel quick-panel">
              <div className="panel-heading"><div><div className="panel-title">Ask your knowledge base</div><div className="panel-subtitle">Start with a business question</div></div><Sparkles size={16} className="muted-icon" /></div>
              <div className="prompt-list">
                {[
                  "What is our remote work policy?",
                  "Which product generated the most revenue?",
                  "Why did September revenue fall compared with August?",
                ].map((prompt) => <button className="prompt-suggestion" key={prompt} onClick={() => onAsk(prompt)}><span>{prompt}</span><ArrowUpRight size={14} /></button>)}
              </div>
            </article>
          </section>
        </>
      )}
    </div>
  );
}

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  selectedTools?: string[];
  sql?: string | null;
  latency?: number;
  tokenUsage?: number | null;
};

export function ChatView({ initialPrompt, onPromptUsed, onViewSource }: {
  initialPrompt: string;
  onPromptUsed: () => void;
  onViewSource: (citation: Citation) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [lastPrompt, setLastPrompt] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const refreshHistory = async () => {
    try {
      setConversations(await api<ConversationRecord[]>("/api/conversations"));
      setHistoryError("");
    } catch (reason) {
      setHistoryError((reason as Error).message);
    }
  };
  useEffect(() => { void refreshHistory(); }, []);
  useEffect(() => {
    if (initialPrompt) {
      setDraft(initialPrompt);
      onPromptUsed();
    }
  }, [initialPrompt, onPromptUsed]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, sending]);

  const newConversation = () => {
    setConversationId(null);
    setMessages([]);
    setError("");
    setLastPrompt("");
    setDraft("");
  };

  const openConversation = async (id: number) => {
    setError("");
    try {
      const record = await api<{ id: number; messages: StoredMessage[] }>(`/api/conversations/${id}`);
      setConversationId(record.id);
      setMessages(record.messages.map((message) => ({
        id: `stored-${message.id}`,
        role: message.role,
        content: message.content,
        citations: message.metadata?.citations ?? [],
        selectedTools: message.metadata?.selected_tools ?? [],
        sql: message.metadata?.sql,
      })));
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const sendMessage = async (submitted?: string, addUserMessage = true) => {
    const query = (submitted ?? draft).trim();
    if (!query || sending) return;
    setSending(true);
    setError("");
    setLastPrompt(query);
    if (addUserMessage) {
      setMessages((current) => [...current, { id: `user-${crypto.randomUUID()}`, role: "user", content: query }]);
      setDraft("");
    }
    try {
      const response = await api<ChatResponse>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ query, conversation_id: conversationId }),
      });
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, {
        id: `assistant-${response.request_id}`,
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        selectedTools: response.selected_tools,
        sql: response.sql,
        latency: response.total_latency_ms,
        tokenUsage: response.token_usage,
      }]);
      await refreshHistory();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSending(false);
    }
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const copyAnswer = async (message: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedId(message.id);
      window.setTimeout(() => setCopiedId(""), 1800);
    } catch {
      setError("Clipboard access is unavailable in this browser.");
    }
  };

  return (
    <div className="chat-page">
      <aside className="chat-history">
        <div className="history-header"><div><span className="eyebrow">ASSISTANT</span><strong>Conversations</strong></div><button className="icon-button primary-icon" onClick={newConversation} aria-label="Start a new conversation"><Plus size={17} /></button></div>
        <button className={`new-chat-button ${conversationId === null && messages.length === 0 ? "selected" : ""}`} onClick={newConversation}><Plus size={15} />New conversation</button>
        {historyError && <div className="history-error">{historyError}</div>}
        <div className="history-label">RECENT</div>
        <div className="history-list">
          {conversations.map((conversation) => <button className={`history-item ${conversation.id === conversationId ? "active" : ""}`} key={conversation.id} onClick={() => void openConversation(conversation.id)}><MessageSquareText size={15} /><span>{conversation.title}</span></button>)}
          {!conversations.length && <div className="history-empty">Your conversations will appear here.</div>}
        </div>
        <div className="history-foot"><ShieldCheck size={14} /><span>Evidence-backed responses</span></div>
      </aside>

      <section className="chat-main">
        <div className="chat-topline"><div className="chat-title"><div className="nova-avatar"><Sparkles size={16} /></div><div><strong>Nova assistant</strong><span><span className="presence-dot" /> Grounded in your workspace</span></div></div><span className="model-tag">AI AGENT</span></div>

        <div className={`chat-transcript ${messages.length === 0 ? "empty-transcript" : ""}`}>
          {messages.length === 0 ? (
            <div className="chat-welcome">
              <div className="welcome-orbit"><Sparkles size={23} /></div>
              <span className="eyebrow">NOVA KNOWLEDGE ASSISTANT</span>
              <h2>What would you like<br />to understand?</h2>
              <p>Ask across company documents and business data. Nova will show its sources and generated SQL.</p>
              <div className="starter-prompts">
                {[
                  { icon: FileText, text: "What is our remote work policy?" },
                  { icon: Database, text: "Which product generated the most revenue?" },
                  { icon: Activity, text: "Why did September revenue fall compared with August?" },
                ].map(({ icon: Icon, text }) => <button key={text} onClick={() => setDraft(text)}><Icon size={15} /><span>{text}</span><ChevronRight size={14} /></button>)}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => (
                <article className={`message-row ${message.role}`} key={message.id}>
                  <div className={`message-avatar ${message.role}`}>{message.role === "assistant" ? <Sparkles size={15} /> : "N"}</div>
                  <div className="message-body">
                    <div className="message-meta"><strong>{message.role === "assistant" ? "Nova" : "You"}</strong>{message.latency !== undefined && <span>{message.latency.toLocaleString()} ms</span>}</div>
                    {message.role === "assistant" ? (
                      <>
                        <div className="markdown-content"><Suspense fallback={<div className="loading-row"><span className="spinner" />Rendering answer…</div>}><MarkdownAnswer content={message.content} /></Suspense></div>
                        {message.selectedTools?.length ? <div className="tool-summary"><span>USED</span>{message.selectedTools.map((tool) => <span className="tool-chip" key={tool}>{toolLabels[tool] ?? tool}</span>)}</div> : null}
                        {message.sql && <details className="sql-details"><summary><Database size={14} />Generated read-only SQL <ChevronRight size={13} /></summary><pre><code>{message.sql}</code></pre></details>}
                        {message.citations?.length ? <div className="citation-section"><div className="citation-heading"><span>Sources</span><span>{message.citations.length} passages</span></div><div className="citation-list">
                          {message.citations.map((citation, index) => <button className="citation-card" key={`${citation.document_id}-${citation.chunk_index}-${index}`} onClick={() => onViewSource(citation)}>
                            <span className="citation-number">{index + 1}</span><span className="citation-copy"><strong>{citation.filename}</strong><small>{citation.page ? `Page ${citation.page}` : "Document passage"} · Relevance {Math.round(citation.score * 100)}%</small><span>{citation.snippet.slice(0, 180)}{citation.snippet.length > 180 ? "…" : ""}</span></span><ArrowUpRight size={14} />
                          </button>)}
                        </div></div> : null}
                        <div className="message-actions"><button onClick={() => void copyAnswer(message)}>{copiedId === message.id ? <Check size={13} /> : <Copy size={13} />}{copiedId === message.id ? "Copied" : "Copy"}</button>{message.tokenUsage !== null && message.tokenUsage !== undefined && <span>{message.tokenUsage} tokens</span>}</div>
                      </>
                    ) : <div className="user-message-content">{message.content}</div>}
                  </div>
                </article>
              ))}
              {sending && <div className="thinking-row"><span className="thinking-icon"><Sparkles size={14} /></span><div><span className="thinking-dots"><i /><i /><i /></span><span>Searching your workspace and preparing an answer…</span></div></div>}
              <div ref={endRef} />
            </div>
          )}
        </div>

        <div className="composer-area">
          {error && <div className="chat-error" role="alert"><span>{error}</span>{lastPrompt && <button onClick={() => void sendMessage(lastPrompt, false)}><RefreshCw size={13} />Retry</button>}<button className="close-error" onClick={() => setError("")} aria-label="Dismiss error"><X size={14} /></button></div>}
          <form className="composer" onSubmit={(event: FormEvent) => { event.preventDefault(); void sendMessage(); }}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onComposerKeyDown} placeholder="Ask a question across NovaTech…" rows={2} maxLength={4000} aria-label="Ask Nova" />
            <div className="composer-footer"><span><kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for a new line</span><button className="send-button" type="submit" disabled={!draft.trim() || sending} aria-label="Send message">{sending ? <LoaderCircle className="spin" size={17} /> : <Send size={16} />}</button></div>
          </form>
          <div className="composer-disclaimer">Nova uses indexed sources and validated read-only queries. Verify important decisions against the source.</div>
        </div>
      </section>
    </div>
  );
}

export function DocumentsView({ initialSearch, onSearchUsed, onViewSource }: {
  initialSearch: string;
  onSearchUsed: () => void;
  onViewSource: (citation: Citation) => void;
}) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Citation[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setError("");
    try { setDocuments(await api<DocumentRecord[]>("/api/documents")); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (initialSearch) {
      setSearch(initialSearch);
      void runSearch(initialSearch);
      onSearchUsed();
    }
  }, [initialSearch, onSearchUsed]);

  const uploadFiles = async () => {
    if (!files.length || uploading) return;
    setUploading(true);
    setError("");
    setNotice("");
    const added: string[] = [];
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      try {
        const result = await api<{ filename: string; status: string }>("/api/documents", { method: "POST", body: form });
        added.push(result.filename);
      } catch (reason) {
        setError(`${file.name}: ${(reason as Error).message}`);
        break;
      }
    }
    if (added.length) setNotice(`${added.length} document${added.length === 1 ? "" : "s"} indexed and ready to search.`);
    setFiles([]);
    setUploading(false);
    await load();
  };

  const runSearch = async (submitted = search) => {
    if (submitted.trim().length < 2 || searching) return;
    setSearching(true);
    setError("");
    try {
      const response = await api<{ citations: Citation[] }>("/api/documents/search", {
        method: "POST",
        body: JSON.stringify({ query: submitted, limit: 8 }),
      });
      setResults(response.citations);
    } catch (reason) { setError((reason as Error).message); }
    finally { setSearching(false); }
  };

  const deleteDocument = async (document: DocumentRecord) => {
    if (!window.confirm(`Remove "${document.filename}" and its indexed passages?`)) return;
    try {
      await api<void>(`/api/documents/${document.id}`, { method: "DELETE" });
      setNotice(`${document.filename} was removed.`);
      await load();
    } catch (reason) { setError((reason as Error).message); }
  };

  return (
    <div className="page-stack">
      <PageHeading eyebrow="KNOWLEDGE BASE" title="Documents" description="Upload source material, inspect indexing status, and search the evidence Nova can cite." action={<label className="button button-primary upload-cta"><Upload size={16} />Add documents<input type="file" accept=".pdf,.docx,.txt,.csv" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></label>} />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {notice && <div className="success-banner"><CheckCircle2 size={16} />{notice}<button onClick={() => setNotice("")} aria-label="Dismiss"><X size={14} /></button></div>}

      <section className="documents-main-grid">
        <article className="panel document-library">
          <div className="panel-heading"><div><div className="panel-title">Source library</div><div className="panel-subtitle">{loading ? "Loading indexed sources…" : `${documents.length} documents · ${documents.reduce((sum, doc) => sum + doc.chunk_count, 0)} passages`}</div></div><button className="icon-button" onClick={() => void load()} aria-label="Refresh documents"><RefreshCw size={15} /></button></div>
          {files.length > 0 && <div className="upload-queue"><div><strong>{files.length} selected</strong><span>{files.map((file) => file.name).join(", ")}</span></div><button className="button button-primary button-small" onClick={() => void uploadFiles()} disabled={uploading}>{uploading ? <LoaderCircle className="spin" size={14} /> : <Upload size={14} />}{uploading ? "Indexing…" : "Upload & index"}</button><button className="icon-button" onClick={() => setFiles([])} aria-label="Clear selected files"><X size={14} /></button></div>}
          <div className="document-table-wrap"><table className="data-table document-table"><thead><tr><th>DOCUMENT</th><th>STATUS</th><th>PASSAGES</th><th>SIZE</th><th>UPLOADED</th><th /></tr></thead><tbody>
            {documents.map((document) => <tr key={document.id}><td><div className="table-file"><div className="file-icon"><FileText size={16} /></div><div><strong>{document.filename}</strong><small>{document.content_type}</small></div></div></td><td><span className={`status-badge ${document.status !== "indexed" ? "pending" : ""}`}><span />{document.status}</span></td><td>{document.chunk_count}</td><td>{formatBytes(document.file_size)}</td><td>{formatDate(document.uploaded_at)}</td><td><button className="table-action danger-hover" onClick={() => void deleteDocument(document)} aria-label={`Delete ${document.filename}`}><Trash2 size={15} /></button></td></tr>)}
          </tbody></table></div>
          {!loading && documents.length === 0 && <div className="empty-panel"><div className="empty-icon"><Files size={20} /></div><strong>Your source library is empty</strong><p>Add a PDF, DOCX, TXT, or CSV to start building a searchable knowledge base.</p><label className="button button-secondary upload-cta"><Upload size={15} />Choose a file<input type="file" accept=".pdf,.docx,.txt,.csv" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></label></div>}
          <div className="upload-guidance"><ShieldCheck size={14} /><span>The API enforces its configured upload size limit. Content is extracted, chunked, embedded, and indexed in Qdrant.</span></div>
        </article>

        <article className="panel document-search-panel">
          <div className="panel-heading"><div><div className="panel-title">Search evidence</div><div className="panel-subtitle">Preview passages before asking Nova</div></div><Search size={16} className="muted-icon" /></div>
          <form className="inline-search" onSubmit={(event) => { event.preventDefault(); void runSearch(); }}><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Try “remote work policy”" maxLength={2000} /><button type="submit" disabled={searching || search.trim().length < 2}>{searching ? <LoaderCircle className="spin" size={15} /> : <ArrowRight size={15} />}</button></form>
          {results.length ? <div className="search-results"><div className="results-count">{results.length} matching passages</div>{results.map((citation, index) => <button className="search-result-card" key={`${citation.document_id}-${citation.chunk_index}-${index}`} onClick={() => onViewSource(citation)}><div className="result-source"><FileText size={14} /><strong>{citation.filename}</strong><span>{citation.page ? `Page ${citation.page}` : "Passage"}</span></div><p>{citation.snippet}</p><div className="result-foot"><span>Relevance score</span><strong>{Math.round(citation.score * 100)}%</strong></div></button>)}</div> : <div className="search-empty"><div className="search-empty-icon"><Search size={18} /></div><strong>{searching ? "Searching indexed passages…" : results.length === 0 && search ? "No evidence found" : "Find relevant evidence"}</strong><p>{search ? "Try a different phrase or upload a source document." : "Enter a phrase to retrieve relevant snippets with source metadata."}</p></div>}
        </article>
      </section>
    </div>
  );
}

type SQLResult = { sql: string; columns: string[]; rows: Record<string, unknown>[]; row_count: number };

export function DatabaseView() {
  const [overview, setOverview] = useState<DatabaseOverview | null>(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<SQLResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try { setOverview(await api<DatabaseOverview>("/api/database/overview")); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const runQuery = async (event?: FormEvent) => {
    event?.preventDefault();
    if (question.trim().length < 2 || running) return;
    setRunning(true);
    setError("");
    try {
      setResult(await api<SQLResult>("/api/database/query", { method: "POST", body: JSON.stringify({ question }) }));
    } catch (reason) { setError((reason as Error).message); }
    finally { setRunning(false); }
  };

  const examples = ["What was revenue in Q3 2025?", "Which product generated the most revenue?", "How many customers are in the database?"];
  const chartData = overview?.monthly_revenue.map((row) => ({
    month: new Date(`${row.month}T12:00:00`).toLocaleDateString(undefined, { month: "short" }),
    revenue: Number(row.revenue),
  })) ?? [];

  return (
    <div className="page-stack">
      <PageHeading eyebrow="BUSINESS INTELLIGENCE" title="Database explorer" description="Ask in natural language. The platform generates, validates, and executes read-only SQL against NovaTech's seeded business data." />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {loading && <LoadingState />}
      {!loading && overview && <>
        <section className="database-stat-grid">
          <MetricCard label="Customers" value={overview.customers.toLocaleString()} detail="Verified business records" icon={Users} accent="blue" />
          <MetricCard label="Products" value={overview.products.toLocaleString()} detail="Catalog entries" icon={Layers3} accent="violet" />
          <MetricCard label="Orders" value={overview.orders.toLocaleString()} detail="Completed orders" icon={Database} accent="teal" />
          <MetricCard label="Recognized revenue" value={formatCurrency(Number(overview.recognized_revenue))} detail="2025 financial year" icon={ArrowUpRight} accent="amber" />
        </section>
        <section className="database-content-grid">
          <article className="panel database-chart-panel"><div className="panel-heading"><div><div className="panel-title">Monthly revenue</div><div className="panel-subtitle">The chart reads from the monthly_revenue table</div></div><span className="panel-pill">USD · 2025</span></div>
            {chartData.length ? <div className="chart-wrap database-chart"><Suspense fallback={<div className="loading-row"><span className="spinner" />Rendering chart…</div>}><MonthlyRevenueChart data={chartData} /></Suspense></div> : <div className="empty-inline">No monthly revenue rows were returned.</div>}
          </article>
          <article className="panel schema-panel"><div className="panel-heading"><div><div className="panel-title">Available tables</div><div className="panel-subtitle">Query scope is restricted server-side</div></div><ShieldCheck size={16} className="muted-icon" /></div>
            {[
            { name: "customers", count: overview.customers, detail: "industry, region" },
            { name: "products", count: overview.products, detail: "category, price" },
            { name: "orders", count: overview.orders, detail: "date, status, total" },
            { name: "sales", count: overview.sales, detail: "product revenue" },
            { name: "monthly_revenue", count: overview.monthly_revenue.length, detail: "recognized totals" },
            ].map((table) => <div className="schema-row" key={table.name}><div className="schema-table-icon"><Database size={14} /></div><div><strong>{table.name}</strong><span>{table.count.toLocaleString()} records · {table.detail}</span></div><span className="schema-lock"><ShieldCheck size={13} /></span></div>)}
          </article>
        </section>
        <section className="panel sql-playground">
          <div className="panel-heading"><div><div className="panel-title">Natural language query</div><div className="panel-subtitle">Generated SQL is always parsed, table-scoped, and row-limited before execution.</div></div><span className="readonly-tag"><ShieldCheck size={13} />READ-ONLY</span></div>
          <form className="query-form" onSubmit={(event) => void runQuery(event)}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about customers, products, orders, or revenue…" rows={2} maxLength={2000} /><button className="button button-primary" type="submit" disabled={running || question.trim().length < 2}>{running ? <LoaderCircle className="spin" size={15} /> : <Search size={15} />}{running ? "Running…" : "Generate & run"}</button></form>
          <div className="example-queries"><span>TRY</span>{examples.map((example) => <button key={example} onClick={() => setQuestion(example)}>{example}<ArrowUpRight size={12} /></button>)}</div>
          {result && <div className="query-output">
            <div className="query-output-heading"><strong>Query result</strong><span>{result.row_count} row{result.row_count === 1 ? "" : "s"}</span></div>
            <details className="sql-details" open><summary><Database size={14} />Generated SQL <ChevronRight size={13} /></summary><pre><code>{result.sql}</code></pre></details>
            <div className="result-table-wrap"><table className="data-table"><thead><tr>{result.columns.map((column) => <th key={column}>{column.replace(/_/g, " ").toUpperCase()}</th>)}</tr></thead><tbody>{result.rows.map((row, rowIndex) => <tr key={rowIndex}>{result.columns.map((column) => <td key={column}>{String(row[column] ?? "—")}</td>)}</tr>)}</tbody></table>{!result.rows.length && <div className="empty-inline">The validated query returned no rows.</div>}</div>
          </div>}
        </section>
      </>}
    </div>
  );
}

export function EvaluationsView({ onViewSource }: { onViewSource: (citation: Citation) => void }) {
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [detail, setDetail] = useState<EvaluationRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [caseResponse, history] = await Promise.all([
        api<{ cases: EvaluationCase[] }>("/api/evaluations/cases"),
        api<EvaluationRun[]>("/api/evaluations/runs"),
      ]);
      setCases(caseResponse.cases);
      setRuns(history);
    } catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const runNow = async () => {
    if (running || !cases.length) return;
    setRunning(true);
    setError("");
    try {
      const latest = await api<EvaluationRunDetail>("/api/evaluations/runs", {
        method: "POST",
        body: JSON.stringify({ limit: cases.length }),
      });
      setDetail(latest);
      await load();
    } catch (reason) { setError((reason as Error).message); }
    finally { setRunning(false); }
  };

  const openRun = async (id: number) => {
    setError("");
    try { setDetail(await api<EvaluationRunDetail>(`/api/evaluations/runs/${id}`)); }
    catch (reason) { setError((reason as Error).message); }
  };

  const summary = detail?.summary ?? runs[0]?.summary ?? null;
  const graphData = runs.slice(0, 8).reverse().map((run) => ({
    run: `#${run.id}`,
    answer: (run.summary.answer_correctness ?? 0) * 100,
    retrieval: (run.summary.retrieval_relevance ?? 0) * 100,
  }));

  return (
    <div className="page-stack">
      <PageHeading eyebrow="QUALITY & RELIABILITY" title="Evaluations" description="Run the real 48-question NovaTech suite against the current documents, database, and agent. Scores are computed from observed answers and evidence." action={<button className="button button-primary" onClick={() => void runNow()} disabled={running || loading || !cases.length}>{running ? <LoaderCircle className="spin" size={15} /> : <FlaskConical size={15} />}{running ? "Running live suite…" : "Run evaluation"}</button>} />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {loading && <LoadingState />}
      {!loading && <>
        <section className="evaluation-banner"><div className="evaluation-banner-icon"><FlaskConical size={19} /></div><div><strong>{cases.length} evaluation cases</strong><span>RAG · SQL · calculations · cross-source · insufficient evidence · ambiguity · citations</span></div><span className="dataset-badge"><span />LIVE DATASET</span></section>
        {summary ? <section className="evaluation-metric-grid">
          <EvaluationMetric label="Answer correctness" value={summary.answer_correctness} help="Expected evidence terms present in the answer" color="#6272e9" />
          <EvaluationMetric label="Retrieval relevance" value={summary.retrieval_relevance} help="Retrieved passages aligned to case evidence" color="#36a98b" />
          <EvaluationMetric label="Citation correctness" value={summary.citation_correctness} help="Citations point to expected source files" color="#e9a14e" />
          <EvaluationMetric label="SQL correctness" value={summary.sql_correctness} help="Generated SQL validated and executed" color="#9b75d0" />
        </section> : <div className="panel no-evaluation"><div className="empty-icon"><FlaskConical size={20} /></div><strong>No evaluation run yet</strong><p>Run the suite to measure answer, retrieval, citation, SQL, and latency performance from real executions.</p></div>}
        <section className="evaluation-grid">
          <article className="panel evaluation-chart-panel"><div className="panel-heading"><div><div className="panel-title">Quality over runs</div><div className="panel-subtitle">Measured scores from completed evaluations</div></div><span className="panel-pill">ACTUAL RUNS</span></div>
            {graphData.length ? <div className="chart-wrap evaluation-chart"><Suspense fallback={<div className="loading-row"><span className="spinner" />Rendering chart…</div>}><EvaluationTrendChart data={graphData} /></Suspense></div> : <div className="chart-placeholder"><FlaskConical size={17} /><span>Scores will appear after the first evaluation run.</span></div>}
          </article>
          <article className="panel evaluation-history-panel"><div className="panel-heading"><div><div className="panel-title">Run history</div><div className="panel-subtitle">Persisted evaluation executions</div></div><button className="icon-button" onClick={() => void load()} aria-label="Refresh evaluations"><RefreshCw size={15} /></button></div>
            {runs.length ? <div className="evaluation-runs">{runs.map((run) => <button className={`evaluation-run ${detail?.id === run.id ? "active" : ""}`} key={run.id} onClick={() => void openRun(run.id)}><span className="run-status-icon"><CheckCircle2 size={16} /></span><span className="run-copy"><strong>Run #{run.id} · {run.total_cases} cases</strong><small>{formatDateTime(run.started_at)}</small></span><span className="run-score">{formatScore(run.summary.answer_correctness)}</span></button>)}</div> : <div className="empty-inline">Completed runs will be recorded here.</div>}
            {summary && <div className="run-details"><div><span>Mean latency</span><strong>{summary.average_latency_ms?.toLocaleString() ?? "—"} ms</strong></div><div><span>Mean token usage</span><strong>{summary.average_token_usage?.toLocaleString() ?? "Not available"}</strong></div></div>}
          </article>
        </section>
        {detail?.results && <section className="panel evaluation-results-panel"><div className="panel-heading"><div><div className="panel-title">Latest run results</div><div className="panel-subtitle">Case-level metrics from actual agent responses</div></div><span className="panel-pill">RUN #{detail.id} · {detail.total_cases} CASES</span></div>
          <div className="evaluation-results-list">{detail.results.slice(0, 12).map((result) => <EvaluationResultRow key={result.case_id} result={result} onViewSource={onViewSource} />)}</div>
        </section>}
      </>}
    </div>
  );
}

function EvaluationMetric({ label, value, help, color }: { label: string; value: number | null; help: string; color: string }) {
  return <article className="eval-metric"><div className="eval-metric-top"><span>{label}</span><span className="eval-metric-swatch" style={{ background: color }} /></div><strong>{formatScore(value)}</strong><div className="eval-progress"><span style={{ width: `${Math.min(100, Math.max(0, (value ?? 0) * 100))}%`, background: color }} /></div><small>{help}</small></article>;
}

function EvaluationResultRow({ result, onViewSource }: { result: EvaluationResult; onViewSource: (citation: Citation) => void }) {
  return <article className="evaluation-result-row"><div className="evaluation-result-main"><div className="result-id">{result.case_id}</div><div className="evaluation-question"><strong>{result.question}</strong><span>{result.category.replace(/_/g, " ")}</span></div><div className="eval-row-scores"><span>Answer <strong>{formatScore(result.answer_correctness)}</strong></span><span>Citations <strong>{formatScore(result.citation_correctness)}</strong></span><span>SQL <strong>{formatScore(result.sql_correctness)}</strong></span><span>{Math.round(result.latency_ms)} ms</span></div></div><details className="eval-answer-details"><summary>Inspect answer</summary><p>{result.answer}</p>{result.citations.map((citation, index) => <button key={`${citation.document_id}-${index}`} onClick={() => onViewSource(citation)}><FileText size={13} />{citation.filename}</button>)}</details></article>;
}

export function MonitoringView() {
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const [requests, setRequests] = useState<MonitoringRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [metrics, rows] = await Promise.all([
        api<MonitoringSummary>("/api/monitoring/summary"),
        api<MonitoringRequest[]>("/api/monitoring/requests?limit=100"),
      ]);
      setSummary(metrics);
      setRequests(rows);
    } catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  return (
    <div className="page-stack">
      <PageHeading eyebrow="OPERATIONS" title="Monitoring" description="Operational telemetry captured from actual chat and database requests. Queries are redacted before they are stored." action={<button className="button button-secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""} />Refresh</button>} />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {loading && <LoadingState />}
      {!loading && summary && <>
        <section className="metric-grid monitoring-metrics">
          <MetricCard label="Requests captured" value={summary.requests.toLocaleString()} detail="Chat and business-data queries" icon={Activity} accent="blue" />
          <MetricCard label="Average latency" value={`${summary.average_latency_ms.toLocaleString()} ms`} detail="End-to-end request time" icon={Clock3} accent="violet" />
          <MetricCard label="Evidence retrieved" value={summary.retrieved_chunks.toLocaleString()} detail="Cited chunks from RAG runs" icon={FileText} accent="teal" />
          <MetricCard label="Recorded errors" value={summary.errors.toLocaleString()} detail="Failed requests in telemetry" icon={ShieldCheck} accent="amber" />
        </section>
        <article className="panel telemetry-panel"><div className="panel-heading"><div><div className="panel-title">Recent requests</div><div className="panel-subtitle">Request ID · selected tools · timing · error state</div></div><span className="panel-pill">{requests.length} ROWS</span></div>
          {requests.length ? <div className="telemetry-table-wrap"><table className="data-table telemetry-table"><thead><tr><th>REQUEST</th><th>QUERY</th><th>TOOLS</th><th>RETRIEVAL</th><th>LLM</th><th>TOTAL</th><th>STATUS</th></tr></thead><tbody>{requests.map((request) => <tr key={`${request.request_id}-${request.timestamp}`}><td><code className="request-id">{request.request_id.slice(0, 14)}</code><small>{formatDateTime(request.timestamp)}</small></td><td className="telemetry-query">{request.query || "—"}{request.error && <small className="error-type">{request.error}</small>}</td><td><div className="telemetry-tools">{request.selected_tools.length ? request.selected_tools.map((tool) => <span className="tool-chip" key={tool}>{toolLabels[tool] ?? tool}</span>) : <span className="muted-cell">—</span>}</div></td><td>{Math.round(request.retrieval_latency_ms)} ms</td><td>{Math.round(request.llm_latency_ms)} ms</td><td><strong>{Math.round(request.total_latency_ms)} ms</strong></td><td><span className={`http-status ${request.status_code >= 400 ? "failed" : "success"}`}>{request.status_code}</span></td></tr>)}</tbody></table></div> : <div className="empty-panel"><div className="empty-icon"><Activity size={19} /></div><strong>No monitored requests yet</strong><p>Chat and database API calls will appear with measured latency and tool usage.</p></div>}
        </article>
        <div className="telemetry-note"><ShieldCheck size={14} /><span>Credentials and common secret patterns are redacted from stored query telemetry. Provider keys are never included.</span></div>
      </>}
    </div>
  );
}

export function SettingsView() {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [health, setHealth] = useState<{ status: string; dependencies: Record<string, string> } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [config, status] = await Promise.all([
        api<PlatformSettings>("/api/settings"),
        api<{ status: string; dependencies: Record<string, string> }>("/api/health"),
      ]);
      setSettings(config);
      setHealth(status);
    } catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  return (
    <div className="page-stack">
      <PageHeading eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Runtime status and safe configuration metadata. Secrets are never returned by the settings API." action={<button className="button button-secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={15} />Refresh status</button>} />
      {error && <ErrorBanner message={error} retry={() => void load()} />}
      {loading && <LoadingState />}
      {!loading && settings && <div className="settings-layout">
        <div className="settings-main">
          <article className="panel settings-panel"><div className="panel-heading"><div><div className="panel-title">AI providers</div><div className="panel-subtitle">Provider and model metadata from server configuration</div></div><Sparkles size={16} className="muted-icon" /></div>
            <div className="provider-row"><div className="provider-icon llm-provider"><Sparkles size={17} /></div><div className="provider-copy"><strong>Language model</strong><span>{settings.llm.provider}{settings.llm.model ? ` · ${settings.llm.model}` : " · evidence-only mode"}</span></div><span className={`config-state ${settings.llm.configured ? "ready" : "needs-config"}`}><span />{settings.llm.configured ? "Connected" : settings.llm.provider === "disabled" ? "Disabled" : "Needs API key"}</span></div>
            <div className="provider-row"><div className="provider-icon embed-provider"><Layers3 size={17} /></div><div className="provider-copy"><strong>Embedding model</strong><span>{settings.embeddings.provider} · {settings.embeddings.model}</span></div><span className={`config-state ${settings.embeddings.configured ? "ready" : "needs-config"}`}><span />{settings.embeddings.configured ? "Configured" : "Needs API key"}</span></div>
            <div className="provider-row"><div className="provider-icon vector-provider"><Database size={17} /></div><div className="provider-copy"><strong>Vector database</strong><span>{settings.vector_store} · document passage index</span></div><span className={`config-state ${health?.dependencies.vector_store === "ok" ? "ready" : "needs-config"}`}><span />{health?.dependencies.vector_store ?? "Unknown"}</span></div>
            <div className="provider-row"><div className="provider-icon database-provider"><Database size={17} /></div><div className="provider-copy"><strong>Relational database</strong><span>{settings.database} · business and operational records</span></div><span className={`config-state ${health?.dependencies.database === "ok" ? "ready" : "needs-config"}`}><span />{health?.dependencies.database ?? "Unknown"}</span></div>
          </article>
          <article className="panel settings-panel"><div className="panel-heading"><div><div className="panel-title">Security & indexing</div><div className="panel-subtitle">Active server-side safeguards</div></div><ShieldCheck size={16} className="muted-icon" /></div>
            <div className="setting-line"><div><strong>Maximum upload size</strong><span>Enforced on the API before file extraction</span></div><b>{settings.max_upload_mb} MB</b></div>
            <div className="setting-line"><div><strong>Passage chunk size</strong><span>Character window · overlap {settings.chunk_overlap}</span></div><b>{settings.chunk_size}</b></div>
            <div className="setting-line"><div><strong>Rate limit</strong><span>Per client IP · rolling in-memory window</span></div><b>{settings.rate_limit.requests} / {settings.rate_limit.window_seconds}s</b></div>
            <div className="setting-line"><div><strong>Supported source types</strong><span>Validated before indexing</span></div><b>{settings.allowed_file_types.join(" · ")}</b></div>
          </article>
        </div>
        <aside className="panel setup-panel"><div className="setup-icon"><ShieldCheck size={20} /></div><h3>Configure privately</h3><p>Provider credentials are read from your backend <code>.env</code> file and are never exposed to the browser.</p><div className="setup-step"><span>1</span><div><strong>Copy the example</strong><code>Copy-Item .env.example .env</code></div></div><div className="setup-step"><span>2</span><div><strong>Add approved provider keys</strong><small>Set LLM_API_KEY and EMBEDDING_API_KEY only when using hosted models.</small></div></div><div className="setup-step"><span>3</span><div><strong>Restart the API</strong><small>Provider status is reloaded from server configuration.</small></div></div><div className="setup-warning"><ShieldCheck size={14} />Never commit your .env file.</div></aside>
      </div>}
    </div>
  );
}

function formatCurrency(value: number) {
  if (!Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatScore(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
