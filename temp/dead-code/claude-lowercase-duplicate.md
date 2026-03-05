# VREDA.ai — The Scientific Operating System

> "The human provides the **curiosity**, the AI provides the **completion**."

## Mission
Build the world's first General-Purpose Scientific Operating System — a universal "Compiler" for the Scientific Method that turns any research inquiry into an Autonomous Quest: **Ideation -> Budgeting -> Execution -> Verification -> Discovery.**

## The Problem We Solve
Researchers spend ~70% of their time on low-value execution: literature cross-referencing, debugging environments, writing boilerplate simulation code, manually verifying data. VREDA eliminates this by automating the full Science-to-Code pipeline.

## The Product: "Discovery Pack"
Users don't get a chat message. They get a **Verified Artifact Bundle**:
- **The Manuscript** — AI-generated, human-readable research report
- **The Code Repo** — Fully functional, bug-free experiment code
- **The Verification Log** — Certificate showing how physics/logic was validated

---

## Core Architecture: The "Four Rooms" Pipeline

VREDA is a **Multi-Agent Orchestrator** — specialized agents that check each other's work.

### Room 1: The Strategist (Reasoning & Budgeting)
- Decomposes macro research goals into micro execution steps
- Generates a Research Manifest with methodology, key findings, hypotheses
- **Status**: BUILT — `src/lib/agents/strategist.ts` + `src/lib/agents/prompts.ts`

### Room 2: The Librarian (Literature & Knowledge)
- Scans 200M+ papers (Semantic Scholar API, arXiv)
- Extracts protocols and parameters into machine-readable JSON
- **Status**: PARTIAL — RAG over uploaded PDFs works; literature API search NOT yet built
- Files: `src/lib/embeddings/gemini.ts`, `src/lib/pdf/extract.ts`, `src/lib/pdf/chunker.ts`

### Room 3: The Coder & Executor (The Sandbox)
- Writes code (Python, C++, Julia) to run experiments
- Executes in secure cloud sandbox (E2B)
- Self-corrects: reads errors and fixes autonomously (LangGraph write->run->fix loop)
- **Status**: NOT YET BUILT — Phase 3 milestone

### Room 4: The Verifier (The Scientific Judge)
- Validates results against First Principles (Conservation of Energy, Big-O, Chemical Valence)
- Uses LLM-based structured checks first, Z3/PINNs later
- **Status**: NOT YET BUILT — Phase 4 milestone

---

## Current Tech Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| **Frontend** | Next.js 16 + React 19 + TypeScript 5 | Working |
| **Styling** | Custom CSS (dark theme) | Working |
| **Auth & DB** | Supabase (PostgreSQL + pgvector) | Working |
| **Embeddings** | Google Gemini API (`gemini-embedding-001`, 768-dim via MRL) | Working |
| **Embedding SDK** | `@google/genai` v1.40.0 | Working |
| **Fast LLM** | Gemini 2.0 Flash (via OpenRouter) | Working |
| **Config** | Centralized `src/lib/config.ts` with `requireEnv()` | Working |
| **Error Handling** | Custom error classes in `src/lib/errors.ts` | Working |
| **Logging** | Structured JSON logger in `src/lib/logger.ts` | Working |
| **Retry** | Exponential backoff in `src/lib/retry.ts` | Working |
| **Validation** | UUID, message, file validation in `src/lib/validation.ts` | Working |
| **Orchestration** | LangGraph | Not yet integrated |
| **Code Execution** | E2B Sandbox API | Not yet integrated |
| **Literature APIs** | Semantic Scholar + arXiv (`src/lib/literature/`) | Working |
| **Verification** | Z3 / PINNs | Not yet integrated |

---

## Project Structure

All code lives in `vreda-app/`:

```
vreda-app/src/
├── app/                          # Next.js App Router
│   ├── api/
│   │   ├── chat/route.ts         # Streaming chat with RAG + Strategist
│   │   ├── conversations/
│   │   │   ├── route.ts          # GET/POST conversations
│   │   │   └── [id]/messages/route.ts  # GET messages for a quest
│   │   ├── literature/
│   │   │   ├── search/route.ts   # POST — search arXiv + Semantic Scholar
│   │   │   └── fetch/route.ts    # POST — fetch paper by arXiv ID → full pipeline
│   │   ├── strategist/
│   │   │   ├── analyze/route.ts  # POST — re-run Parser + Scout
│   │   │   ├── hypothesize/route.ts  # POST — run Brainstormer
│   │   │   ├── budget/route.ts   # POST — run Accountant
│   │   │   └── approve/route.ts  # POST — finalize manifest
│   │   └── upload/route.ts       # PDF upload + processing pipeline
│   ├── auth/
│   │   ├── login/page.tsx        # Login page
│   │   └── signup/page.tsx       # Signup page
│   ├── chat/page.tsx             # Main chat interface
│   ├── layout.tsx                # Root layout
│   └── page.tsx                  # Landing / redirect
├── components/chat/
│   ├── ChatArea.tsx              # Main chat display area
│   ├── ChatInput.tsx             # Message input + file upload + arXiv ID detection
│   ├── ManifestCard.tsx          # Research Manifest display (legacy)
│   ├── MessageBubble.tsx         # Individual message rendering (dispatches to cards)
│   ├── PaperAnalysisCard.tsx     # Parser + Scout output display
│   ├── CodePathCard.tsx          # Code path assessment (Path A/B)
│   ├── HypothesisSelector.tsx    # 3 hypothesis cards with select/refine
│   ├── BudgetCard.tsx            # Budget breakdown with approve button
│   ├── PaperSearchCard.tsx       # Literature search results with import
│   └── Sidebar.tsx               # Conversation list + nav
├── lib/
│   ├── agents/
│   │   ├── strategist.ts         # Original strategist (manifest + chat query)
│   │   ├── prompts.ts            # System prompts for chat agent
│   │   └── strategist-room/      # Multi-agent orchestrator
│   │       ├── index.ts          # Orchestrator entry points
│   │       ├── agent-call.ts     # Shared makeAgentCall<T>() utility
│   │       ├── state.ts          # Session state factory
│   │       ├── parser-agent.ts   # Extract paper structure
│   │       ├── scout-agent.ts    # Detect code availability
│   │       ├── brainstormer-agent.ts  # Generate hypotheses
│   │       ├── accountant-agent.ts    # Estimate budget
│   │       └── prompts/          # Per-agent system prompts
│   ├── embeddings/
│   │   └── gemini.ts             # Gemini embedding (task-type aware)
│   ├── literature/               # Literature API clients
│   │   ├── index.ts              # Barrel exports
│   │   ├── arxiv.ts              # arXiv API (search + fetch by ID)
│   │   ├── semantic-scholar.ts   # Semantic Scholar API (search + get)
│   │   ├── rate-limiter.ts       # Token bucket rate limiters
│   │   └── types.ts              # PaperMetadata, SearchResult types
│   ├── pdf/
│   │   ├── extract.ts            # PDF text extraction
│   │   └── chunker.ts            # Text chunking (1000 chars, 200 overlap)
│   ├── supabase/
│   │   ├── admin.ts              # Admin client (bypasses RLS)
│   │   ├── client.ts             # Browser client
│   │   └── server.ts             # Server-side client
│   ├── config.ts                 # Centralized env var management
│   ├── errors.ts                 # Custom error classes (incl. AgentError)
│   ├── logger.ts                 # Structured logger
│   ├── openrouter.ts             # OpenRouter API client
│   ├── retry.ts                  # Generic retry with exponential backoff
│   └── validation.ts             # Input validation utilities
├── types/
│   ├── index.ts                  # Core types + re-exports
│   └── strategist.ts             # Strategist Room types
└── middleware.ts                 # Auth route protection
```

Root-level files:
```
Verda/
├── claude.md                     # This file — project source of truth
├── ROADMAP.md                    # Detailed phased build plan
├── PITCH.md                      # Startup pitch and vision
├── .gitignore                    # Git ignore rules
├── .env.example                  # Environment variable template
└── vreda-app/                    # Application code
```

---

## Database Schema (Supabase)

| Table | Purpose |
|-------|---------|
| `conversations` | Research Quest sessions per user |
| `messages` | Chat messages with role/content/metadata |
| `documents` | Uploaded PDFs with processing status |
| `document_chunks` | Text chunks + vector embeddings (768-dim, HNSW index) for RAG |
| `strategist_sessions` | Strategist Room state (JSONB) per document |

## API Endpoints

| Endpoint | Method | Purpose | Validation |
|----------|--------|---------|------------|
| `/api/chat` | POST | Streaming chat with RAG context | UUID, message length (10k max) |
| `/api/conversations` | GET | List user's conversations | Auth via Supabase RLS |
| `/api/conversations` | POST | Create new conversation | Auth via Supabase RLS |
| `/api/conversations/[id]/messages` | GET | Get messages for a quest | UUID format check |
| `/api/upload` | POST | Upload and process PDF | File type, size (50MB), magic bytes |
| `/api/strategist/analyze` | POST | Re-run Parser + Scout | Session ID |
| `/api/strategist/hypothesize` | POST | Run Brainstormer | Session ID, message |
| `/api/strategist/budget` | POST | Run Accountant | Session ID, hypothesis ID |
| `/api/strategist/approve` | POST | Finalize manifest | Session ID |
| `/api/literature/search` | POST | Search arXiv + Semantic Scholar | Query string, auth |
| `/api/literature/fetch` | POST | Fetch paper by arXiv ID → full pipeline | arXiv ID, conversation ID |

---

## Build Progress

### Phase 0: Security Emergency — COMPLETE
- [x] Deleted test files with hardcoded API keys
- [x] Fixed storage bucket (public -> private)
- [x] Removed `dangerouslyAllowBrowser: true` from OpenRouter client
- [x] Removed random vector fallback from embeddings (throws error instead)
- [x] Created `.env.example`

### Phase 1: Foundation Hardening — COMPLETE
- [x] Root-level git repository initialized
- [x] Centralized config (`src/lib/config.ts`)
- [x] Custom error classes (`src/lib/errors.ts`)
- [x] Structured logger (`src/lib/logger.ts`)
- [x] Generic retry utility (`src/lib/retry.ts`)
- [x] Input validation (`src/lib/validation.ts`)
- [x] All 4 API routes hardened with validation + error handling
- [x] Chat route race condition fixed (admin client for background saves)
- [x] Migrated to `@google/genai` SDK + `gemini-embedding-001` model
- [x] `npm run build` passes clean, `npm run lint` passes (0 errors)

### Phase 1.5: Strategist Room — COMPLETE
- [x] 4 sub-agents: Parser, Scout, Brainstormer, Accountant
- [x] Orchestrator with state machine in `strategist-room/index.ts`
- [x] 4 API routes: `/api/strategist/{analyze,hypothesize,budget,approve}`
- [x] 4 UI cards: PaperAnalysisCard, CodePathCard, HypothesisSelector, BudgetCard
- [x] Per-agent temperature tuning, task-type embeddings, HNSW index, improved chunking

### Phase 2A: Librarian-Lite — COMPLETE
- [x] arXiv API client (search + fetch by ID)
- [x] Semantic Scholar API client (search + get paper)
- [x] Token bucket rate limiter (arXiv 1/3s, S2 10/s)
- [x] `POST /api/literature/search` — merged, deduplicated results
- [x] `POST /api/literature/fetch` — arXiv ID → download → upload pipeline → Strategist
- [x] arXiv ID detection in ChatInput with "Fetch & Analyze" banner
- [x] PaperSearchCard component with Import button
- [x] "search:" command in chat for paper discovery

### Phase 2B: The Coder Room — NEXT UP
- [ ] E2B sandbox wrapper
- [ ] Code Writer agent + prompts
- [ ] Code Fixer agent + LangGraph write→run→fix cycle
- [ ] Execution API routes
- [ ] CodeEditorCard + CodeExecutionCard UI
- [ ] End-to-end: paper → hypothesis → budget → code → execute → results

### Phase 3-6: See ROADMAP.md

---

## Dev Commands
```bash
cd vreda-app
npm run dev      # Dev server on localhost:3000
npm run build    # Production build (must pass clean)
npm run start    # Production server
npm run lint     # ESLint
```

## Conventions
- Path alias: `@/*` -> `./src/*`
- App Router, NOT Pages Router
- Server components by default; `"use client"` for interactive components
- Supabase RLS enforces per-user data isolation
- Environment variables in `.env.local` (never commit — use `.env.example` as template)
- Streaming responses via Web ReadableStream API
- All errors use custom classes from `src/lib/errors.ts`
- All logging via structured `logger` from `src/lib/logger.ts` (no raw console.log)
- All env vars accessed via `config` from `src/lib/config.ts` (no raw process.env)
- Retry-sensitive operations use `withRetry()` from `src/lib/retry.ts`

## Domain Coverage (Universal — Same Pipeline Logic)
- **AI & Computer Science**: Hyperparameter tuning, neural architecture search, code gen/debug
- **Physical Sciences**: Molecular simulations, fluid dynamics, hypothesis testing
- **Data Science**: Feature engineering, model benchmarking
- **Biology**: Protein folding analysis, genomic sequence processing
- **Mathematics**: Theorem validation, proof verification
