import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Database,
  Files,
  FlaskConical,
  LayoutDashboard,
  MessageSquareText,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { api } from "./api";
import {
  ChatView,
  DashboardView,
  DatabaseView,
  DocumentsView,
  EvaluationsView,
  MonitoringView,
  SettingsView,
} from "./pages";
import type { Citation } from "./types";

type Section =
  | "Overview"
  | "Chat"
  | "Documents"
  | "Database"
  | "Evaluations"
  | "Monitoring"
  | "Settings";

const navigation: { label: Section; icon: LucideIcon; caption?: string }[] = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Chat", icon: MessageSquareText, caption: "Ask Nova" },
  { label: "Documents", icon: Files },
  { label: "Database", icon: Database },
  { label: "Evaluations", icon: FlaskConical },
  { label: "Monitoring", icon: Activity },
  { label: "Settings", icon: SettingsIcon },
];

export default function App() {
  const [activeSection, setActiveSection] = useState<Section>("Overview");
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [chatPrompt, setChatPrompt] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [source, setSource] = useState<Citation | null>(null);

  useEffect(() => {
    const check = () =>
      api<{ status: string }>("/api/health")
        .then((result) => setApiHealthy(result.status === "ok"))
        .catch(() => setApiHealthy(false));
    void check();
    const timer = window.setInterval(() => void check(), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setDocumentSearch("");
        setActiveSection("Documents");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const openChat = useCallback((prompt = "") => {
    setChatPrompt(prompt);
    setActiveSection("Chat");
  }, []);

  const openDocuments = useCallback((query = "") => {
    setDocumentSearch(query);
    setActiveSection("Documents");
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setActiveSection("Overview"); }}>
          <span className="brand-mark"><ShieldCheck size={19} strokeWidth={2.4} /></span>
          <span className="brand-copy"><strong>nova<span>tech</span></strong><small>INTELLIGENCE WORKSPACE</small></span>
        </a>

        <div className="workspace-switcher">
          <div className="workspace-avatar">N</div>
          <div className="workspace-copy"><strong>NovaTech</strong><span>Enterprise workspace</span></div>
          <span className="switcher-dots" aria-hidden="true">···</span>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon, caption }) => (
            <button
              key={label}
              className={`nav-item ${activeSection === label ? "active" : ""}`}
              onClick={() => setActiveSection(label)}
              aria-current={activeSection === label ? "page" : undefined}
            >
              <Icon size={17} strokeWidth={1.9} />
              <span>{caption ?? label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="secure-note"><span><ShieldCheck size={15} /></span><div><strong>Secure workspace</strong><small>Data stays under your control</small></div></div>
          <div className="profile-row">
            <div className="profile-avatar">NT</div>
            <div className="profile-copy"><strong>NovaTech team</strong><span>Workspace member</span></div>
            <span className={`presence-dot ${apiHealthy === false ? "offline" : ""}`} title={apiHealthy ? "API connected" : "API unavailable"} />
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-separator">/</span><strong>{activeSection}</strong></div>
          <div className="topbar-actions">
            <button className="global-search" onClick={() => openDocuments()} aria-label="Search documents">
              <Search size={15} /><span>Search your knowledge</span><kbd>⌘ K</kbd>
            </button>
            <span className={`connection-state ${apiHealthy === null ? "checking" : apiHealthy ? "connected" : "disconnected"}`}>
              <span className="connection-dot" />{apiHealthy === null ? "Connecting" : apiHealthy ? "All systems operational" : "API unavailable"}
            </span>
            <button className="help-button" onClick={() => setActiveSection("Settings")} aria-label="Open settings"><span>?</span></button>
          </div>
        </header>

        {apiHealthy === false && (
          <div className="api-warning" role="status">
            <span>The NovaTech API could not be reached.</span>
            <button onClick={() => setActiveSection("Settings")}>Check configuration <ArrowUpRight size={14} /></button>
          </div>
        )}

        <main className="page-content">
          {activeSection === "Overview" && <DashboardView onAsk={openChat} onSearch={openDocuments} />}
          {activeSection === "Chat" && <ChatView initialPrompt={chatPrompt} onPromptUsed={() => setChatPrompt("")} onViewSource={setSource} />}
          {activeSection === "Documents" && <DocumentsView initialSearch={documentSearch} onSearchUsed={() => setDocumentSearch("")} onViewSource={setSource} />}
          {activeSection === "Database" && <DatabaseView />}
          {activeSection === "Evaluations" && <EvaluationsView onViewSource={setSource} />}
          {activeSection === "Monitoring" && <MonitoringView />}
          {activeSection === "Settings" && <SettingsView />}
        </main>
      </div>

      {source && <SourceViewer citation={source} onClose={() => setSource(null)} />}
    </div>
  );
}

function SourceViewer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const [content, setContent] = useState<{ filename: string; chunks: { id: number; page: number | null; content: string }[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ filename: string; chunks: { id: number; page: number | null; content: string }[] }>(
      `/api/documents/${citation.document_id}/chunks`,
    )
      .then(setContent)
      .catch((reason: Error) => setError(reason.message));
  }, [citation.document_id]);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="source-dialog" role="dialog" aria-modal="true" aria-labelledby="source-title">
        <header className="dialog-header">
          <div className="dialog-file-icon"><Files size={17} /></div>
          <div><h2 id="source-title">{citation.filename}</h2><p>{citation.page ? `Page ${citation.page}` : "Source document"} · Evidence snippet</p></div>
          <button className="icon-button" onClick={onClose} aria-label="Close source viewer">×</button>
        </header>
        <div className="dialog-body">
          <div className="evidence-highlight"><span className="evidence-kicker">CITED PASSAGE</span><p>{citation.snippet}</p></div>
          {error && <div className="inline-error">{error}</div>}
          {!content && !error && <div className="loading-row"><span className="spinner" /> Loading source context…</div>}
          {content && (
            <div className="source-context">
              <div className="section-eyebrow">DOCUMENT CONTEXT <span>{content.chunks.length} indexed chunks</span></div>
              {content.chunks.map((chunk) => (
                <article className={`source-chunk ${chunk.content === citation.snippet ? "selected" : ""}`} key={chunk.id}>
                  <span>{chunk.page ? `Page ${chunk.page}` : `Passage ${chunk.id}`}</span><p>{chunk.content}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
