# AI Mirror

Privacy-first, local-first personal second-brain and self-reflection engine. Ingests conversation history from every major AI platform, normalises it, builds a knowledge graph and embeddings, and delivers natural-language analysis of your own thinking.

> **Status:** Scaffolding complete. See `docs/SPEC.md` for the canonical product specification (v1.1).

## Quick start

```bash
cp .env.example .env
docker compose up --build backend neo4j
```

Backend API will be available at <http://localhost:8000>, OpenAPI docs at <http://localhost:8000/docs>, Neo4j browser at <http://localhost:7474>.

To enable the optional local-LLM profile:

```bash
docker compose --profile local-llm up
```

The frontend (built in Phase 2) lives under `./frontend` and runs on <http://localhost:5173>.

## Architecture

- **Backend** — FastAPI + SQLAlchemy 2.0 (async) + Alembic, SQLite as primary datastore.
- **Vector store** — ChromaDB (embedded, persisted to `./backend/data/chroma`).
- **Knowledge graph** — Neo4j Community via Bolt, with a SQLite triple-store fallback.
- **AI framework** — LlamaIndex for GraphRAG + structured JSON output.
- **LLM** — Configurable: OpenAI, Anthropic, or local Ollama.
- **Frontend** — React 19 + Vite + TypeScript + Tailwind + shadcn/ui (sci-fi HUD).

## Endpoints (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | Upload + parse exported conversation archives |
| POST | `/focus-lens` | Natural-language selective analysis |
| POST | `/reports/full-mirror` | Generate the comprehensive Full Mirror report |
| POST | `/reports/advanced-abstract` | Generate Advanced Abstract Analysis |
| GET  | `/dashboard/summary` | LAST MIRROR RUN panel + gauges |
| POST | `/chat/history` | Persistent GraphRAG chat over history |
| GET  | `/export-guide` | Latest export instructions (per-platform) |

See `/docs` (Swagger UI) on the running backend for full schemas.

## Project layout

```
ai-mirror/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/         # SQLAlchemy 2.0 models
│       ├── schemas/        # Pydantic v2 schemas
│       ├── routers/        # FastAPI routers (one per endpoint group)
│       ├── services/       # LLM, embeddings, KG, ingestion, reports
│       └── utils/
└── frontend/               # Phase 2 — React 19 HUD
```

## License

Personal use. Not for redistribution.
