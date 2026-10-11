# Implementation plan

The following phases describe the completed portfolio implementation and the boundaries left for production hardening.

1. **Foundation and development stack** — FastAPI and React/Vite application structure, environment configuration, Docker Compose, and project documentation.
2. **Business data** — SQLAlchemy models, Alembic schema migration, idempotent seed routine, and consistent NovaTech customers, products, orders, sales, and revenue.
3. **Document ingestion** — PDF/DOCX/TXT/CSV validation, extraction, normalization, size limits, chunking, metadata persistence, duplicate detection, and deletion.
4. **Embeddings and retrieval** — local or OpenAI-compatible embedding provider, Qdrant adapter, persisted chunk metadata, retrieval/reranking, and citations.
5. **Chat and citations** — conversation persistence, evidence-focused answers, source viewer support, insufficient-evidence responses, and safe source/tool summaries.
6. **SQL and agent tools** — read-only NL-to-SQL flow, SQLGlot validation, guarded execution, arithmetic calculator, metadata search, and cross-source orchestration.
7. **Evaluation** — 48 categorized questions and persisted real-run results for keyword coverage, retrieval/citation checks, SQL safety, tool selection, latency, and provider-reported token use.
8. **Monitoring and security controls** — request identifiers, redacted request metrics, CORS, rate limiting, safe validation/unhandled errors, environment-based provider secrets, and bounded uploads/queries.
9. **Frontend and verification** — API-connected dashboard, chat, documents, database, evaluations, monitoring, and settings; backend/frontend automated tests; production frontend build; end-to-end local API verification; and documentation.

## Remaining production work

The local/default configuration intentionally optimizes for running the demo without credentials. Before production use, add authentication and authorization, tenant/document isolation, shared rate limits, durable ingestion workers, antivirus scanning, robust semantic evaluation with human-reviewed ground truth, managed secret and data-retention policies, and deployment-specific backups and observability.
