# Architecture

## Request and evidence flow

```text
React/TypeScript UI
       | JSON and multipart HTTP
       v
FastAPI routers ── request IDs, validation, CORS, rate limiting, error boundaries
       |
       v
Agent/orchestrator ── deterministic routing by default; optional OpenAI-compatible tool selection
       |
       +── document_search ── query embed → Qdrant candidates → lexical/semantic rerank
       |                         └─ citations: filename, page, snippet
       +── database_query ── NL-to-SQL → SQLGlot validation → read-only execution
       +── calculator ── restricted arithmetic expressions
       └── document_metadata_search ── PostgreSQL metadata lookup
                  |
         safe synthesis from tool outputs
            /                       \
   PostgreSQL + Alembic          Qdrant
```

The routers are in `backend/app/routers`. Agent and business-tool behavior live in `agent.py` and `business_tools.py`; document extraction, chunking, persistence, retrieval, and indexing are separated into `ingestion.py`, `document_service.py`, `embeddings.py`, and `vector_store.py`. SQLAlchemy models and seed routines own business and application records. The React client calls the API through one shared API module.

## Data lifecycle

1. On startup, development mode creates missing tables; deployment migrations are managed by Alembic. The idempotent seed routine creates the NovaTech sample business and imports bundled text sources.
2. Upload endpoints enforce file type and byte-size limits before extraction. Extracted text is normalized, split into overlapping chunks, stored with document/page/index metadata, embedded, and upserted into Qdrant.
3. Retrieval embeds the question, gathers vector candidates, reranks with lexical and semantic signals, and returns bounded source snippets. The agent includes only retrieved snippets as answer evidence.
4. Qdrant can be configured for in-memory local use or a persistent service. At startup, the app rebuilds an empty or incomplete vector index from persisted PostgreSQL chunks.
5. Evaluation runs persist per-case inputs, outputs, citations, selected tools, score components, latency, and token usage when returned by the provider. Chat/database requests persist redacted operational metrics.

## Agent and SQL trust boundaries

The assistant can return tool names and source summaries but not chain-of-thought. Deterministic local routing supports the core demo without a model credential; an optional OpenAI-compatible provider can select tools and synthesize evidence. Missing or insufficient evidence must remain explicit rather than being filled with invented facts.

Generated SQL is untrusted input even when supplied by the model. The server parses exactly one statement, permits only a `SELECT` over `customers`, `products`, `orders`, `sales`, and `monthly_revenue`, rejects system tables, mutations, DDL, lock clauses, `SELECT INTO`, and unapproved functions, and caps output at 100 rows. PostgreSQL transactions are set read-only before execution. SQLite development execution transpiles the already-validated query to SQLite syntax.

The calculator accepts a deliberately narrow arithmetic grammar rather than Python evaluation. User-controlled inputs are length-validated, and upload parsing is isolated from static frontend content. Provider credentials are read server-side from environment settings, never returned by the settings endpoint, and never logged as configuration values.

## Operations and deployment boundaries

Docker Compose provides PostgreSQL, Qdrant, FastAPI, and the Vite development server. The API uses the initial Alembic migration before startup in Compose; local SQLite development can create tables on startup. The default local embedding mode is deterministic hashing for portability, not a semantic production embedding model. In-memory rate limiting, absent authentication/tenant authorization, and development-oriented Compose settings mean the repository is a portfolio/demo system, not a production deployment blueprint.

Production hardening should add authentication and document-level authorization, tenant isolation, shared rate limiting, persistent backup/restore, ingestion queues and malware scanning, retention controls, and deployment-specific secret management and observability.
