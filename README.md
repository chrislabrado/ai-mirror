# AI Mirror

Privacy-first, local-first personal second-brain and self-reflection engine. It ingests your conversation history from every major AI platform (or pulls it itself from local sources), normalises it, builds temporal tables + a knowledge graph + embeddings, and delivers **evidence-verified, adversarially-reviewed** analysis of your own thinking.

> **Status:** v2 — this repo is the actual running system, not a build spec. The original
> spec-kernel that seeded v1 is preserved at `docs/SPEC.md`; the v2 design rationale is
> `docs/DESIGN-V2_2026-07-02.md`.

## Why v2 exists

v1's analysis was a single LLM call over recent messages: it could flatter, it could invent
"evidence," and when challenged it had nothing to stand on. v2 makes both failure modes
structural non-options:

- **Grounded claims.** Every report block carries claims with evidence quotes citing real
  message ids. The backend verifies each quote against the actual message row; invented
  quotes are discarded and the claim is demoted and tagged `ungrounded`. Evidence chips in
  the UI link to the real conversation.
- **Adversarial review.** A second, independent LLM pass tries to *refute* the draft —
  sycophancy, overreach, unsupported psychology, tone drift. Its verdicts ship with the
  report as a first-class "Adversarial Review" block, and high-severity objections demote
  the claims they hit. Register contract: candid, warm-neutral, evidence-first.
- **Temporal engine.** Deterministic monthly epoch tables (SQL, no LLM) + cached LLM epoch
  profiles + synthesized trajectories where extrapolated points are explicitly marked
  `SYNTHETIC` with confidence bands. Growth claims reason from the tables, not vibes.
- **Meta-analysis.** Compare mirror runs over time: stable traits (test-retest), genuine
  change, and narrative variance (model noise dressed as change).
- **Unrealized opportunities.** Dropped threads (conversations that ended on your open
  question), aptitudes never exploited, cross-domain transfer you haven't made.
- **Honest empty states.** No LLM configured → an explicit NOT-ANALYZED banner, never
  placeholder prose styled like insight.

## Fable mode (tiered models)

`FABLE_MODE=true` (or `{"fable": true}` per request) routes **scaffold** work
(conversation summaries, epoch profiles, KG extraction) to a fast model and **hard** work
(report synthesis, trajectories, meta-analysis, the adversarial critique) to the strongest
one:

| tier | default model |
|---|---|
| scaffold | `claude-sonnet-4-6` |
| hard | `claude-fable-5` |

Configurable via `SCAFFOLD_MODEL` / `HARD_MODEL`. Off → single `LLM_MODEL` everywhere.

## LLM providers

`claude_cli` (default) shells out to a local `claude` binary — subscription OAuth, zero API
keys on disk, fully local-first. Also supported: `anthropic`, `openai`, `grok`/`xai`,
`ollama` (local models).

## Remote input extraction

The system can pull its own inputs — no manual export/upload:

```bash
curl -X POST localhost:8000/ingest/remote -H 'Content-Type: application/json' \
  -d '{"connector": "claude_code", "limit": 50}'
```

Connectors: `claude_code` (`~/.claude/projects/**/*.jsonl`), `openclaw` (OpenClaw v3
session logs), `path` (any directory **under the `INGEST_ALLOWED_ROOTS` allow-list** —
anything outside is rejected). Manual exports still work via `POST /ingest` for ChatGPT,
Claude, Grok, Gemini, Perplexity, and local models.

## Quick start (native, local-first)

```bash
cp .env.example .env                      # default provider: claude_cli
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# in another shell:
cd frontend && npm install && npm run dev # http://localhost:5173
```

Docker (API-key providers; the `claude_cli` provider needs the native run):

```bash
docker compose up --build backend
docker compose --profile frontend up     # optional UI container
docker compose --profile neo4j up        # optional graph mirror
docker compose --profile local-llm up    # optional Ollama
```

## Endpoints (v2)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | Upload + parse exported conversation archives |
| POST | `/ingest/remote` | Pull inputs from local sources (allow-listed roots) |
| POST | `/reports/full-mirror` | Full Mirror report — claims, verified evidence, critique |
| POST | `/reports/advanced-abstract` | Abstract synthesis (same grounding contract) |
| POST | `/reports/meta-analysis` | Compare the last N mirror runs |
| POST | `/focus-lens` | Natural-language selective analysis |
| GET  | `/temporal/epochs` | Deterministic epoch tables + LLM epoch profiles |
| POST | `/temporal/refresh` | Recompute stats, profile new epochs |
| POST/GET | `/temporal/trajectories` | Synthesize / fetch observed+extrapolated series |
| GET  | `/dashboard/summary` | Last-run panel + gauges |
| POST | `/chat/history` | Chat over your history (vector retrieval) |
| GET  | `/export-guide` | Per-platform export instructions |

Full schemas: Swagger UI at `/docs` on the running backend.

## Architecture

- **Backend** — FastAPI + SQLAlchemy 2.0 (async) + SQLite. Analysis engine v2 in
  `backend/app/services/analysis_v2.py` (grounding gate, corpus assembly, critique,
  meta-analysis) and `temporal.py` (epoch stats/profiles/trajectories).
- **Vector store** — ChromaDB embedded (bundled local embedding model).
- **Knowledge graph** — SQLite triples (Neo4j optional write-mirror).
- **Frontend** — React 19 + Vite + TS + Tailwind, sci-fi HUD. Claims, confidence badges,
  verified-evidence links, critique panel, trajectory sparklines (observed solid /
  synthetic dashed + band).

## License

Personal use. Not for redistribution.
