# VREDA.ai — Complete Project Memory

> Use this file to onboard a new Claude session. It contains everything needed to understand the codebase, architecture, patterns, and current state.

---

## 1. What is VREDA?

VREDA is the world's first **General-Purpose Scientific Operating System** — a multi-agent orchestrator that turns research papers into verified, executable experiments. Users upload a paper (or paste an arXiv ID), and the system runs a pipeline: **Parse → Hypothesize → Budget → Code → Execute → Verify**.

The product output is a **Discovery Pack**: a research manuscript + working code repo + verification log.

---

## 2. Repository Layout (Monorepo)

```
Verda/
├── apps/web/                    # Next.js 16 + React 19 — main product UI + API
├── services/hypothesis-room/    # Python FastAPI + LangGraph hypothesis engine
├── packages/contracts/          # Shared JSON schemas for inter-service APIs
├── scripts/dev-up.sh            # Starts both services together
├── docs/
│   ├── REPO_STRUCTURE.md        # Ownership rules, migration guide, room scaffold
│   └── hypothesis_pipeline.mmd  # Mermaid diagram of hypothesis flow
├── temp/
│   ├── dead-code/               # Archived old code
│   ├── placeholder-services/    # Stubs for coder-room, experiment-room, verifier-room
│   └── reference-docs/          # IMPROVEMENTS.md, PITCH.md, RESEARCH_REVIEW.md
├── ARCHITECTURE.md              # System architecture (primary reference)
├── README.md                    # Monorepo quickstart
├── ROADMAP.md                   # Phased build plan
├── SESSION_HANDOFF.md           # Last session's bug fix notes
├── .env.example                 # Env var template
└── .gitignore
```

---

## 3. apps/web — The Next.js Application

**Path**: `apps/web/` | **Package**: `vreda-app` v0.1.0 | **Port**: 3000

### Key Dependencies
| Package | Purpose |
|---------|---------|
| `next 16.1.6` + `react 19.2.3` | Framework |
| `@supabase/ssr` + `@supabase/supabase-js` | Auth, DB, Storage |
| `openai ^6.19.0` | All LLM calls (OpenAI-compatible APIs) |
| `@google/genai ^1.40.0` | Gemini embeddings (768-dim) |
| `zod ^4.3.6` | Agent output validation |
| `fast-xml-parser ^5.3.5` | arXiv Atom API parsing |
| `pdf-parse ^1.1.1` | PDF text extraction |
| `react-markdown` + `remark-gfm` | Markdown rendering |
| `lucide-react` | Icons |

### Build Commands
```bash
cd apps/web
npm run dev          # Dev server
npm run dev:clean    # Clean .next/dev then dev
npm run build        # Production build (must pass clean)
npm run lint         # ESLint
```

---

## 4. Source Tree — apps/web/src/

### API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/chat` | POST | Streaming chat with RAG context |
| `/api/conversations` | GET/POST | List/create conversations |
| `/api/conversations/[id]/messages` | GET | Messages for a quest |
| `/api/upload` | POST | PDF upload → full ingestion pipeline (NDJSON stream) |
| `/api/literature/search` | POST | Federated arXiv + Semantic Scholar search |
| `/api/literature/fetch` | POST | arXiv ID → download → ingestion pipeline |
| `/api/strategist/analyze` | POST | Re-run Parser + Scout |
| `/api/strategist/hypothesize` | POST | Run hypothesis pipeline (maxDuration 120s) |
| `/api/strategist/budget` | POST | Run Accountant agent |
| `/api/strategist/approve` | POST | Finalize manifest |
| `/api/strategist/session` | GET | Lookup session by conversation_id |
| `/api/auth/signup` | POST | Create account |

### UI Components (`src/components/chat/`)

| Component | Renders When `metadata.type` = |
|-----------|-------------------------------|
| `PaperAnalysisCard` + `CodePathCard` | `paper_analysis` |
| `HypothesisSelector` | `hypothesis_options` |
| `BudgetCard` | `budget_quote` |
| `ManifestCard` | `enhanced_manifest` |
| `PaperSearchCard` | `literature_search` |
| `PipelineProgressCard` | `pipeline_progress` |
| `MessageBubble` (plain markdown) | `text` or default |

Also: `ChatArea`, `ChatInput` (arXiv ID detection), `Sidebar`

### Core Libraries (`src/lib/`)

| Module | Purpose |
|--------|---------|
| `config.ts` | Centralized env var management (`requireEnv`/`optionalEnv`) |
| `errors.ts` | Custom errors: `VredaError`, `EmbeddingError`, `LLMError`, `ValidationError`, `StorageError`, `AgentError` |
| `logger.ts` | Structured JSON logger (no raw `console.log`) |
| `retry.ts` | `withRetry()` — exponential backoff |
| `validation.ts` | `validateUUID`, `validateMessage`, `validateFileUpload`, `validatePDFMagicBytes` |
| `openai-client.ts` | OpenAI client |
| `openrouter.ts` | OpenRouter client |
| `deepseek.ts` | DeepSeek client |
| `k2think.ts` | K2Think client |

### Agents (`src/lib/agents/`)

**Strategist Room** (`strategist-room/`):
- `index.ts` — Orchestrator with 4 stage functions
- `agent-call.ts` — `makeAgentCall<T>()`: multi-provider with fallback chain, Zod validation, auto-retry on schema failure
- `schemas.ts` — Zod schemas for all agent outputs (`AGENT_SCHEMAS` registry)
- `state.ts` — `createInitialState()`
- `fallback.ts` — Fallback outputs when agents fail
- `parser-agent.ts` — Structured paper extraction (temp 0.2)
- `scout-agent.ts` — Code path assessment: Path A (repo found) vs Path B (formula-to-code) (temp 0.2)
- `accountant-agent.ts` — Budget estimation (temp 0.2)

**Hypothesis Pipeline** (`strategist-room/hypothesis/`):
- `index.ts` — 5-stage: Gap → Generate → Critic → Revise → Rank
- `gap-detector.ts` — Finds research gaps from ResearchIntelligence
- `generator.ts` — Domain-aware, 10 hypothesis types, self-reflection loop (temp 0.7/0.5)
- `critic.ts` — Adversarial review, 6-dim scores (0-100), verdict: strong/viable/weak (temp 0.3)
- `ranker.ts` — Multi-dimensional composite scoring
- `types.ts` — Full type system

**Legacy**: `strategist.ts` — original single-prompt manifest + chat RAG

### Embeddings (`src/lib/embeddings/`)
- `index.ts` — Router: OpenAI (`text-embedding-3-large`) if key set, else Gemini
- `openai.ts` — OpenAI embeddings
- `gemini.ts` — `gemini-embedding-001` (768-dim via MRL, task-type aware)

### Literature (`src/lib/literature/`)
- `arxiv.ts` — arXiv Atom API (search + fetchByArxivId), rate-limited, 4 retries / 5s base
- `semantic-scholar.ts` — S2 search + getCitationGraph + recommendations
- `rate-limiter.ts` — Token bucket: arXiv 1/3s, S2 10/s, PwC 5/s, GitHub 1/60s or 5/s
- `types.ts` — `PaperMetadata`, `SearchResult`

### Research Intelligence (`src/lib/research-intelligence/`)
- `index.ts` — `gatherResearchIntelligence()`: parallel PwC + S2 + GitHub
- `papers-with-code.ts` — PwC API lookup by arXiv ID
- `github.ts` — GitHub REST API: repo metrics
- `citation-graph.ts` — S2: citation graph, recommendations, related papers

### Other
- `pdf/extract.ts` + `chunker.ts` — PDF extraction, 1500-char chunks with 200 overlap
- `pipeline/checkpoint.ts` — Fire-and-forget status updates to `documents.status`
- `supabase/admin.ts`, `client.ts`, `server.ts` — Supabase clients (admin/browser/SSR)

---

## 5. The Strategist Room Pipeline (Core Flow)

```
Upload/Fetch Paper
    │
    ▼
Stage 1: runInitialAnalysis()
    ├── Parser Agent → PaperAnalysis (title, authors, equations, datasets, claims)
    ├── gatherResearchIntelligence() → code repos, citation graph, related papers
    └── Scout Agent → CodePathAssessment (Path A: repo exists / Path B: write from scratch)
    │
    ▼
Stage 2: runHypothesisGeneration() — user triggers with message
    ├── Gap Detector → research gaps from intelligence
    ├── Generator → 5 hypotheses (domain-aware, self-reflection)
    ├── Critic → adversarial review, 6-dim scores
    ├── Revision → fix weak hypotheses
    └── Ranker → composite score sort
    │
    ▼
Stage 3: runBudgetEstimation() — user selects hypothesis
    └── Accountant Agent → BudgetQuote (tokens, compute, APIs, storage)
    │
    ▼
Stage 4: finalizeManifest() — user approves budget
    └── EnhancedResearchManifest (paper + hypothesis + budget + execution plan + risks)
```

### LLM Provider Priority Chain (web app)
OpenAI → DeepSeek → OpenRouter → K2Think (first with configured API key)

### Agent Temperature Settings
- Parser: 0.2 | Scout: 0.2 | Accountant: 0.2
- Generator: 0.7/0.5 | Critic: 0.3 | Brainstormer: 0.7

---

## 6. services/hypothesis-room — Python FastAPI Service

**Path**: `services/hypothesis-room/` | **Port**: 8000 | **Python**: >=3.12

**Status**: Built but NOT wired to the web app yet. Integration planned via `HYPOTHESIS_ENGINE_MODE=ts|python` flag.

### Endpoints
- `GET /healthz` — status + active providers
- `POST /generate` — accepts `{arxiv_id, pdf_path, config}`, returns NDJSON stream

### 7-Stage Pipeline
1. **Ingestion**: fetch arXiv PDF, PyMuPDF extract, chunk, LLM extract PaperSummary, init KnowledgeGraph
2. **Grounding**: S2 recommendations, PwC code lookup, LLM gap analysis, populate vector store
3. **Overgeneration**: 7 diversity tags × ~30 seeds ≈ 200 → cosine dedup → ~120 unique seeds
4. **Filtering**: parallel scoring (novelty + budget + verifiability) → top-K×5
5. **Refinement**: Proposer → Critic → Elo → MetaReviewer → Evolver (max 4 cycles, auto-converge)
6. **Tournament**: proximity-based Elo pairwise debates, 3 rounds
7. **Output**: top-K `EnhancedHypothesis` → `GeneratorOutput` JSON

### Tiered LLM Routing
| Tier | Role | Default Model |
|------|------|---------------|
| REASONING | Critic, Meta-Reviewer, Tournament | deepseek-r1-0528 |
| CREATIVE | Proposer, Evolver, Seeding | deepseek-v3 |
| FAST | Extraction, Filtering | gpt-4o-mini-ca |

### Local Dev
```bash
cd services/hypothesis-room
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python -m vreda_hypothesis.server  # http://localhost:8000
```

---

## 7. packages/contracts — Shared Schemas

JSON Schema contracts (versioned, additive-only for minor):
- `hypothesis-generate-request.v1.json`
- `hypothesis-generate-response.v1.json`
- `room-progress-event.v1.json` — `{type, step, message, current, total, data}`

---

## 8. Database Schema (Supabase + pgvector)

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `conversations` | id, user_id, title | Research quest sessions (RLS per user) |
| `messages` | id, conversation_id, role, content, metadata (JSONB) | Chat messages; `metadata.type` drives UI cards |
| `documents` | id, user_id, conversation_id, filename, storage_path, status | Uploaded PDFs; status tracks pipeline progress |
| `document_chunks` | id, document_id, content, embedding vector(768), chunk_index | Text chunks + embeddings for RAG |
| `strategist_sessions` | id, session_id, conversation_id, document_id, state (JSONB), phase | Full StrategistRoomState serialized |

SQL files: `apps/web/supabase/setup.sql`, `002_strategist_sessions.sql`, `003_hnsw_index.sql`

---

## 9. Environment Variables

```env
# Required
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# LLM Providers (at least one required)
OPENAI_API_KEY=              # Primary — also for embeddings
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
GEMINI_API_KEY=              # Fallback embeddings
OPENROUTER_API_KEY=
OPENROUTER_MODEL=deepseek/deepseek-r1:free
DEEPSEEK_API_KEY=
K2THINK_API_KEY=

# Optional
GITHUB_TOKEN=                # Raises GitHub API limit 60/hr → 5000/hr
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## 10. Key Patterns & Conventions

- **Path alias**: `@/*` → `./src/*`
- **App Router** (NOT Pages Router), server components by default
- **`"use client"`** only for interactive components
- **All env vars** via `config` from `src/lib/config.ts` (never raw `process.env`)
- **All logging** via `logger` from `src/lib/logger.ts` (never raw `console.log`)
- **All errors** use classes from `src/lib/errors.ts`
- **Retry-sensitive ops** use `withRetry()` from `src/lib/retry.ts`
- **NDJSON streaming** for upload and fetch pipelines (`PipelineProgressCard` renders live)
- **Graceful degradation**: Research Intelligence, Scout, Critic failures are non-fatal
- **Auth**: `middleware.ts` guards `/chat` routes → redirect to `/auth/login`
- **Supabase RLS** enforces per-user data isolation

---

## 11. Known Issues & Recent Fixes

### arXiv 429 Rate Limit (Fixed 2026-03-01)
**File**: `apps/web/src/lib/literature/arxiv.ts`
- **Bug**: `arxivLimiter.acquire()` was outside retry loop — retries fired without rate limiting
- **Fix**: Moved `acquire()` inside `withRetry()` callback; increased retries 2→4, baseDelay 3s→5s
- **Result**: Retry delays now 5s→10s→20s→40s

---

## 12. What's Built vs Not Built

| Component | Status |
|-----------|--------|
| Frontend (Next.js + chat UI) | Done |
| Auth + DB (Supabase) | Done |
| PDF upload + RAG pipeline | Done |
| Strategist Room (Parser, Scout, Brainstormer, Accountant) | Done |
| Enhanced Hypothesis Pipeline (TS) | Done |
| Literature APIs (arXiv + S2) | Done |
| Research Intelligence (PwC + GitHub + Citations) | Done |
| Python Hypothesis Service | Built, not integrated |
| Coder Room (E2B sandbox) | Not built (Phase 2B) |
| Experiment Room | Not built |
| Verifier Room (Z3/PINNs) | Not built |
| Multi-paper RAG | Not built |

---

## 13. Local Development

```bash
# Both services:
./scripts/dev-up.sh

# Web only:
cd apps/web && npm run dev

# Python hypothesis service:
cd services/hypothesis-room
source .venv/bin/activate
python -m vreda_hypothesis.server
```
