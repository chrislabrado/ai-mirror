# AI Mirror — Complete Project Specification (Kernel Version)

**Version:** 1.1 (May 17, 2026)
**Status:** FINAL — Use this document verbatim. Do not add, remove, or reinterpret any feature.

---

## 1. Project Overview & Vision

AI Mirror is a privacy-first, local-first personal second-brain / self-reflection engine.

It ingests conversation history from every major AI platform, normalises it, builds a knowledge graph + embeddings, and delivers powerful natural-language analysis of the user's own thinking patterns, strengths, weaknesses, psychology, neurodivergence signals, and aptitudes.

**Core Value:** Turn years of AI chats into evidence-based self-insight via comprehensive reports, selective Focus Lens queries, and interactive exploration.

**Non-Negotiable Principles:**

- Everything runs locally or self-hosted (Docker-compose preferred).
- Perfect symmetry, generous 32 px padding, calm breathing room.
- Premium sci-fi HUD visual style (deep navy/black + emerald-teal neon glows, holographic panels, faint data-grid overlay).
- No gamification mechanics (no XP, levels, streaks, badges, progress rings for accomplishments).
- Every analysis section is stored as reusable modular JSON blocks.

---

## 2. Visual & UI Design Principles

- **Aesthetic:** High-production sci-fi HUD (Deus Ex / Halo / Cyberpunk 2077 quality). Subtle neon glows on buttons and panels only.
- **Layout Rules:** Perfect left-right symmetry everywhere. One clear focal point per screen. Minimal top bar. Slim glowing left sidebar.
- **Tech:** React 19 + Vite + TypeScript + TailwindCSS + shadcn/ui. React Flow for graphs. React Markdown for reports.

---

## 3. Tech Stack (Exact)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 19 + Vite + TS + Tailwind + shadcn/ui | Dark mode only |
| Backend | FastAPI + SQLAlchemy 2.0 + Alembic | Async, Pydantic v2 |
| Primary DB | SQLite | Single file |
| Vector Store | ChromaDB (embedded) or LlamaIndex | Zero-config |
| Knowledge Graph | Neo4j Community (Docker) | Fallback: SQLite triples |
| AI Framework | LlamaIndex (preferred) or LangChain | GraphRAG + structured output |
| LLM | Configurable API keys + local Ollama fallback | JSON-mode required |
| Deployment | Docker-compose (local-first) | One-command run |

---

## 4. High-Level Architecture

See the Mermaid diagram from previous version — identical.

### Required Backend Endpoints (implement exactly):

- `POST /ingest`
- `POST /focus-lens`
- `POST /reports/full-mirror`
- `POST /reports/advanced-abstract`
- `GET  /dashboard/summary`
- `POST /chat/history`
- `GET  /export-guide` (static + dynamic content)

---

## 5. Data Model & Knowledge Graph

Keep the exact tables and KG node/relationship examples from previous spec.

**Tables (implemented):** `sources`, `conversations`, `messages`, `entities`, `relationships`, `reports`, `report_blocks`, `ingestion_jobs`.

---

## 6. Core Features (priority order)

### 6.1 Dashboard (Exact Layout)

**Left Sidebar Nav** (slim, glowing icons + labels):

- Dashboard
- History
- Insights
- Knowledge Graph
- Queries
- Focus Lens
- Export Guide ← NEW

**Main Content Area:**

- Top-right holographic panel: "LAST MIRROR RUN — [Date]" with 4–5 key bullets + three semi-circular speedometer gauges (Thought Clarity, Self-Reflection Depth, Aptitude Balance).
- Immediately below: Horizontal row of five large neon-bordered action buttons:
  1. 🔍 Full Mirror Analysis
  2. 🌐 Advanced Abstract Analysis
  3. 💬 Talk to My History
  4. 🔎 Focus Lens
  5. 📡 Refresh Insights

### 6.2 Full Mirror Analysis Report

Exact Markdown structure (enforce via structured LLM output).

### 6.3 Focus Lens

Natural-language selective analysis with parsed filters, hybrid retrieval, and structured Markdown output.

### 6.4 Other Core Screens

- Talk to My History (persistent GraphRAG chat)
- History Browser
- Knowledge Graph Explorer (React Flow)
- Insights Hub

### 6.5 Data Export Guide ← NEW

Nav item: "Export Guide" (icon: 📤). Page content lists exact 2026 steps per platform: ChatGPT, Claude, Grok, Gemini, Perplexity, Local Models. Each platform in an expandable accordion. Notes: "AI Mirror can ingest any of these exported JSON/ZIP files directly."

---

## 7. Implementation Instructions (Strict)

1. Build exactly as specified. Do not add extra features.
2. Start with docker-compose.yml + backend + SQLite models.
3. Then implement the React frontend with the exact sci-fi HUD dashboard.
4. Use structured JSON outputs for all LLM calls.
5. Store Full Mirror sections as modular JSON blocks.
6. Make the Export Guide static Markdown rendered beautifully in React.
7. Provide clear comments and separation of concerns.
