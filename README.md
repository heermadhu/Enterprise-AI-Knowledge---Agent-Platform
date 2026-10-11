# NovaTech AI Knowledge & Agent Platform

A full-stack enterprise knowledge workspace for evidence-backed answers across company documents and business data. The demo seeds a fictional NovaTech business, indexes its policy and reporting corpus, and exposes a tool-using assistant with citations, read-only SQL, calculations, evaluations, and request telemetry.

## Features

- **Documents and RAG:** Upload PDF, DOCX, TXT, or CSV files; extract and clean text; split it into metadata-bearing chunks; embed and index chunks in Qdrant; retrieve and rerank evidence; and return citations with filename, page when available, and snippet.
- **Business data:** PostgreSQL-backed customers, products, orders, sales, and monthly revenue, with an interactive database overview and natural-language query UI. The deterministic seed contains 120 customers, 20 products, 1,200 orders, and 12 months of internally consistent 2025 revenue.
- **Tool-using assistant:** Routes questions to document search, safe database queries, a calculator, and document metadata search. Multi-source questions can combine database comparisons, calculations, and report evidence. The UI receives tool/source summaries, not chain-of-thought.
- **Evaluation and monitoring:** Run a 48-case dataset covering document retrieval, SQL, calculations, cross-source answers, ambiguity, citations, and insufficient evidence. Persist run-level and case-level measurements, and inspect request latency, tools, retrieval counts, token use, status, and errors.
- **Workspace UI:** Dashboard, conversation history, chat with Markdown and citations, document upload/search/source viewer, database explorer, evaluation runs, monitoring, and settings.
- **Local-first defaults:** The app works without paid AI credentials using local hashing embeddings and an evidence-based extractive answer mode. An OpenAI-compatible LLM and embedding provider can be enabled with environment variables.

## Quick start with Docker Compose

Requirements: Docker Desktop with Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

- Web app: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>
- Qdrant dashboard: <http://localhost:6333/dashboard>

The Compose stack starts PostgreSQL, Qdrant, FastAPI, and the Vite development server. The backend runs the Alembic migration before starting. The sample PostgreSQL password in Compose is for local development only; replace it and other deployment credentials outside a local demo. Do not commit `.env`.

### Configure hosted AI (optional)

The defaults are `LLM_PROVIDER=disabled` and `EMBEDDING_PROVIDER=local`. To use an OpenAI-compatible provider, configure the provider, API key, model, and base URL in `.env`:

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=your-provider-key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=your-provider-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1
```

Use one embedding model consistently for indexing and retrieval. Restart the backend after changing providers or embedding models; it detects the embedding configuration signature in the vector index and rebuilds vectors from the source chunks in PostgreSQL. Never expose provider keys in the frontend.

## Local development without Docker

Requirements: Python 3.11+, Node.js 20.19+ (or 22.12+), and npm. For the simplest local run, use SQLite and in-memory Qdrant; neither requires a separate service.

In one terminal, from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
Set-Location backend
$env:DATABASE_URL = "sqlite+aiosqlite:///./novatech.db"
$env:QDRANT_URL = ":memory:"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The backend creates local development tables, seeds the business data and bundled documents, and rebuilds an empty in-memory vector index at startup.

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite serves the UI at <http://localhost:5173>; it calls the API at `http://localhost:8000` by default. Set `VITE_API_URL` if the API runs elsewhere. Local SQLite and in-memory Qdrant are development conveniences; use PostgreSQL and persistent Qdrant for a multi-process deployment.

## Architecture

```text
React + TypeScript + Vite
           |
           v
       FastAPI API
           |
    Agent/orchestrator
       /    |     \
 document   SQL   calculator
 search   query   and metadata
   |        |       |
 Qdrant  PostgreSQL |
   \        |      /
    citations + safe tool summary
```

The backend is divided into routers, ingestion, document/index services, embeddings/vector-store adapters, agent/tool orchestration, SQL validation/execution, database models, and telemetry. PostgreSQL stores application data and extracted document chunks; Qdrant holds searchable vectors and payload metadata. The default deterministic router selects tools without an LLM; when configured, the LLM can select tools and synthesize answers from returned evidence. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the component flow and trust boundaries.

### Bundled data

`data/documents/` contains internally consistent synthetic NovaTech financial reports, policies, product documentation, performance analysis, risk guidance, and an annual review. Seeded 2025 revenue is Q1 $1,295,000, Q2 $1,392,000, Q3 $1,497,000, and Q4 $1,670,000. August revenue is $525,000 and September is $472,000. The source reports describe known changes and operational context without asserting unsupported causal explanations.

## API overview

All application routes are under `/api`; interactive OpenAPI documentation is available at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | API and database/vector-store health |
| `GET` / `POST` / `DELETE` | `/api/documents` and `/api/documents/{id}` | List, upload, and delete indexed documents |
| `POST` | `/api/documents/search` | Retrieve evidence citations for a query |
| `GET` | `/api/documents/{id}/chunks` | View extracted source chunks |
| `GET` | `/api/documents/metadata/search?query=...` | Search document metadata |
| `POST` | `/api/chat` | Ask the agent; optionally continue with `conversation_id` |
| `GET` | `/api/conversations` and `/api/conversations/{id}` | List and load persisted chat history |
| `GET` | `/api/database/overview` | Seeded table counts and monthly revenue |
| `POST` | `/api/database/query` | Generate, validate, and execute read-only SQL |
| `GET` | `/api/evaluations/cases` | Inspect the evaluation dataset |
| `POST` / `GET` | `/api/evaluations/runs` | Run evaluations and list persisted runs |
| `GET` | `/api/evaluations/runs/{id}` | Read case-level results for one run |
| `GET` | `/api/monitoring/summary` and `/api/monitoring/requests` | Aggregated and per-request telemetry |
| `GET` | `/api/settings` | Safe, non-secret runtime configuration status |

Example chat request:

```json
{
  "query": "Why did September revenue fall compared with August?",
  "conversation_id": null
}
```

The response includes an answer, evidence citations, selected tools, generated SQL when applicable, request ID, and latency fields. The answer explicitly reports when the retrieved evidence is insufficient; it does not expose private model reasoning.

## SQL and security

- The SQL validator parses a single `SELECT`, restricts access to the five business tables, allows only approved functions, rejects mutations/DDL/system tables/locking/`SELECT INTO`, and imposes a 100-row maximum. PostgreSQL execution additionally sets the transaction read-only. SQLite is used only as a development backend and translates validated PostgreSQL SQL to its dialect.
- Uploads have an allowlist, a configurable size cap (20 MB by default), safe extraction, and duplicate-content handling. Source files are stored outside the frontend static tree.
- API inputs use Pydantic validation; CORS origins and rate limits are configurable; request IDs are returned; unhandled errors return a generic response; telemetry redacts common credential patterns and does not store provider secrets.
- The default rate limiter is in-memory and intended for a single-process demo. Production deployments need authentication/authorization, shared rate-limit storage, secret management, persistent backups, operational alerting, and a reviewed deployment configuration. The demo does not implement tenant isolation or user accounts.

## Tests and evaluations

Backend tests (from the repository root):

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Frontend tests and production build:

```powershell
Set-Location frontend
npm ci
npm test
npm run build
```

Run all 48 evaluation cases through the API:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/evaluations/runs `
  -ContentType "application/json" `
  -Body '{"limit":48}'
```

Scores are computed from actual agent executions and persisted responses, not seeded metric values. Answer correctness is expected-keyword coverage with normalized numeric matching; retrieval relevance measures expected-source precision, while citation correctness checks expected-source coverage; SQL correctness verifies that a generated query is present and passes the read-only validator; tool selection is overlap with expected tools. Latency is measured per run. Token usage is recorded only when the configured provider returns it. These are useful portfolio/demo signals, not a substitute for human-reviewed semantic or production quality evaluation.

## Limitations and future improvements

- The local embedding implementation is a lightweight deterministic hashing embedder, not a semantic embedding model; enable a compatible hosted embedding provider for stronger retrieval.
- Without an LLM provider, the system uses deterministic routing and extractive, citation-oriented answers. Hosted LLM mode is optional and depends on provider availability, credentials, and response behavior.
- The seeded dataset and source documents are fictional demonstration data; they are not representative of a production company corpus.
- Evaluation labels are heuristic and require human-reviewed gold answers for robust quality claims. Add semantic judges, graded relevance, SQL result assertions, and versioned evaluation reports before production use.
- Add identity, role/document-level authorization, tenant isolation, malware scanning, durable job queues for large ingestion workloads, shared rate limiting, deployment observability, and data-retention controls before exposing the service to real users or sensitive data.

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the delivery phases and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture details.
