# VREDA Architecture Guide

This document orients the founding team (you, Claude, and Codex) to the VREDA codebase as of **15 February 2026**. It captures what exists today, how a research quest flows through the system, and where the obvious gaps/opportunities sit so new engineers can ramp quickly.

---

## 1. Repository & Stack Inventory

| Path | Purpose |
| --- | --- |
| `/apps/web` | Next.js 16.1.6 application (React 19.2.3) that powers the entire product experience. |
| `/apps/web/src` | All application code: App Router pages, API routes, agents, libraries, types, components. |
| `/apps/web/supabase` | SQL migrations (tables, policies, indexes, storage bucket). |
| `/services/hypothesis-room` | Python service for advanced hypothesis generation (LangGraph + multi-agent loop). |
| Root docs (`RESEARCH_REVIEW.md`, `ROADMAP.md`, `ARCHITECTURE.md`, etc.) | Product direction + internal knowledge. |

Legacy path aliases (`/vreda-app`, `/vreda-hypothesis`) are retained as symlinks for compatibility.

**Tooling & Build**

* Package manager: npm (lockfile committed).
* TypeScript 5.x (`tsconfig.json`) and strict Next.js App Router.
* ESLint via `eslint-config-next` (Web Vitals + TypeScript) declared in `eslint.config.mjs`; Tailwind 4 beta through `@tailwindcss/postcss` plugin.
* `next.config.ts` lifts server body limit (`serverActions.bodySizeLimit = 50mb`) and whitelists `pdf-parse` for long-running PDF ingestion routes.

**Global Utilities** (all under `src/lib`):

* `logger.ts` – structured logger with JSON output in prod, console in dev.
* `retry.ts` – exponential backoff helper used for embeddings, GitHub/S2 calls, etc.
* `validation.ts` / `errors.ts` – shared ValidationError, AgentError, guard helpers used by every API route.
* `openrouter.ts`, `k2think.ts`, `config.ts` – centralized LLM client setup and env validation.
* `types/` – canonical domain models (`strategist`, `research-intelligence`, shared `MessageMetadata`) to keep UI, API, and agents aligned.

---

## 2. Runtime Architecture & User Flows

### Authentication & Routing

* `src/middleware.ts` wraps every route: unauthenticated users are redirected to `/auth/login`, authenticated users trying to hit `/auth/*` are bounced to `/chat`.
* Supabase SSR helpers (`lib/supabase/server.ts`) inject cookies so both server components and API routes can read/write authenticated sessions.
* `src/app/page.tsx` is a “smart redirect” that sends logged-in users straight to `/chat`, otherwise to `/auth/login`.

### Chat Experience (`src/app/chat/page.tsx`)

1. Client component bootstraps Supabase browser client, loads the logged-in user, and creates/loads conversations via `/api/conversations`.
2. Conversation switch triggers `fetchMessages` and strategist session restore via `/api/strategist/session` so UI cards (paper analysis, hypotheses, budgets) stay hydrated after refresh.
3. Messages stream in through `/api/chat`: server validates inputs, saves the user message, fetches limited conversation history, and streams OpenRouter/K2Think output as text while background-saving the assistant message. The client manages NDJSON-like progress objects for pipeline cards.

### Document Ingestion

There are two symmetric NDJSON pipelines, both emitting progress updates to the UI via `PipelineProgressCard` metadata.

1. **Manual PDF Upload** (`POST /api/upload`):
   1. Validate auth, file metadata, PDF magic bytes.
   2. Upload PDF to Supabase Storage bucket `Research-Paper` using the admin client.
   3. Insert a `documents` row (status `processing`).
   4. Extract text with `pdf-parse` (`lib/pdf/extract.ts`), sanitize it, and run semantic chunking (`lib/pdf/chunker.ts`).
   5. Batch-embed chunks through Gemini (`lib/embeddings/gemini.ts`) and persist embeddings in `document_chunks` (pgvector, 768 dims).
   6. Call `runInitialAnalysis` (Parser → Research Intelligence → Scout) plus `retrieveRelevantChunks` for context. Success stores a `strategist_sessions` snapshot and posts a `paper_analysis` message.
   7. Status checkpoints (`saveCheckpoint` / `markComplete`) update `documents.status` for observability.

2. **arXiv Fetch** (`POST /api/literature/fetch`): mirrors the upload flow but starts by pulling metadata from arXiv + Semantic Scholar, downloading the PDF directly, and then going through steps 2–7 above. It enforces valid IDs via `normalizeArxivId` and `validateUUID`.

Both pipelines degrade gracefully: embedding failures per chunk issue warnings, strategy agents are optional (e.g., research intelligence or scout can fail without aborting the entire ingest), and final `complete` events include whatever data exists.

---

## 3. Backend Services & API Surface

All routes live in `src/app/api`. Each uses Supabase SSR auth, shared validation, and the logger.

| Route | Description & Dependencies |
| --- | --- |
| `POST /api/chat` | Streams chat completions using `runChatQuery`. Requires an existing conversation, persists both user and assistant messages, chunk retrieval via `match_chunks`, uses OpenRouter → K2Think fallback. |
| `GET/POST /api/conversations` | CRUD for chat sessions; enforces per-user RLS. |
| `GET /api/conversations/[id]/messages` | Returns ordered messages with metadata for UI cards. |
| `POST /api/upload` | NDJSON PDF ingestion (see §2). Touches Storage, `documents`, `document_chunks`, embeddings, Strategist Room, and posts assistant messages. |
| `POST /api/literature/search` | Federated search across arXiv + Semantic Scholar with deduplication; no streaming, but non-fatal errors per source. |
| `POST /api/literature/fetch` | arXiv ingestion pipeline (see §2). |
| `POST /api/strategist/analyze` | Re-run Parser+Scout for an existing document, typically when initial analysis fails. |
| `POST /api/strategist/hypothesize` | Pulls strategist session state, assembles RAG context, invokes the Hypothesis Pipeline, saves new session state, and emits a `hypothesis_options` message. |
| `POST /api/strategist/budget` | Picked hypothesis → Accountant Agent → `budget_quote` message. |
| `POST /api/strategist/approve` | Finalizes the manifest, marks session approved, posts `enhanced_manifest`. |
| `GET /api/strategist/session` | Fetch latest strategist session id/phase for a conversation (used by chat client). |

**Patterns to note**

* All strategist endpoints require a valid `session_id` and reuse the JSON state blob stored on upload.
* Validation is defensive: `validateUUID`, `validateMessage`, PDF magic-byte checks, etc. Errors return structured 4xx responses; agent failures are logged but do not crash the process.
* Long-running endpoints (`upload`, `literature/fetch`, `strategist/hypothesize`) set `maxDuration` and stream NDJSON to keep the client responsive.

---

## 4. Data Layer & Persistence

Supabase migrations define the persistence story:

* `setup.sql` – conversations, messages, documents, document_chunks, pgvector index (`match_chunks` RPC), plus RLS policies per user.
* `002_strategist_sessions.sql` – stores full `StrategistRoomState` blobs, indexed by conversation/document, with RLS ensuring users can only read/update their sessions.
* `003_hnsw_index.sql` – replaces IVFFlat with `hnsw` for higher-recall similarity search (cosine) on `document_chunks.embedding`.
* `storage.sql` – private bucket `Research-Paper` and policies allowing users to manage only their own folders.

**Key domain tables**

* `conversations`, `messages` – chat history + metadata powering cards (`MessageMetadata.type`).
* `documents` – ingestion lifecycle. `status` is overloaded to hold checkpoints (`processing:chunk`, `error:embed`, etc.).
* `document_chunks` – pgvector embeddings (768-d) created via Gemini using `batchEmbedTexts`.
* `strategist_sessions` – serialized `StrategistRoomState` JSONB. Session state ensures the hypothesis/budget/manifest chain survives reloads.

---

## 5. AI Agents & Pipelines

### Legacy Strategist Agent

* Found in `src/lib/agents/strategist.ts`. Retrieves paper chunks, feeds them into a single prompt (`STRATEGIST_SYSTEM_PROMPT`/`USER_PROMPT`), and expects a JSON “Research Manifest.” This pathway still powers the general `/api/chat` responses when no Strategist Room session exists.

### Strategist Room (Multi-Agent)

Entry point: `src/lib/agents/strategist-room/index.ts`.

1. **Parser Agent** (`parser-agent.ts`) – structured extraction of title, claims, datasets, hallucination risk. Validated against `PaperAnalysisSchema`.
2. **Research Intelligence** (`lib/research-intelligence`) – merges Papers With Code, GitHub metrics, Semantic Scholar citation graph + recommendations.
3. **Scout Agent** (`scout-agent.ts`) – code path assessment (Path A reuse vs Path B build). Uses real repo metrics when available.
4. **Hypothesis Pipeline** (`hypothesis/index.ts`):
   * Gap Detector (optional, uses research intelligence data).
   * Generator (`hypothesis/generator.ts`) – domain-aware types, reflection rounds, composite scoring.
   * Critic (`hypothesis/critic.ts`) – independent low-temp review attaching feasibility + verdicts.
   * Optional revision loop if critic requests changes.
   * Ranker (`hypothesis/ranker.ts`) – reconciles critic feedback into final ordering with rationale.
5. **Accountant Agent** (`accountant-agent.ts`) – token/compute/API/storage budget, free-tier warnings, contingency.
6. **Manifest Finalization** – composes Enhanced Research Manifest combining hypothesis, code path, execution steps, and risk assessment.

**Agent Infrastructure**

* All agents use `makeAgentCall`: OpenRouter (default `google/gemini-2.0-flash-001`) with automatic fallback to K2 Think if configured.
* Uses `response_format: json_object` plus Zod schemas (`strategist-room/schemas.ts`) to validate outputs. Schema violations trigger an automatic “fix prompt” retry.
* Contextual metadata (documentId, hypothesisId, phase) is logged for traceability.

---

## 6. External Integrations & Configuration

`src/lib/config.ts` enforces required environment variables at import time:

| Key | Purpose |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase client (browser + server) and admin operations. |
| `GEMINI_API_KEY` | Google GenAI embeddings + (optionally) LLM calls. |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Primary LLM provider for agents/chat (default Gemini Flash). |
| `K2THINK_API_KEY`, `K2THINK_MODEL` | Optional fallback LLM. |
| `K2THINK_BASE_URL` (hard-coded) | Provided inside config for completeness. |
| `GITHUB_TOKEN` | Raises GitHub rate limits for repo metrics (optional). |
| `NEXT_PUBLIC_APP_URL` | Used for OpenRouter HTTP headers. |

**External APIs**

* Supabase Storage + Postgres (vector search, RPC `match_chunks`).
* Google GenAI (Gemini embeddings) via `@google/genai`.
* OpenRouter + K2 Think for all structured agent calls.
* arXiv + Semantic Scholar for literature search/fetch (rate limited via token buckets in `literature/rate-limiter.ts`).
* Papers With Code (code discovery) and GitHub REST API (repo health metrics).

Rate limiting uses local token buckets (arXiv 1/3s, Semantic Scholar 10/s, PWC 5/s, GitHub adaptive) plus `withRetry` wrappers for resiliency.

---

## 7. Observability, Reliability & Known Gaps

**Observability & Safety Nets**

* `logger` standardizes INFO/WARN/ERROR, injecting context (documentId, sessionId, stages) across agents, embeddings, and API routes.
* `withRetry` logs transient failures and retries with exponential backoff for all external calls (embeddings, GitHub, Semantic Scholar, LLMs).
* `pipeline/checkpoint.ts` annotates `documents.status` at every major ingest step, enabling UI or dashboards to show precise stuck states.
* Each agent stage catches and records non-fatal errors directly onto `StrategistRoomState.errors`, surfacing them via future cards.

**Graceful Degradation Examples**

* Research Intelligence or Scout failure logs warnings but still returns parser data so the user can continue.
* Hypothesis pipeline continues even if critic or ranker fail, falling back to composite-score sorting.
* NDJSON pipelines send `warning` events for partial embedding failures instead of aborting uploads.

**Known Gaps / Next Opportunities** (summaries from `RESEARCH_REVIEW.md`)

1. **Hypothesis Quality Metrics** – add explicit novelty/feasibility scoring loop (e.g., SPECTER2 embeddings, SciMON-style iteration) beyond current critic heuristics.
2. **Multi-Paper Context** – expand Strategist Room to reason across citation neighborhoods, not just a single uploaded paper.
3. **RAG Upgrades** – adopt semantic/vision-guided chunking, scientific embedding models, and cross-document retrieval to reduce hallucinations.
4. **Verification Layer** – implement anti-gravity/physics verification agent that reasons over outputs before approval, closing the “no verification” gap.

---

## 8. Open Questions & Next Steps

1. **Who owns multi-paper graph work?** Need a design for storing/reusing related papers per conversation.
2. **Execution layer** – Architect the downstream “Coder Room” executor to consume the Enhanced Manifest (currently not implemented here).
3. **Monitoring dashboards** – Would a Supabase-based status board or Vercel logging integration help us see stuck documents faster?
4. **Config management** – Consider migrating secrets to a unified `.env.example` and adding smoke tests that ensure every required env is present before deploy.

This guide should evolve with the product. When major architectural changes land (new agents, new queues, etc.), update the relevant sections so future contributors can keep pace.
