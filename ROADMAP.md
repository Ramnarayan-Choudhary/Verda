# VREDA.ai — Product Roadmap

> Last updated: 2026-02-13
> Team: 2 (Founder + AI co-builder) | Budget: $0 (free tier only)

---

## How It Works: The Quest Pipeline

```
USER INPUT                    FOUR ROOMS                           OUTPUT
─────────                    ──────────                           ──────

"Reproduce the         ┌─────────────────┐
 attention mechanism   │  1. STRATEGIST   │
 from this paper"  ───>│  Decompose goal  │
                       │  Budget estimate │
                       └────────┬────────┘
                                │ Research Manifest
                                v
                       ┌─────────────────┐
                       │  2. LIBRARIAN    │
                       │  Find papers     │
                       │  Extract context │
                       └────────┬────────┘
                                │ Paper Context + Protocols
                                v
                       ┌─────────────────┐
                       │  3. CODER        │
                       │  Write code      │──> sandbox ──> fix loop
                       │  Execute in E2B  │
                       └────────┬────────┘
                                │ Code + Results
                                v
                       ┌─────────────────┐         ┌──────────────┐
                       │  4. VERIFIER     │         │ DISCOVERY    │
                       │  Validate math   │────────>│ PACK         │
                       │  Check physics   │         │ - Manuscript  │
                       └─────────────────┘         │ - Code Repo   │
                                                   │ - Verify Log  │
                                                   └──────────────┘
```

---

## Phase 0: Security Emergency — COMPLETE

**Duration**: 2 hours | **Completed**: 2026-02-11

What we fixed:
- Deleted test files containing hardcoded API keys (`test-gemini.ts`, `test-openrouter.ts`)
- Switched storage bucket from public to private access
- Removed `dangerouslyAllowBrowser: true` from OpenRouter client
- Removed random vector fallback (was silently corrupting embeddings)
- Created `.env.example` template

---

## Phase 1: Foundation Hardening — COMPLETE

**Duration**: 1 day | **Completed**: 2026-02-11

What we built:

| File | Purpose |
|------|---------|
| `src/lib/config.ts` | Centralized env vars — `requireEnv()` throws on missing vars |
| `src/lib/errors.ts` | Custom error classes: `VredaError`, `EmbeddingError`, `LLMError`, `ValidationError`, `StorageError` |
| `src/lib/logger.ts` | Structured logger — JSON in prod, readable in dev. Replaces all console.log |
| `src/lib/retry.ts` | Generic `withRetry()` — exponential backoff (1s/2s/4s), configurable max retries |
| `src/lib/validation.ts` | `validateUUID()`, `validateMessage()`, `validateFileUpload()`, `validatePDFMagicBytes()` |

What we hardened:
- All 4 API routes now validate input and handle errors gracefully
- Chat route race condition fixed (admin client for background message saves)
- Migrated from deprecated `embedding-001` to `gemini-embedding-001` via `@google/genai` SDK
- Build and lint pass clean

**Validation**: Upload PDF -> embedding succeeds with retry -> chat works with RAG context

---

## Phase 1.5: Strategist Room — Multi-Agent Orchestrator — COMPLETE

**Duration**: 2 days | **Completed**: 2026-02-12

What we built:
- 4 sub-agents: Parser, Scout, Brainstormer, Accountant in `src/lib/agents/strategist-room/`
- Orchestrator with state machine: idle → parsing → scouting → analysis_complete → brainstorming → hypothesis_presented → budgeting → budget_presented → approved
- 4 API routes: `/api/strategist/{analyze,hypothesize,budget,approve}`
- 4 UI cards: PaperAnalysisCard, CodePathCard, HypothesisSelector, BudgetCard
- Shared `makeAgentCall<T>()` utility with per-agent temperature tuning
- HNSW vector index (replacing IVFFlat), improved chunking (1000/200)

---

## Phase 2A: Librarian-Lite — arXiv + Semantic Scholar — COMPLETE

**Duration**: 1 day | **Completed**: 2026-02-13

**Goal**: Quick literature integration — fetch papers by arXiv ID and search across APIs.

What we built:

| File | What it does |
|------|-------------|
| `src/lib/literature/arxiv.ts` | `searchArxiv()`, `fetchByArxivId()`, `isArxivId()` — arXiv Atom API |
| `src/lib/literature/semantic-scholar.ts` | `searchPapers()`, `getPaper()` — Semantic Scholar Graph API |
| `src/lib/literature/rate-limiter.ts` | Token bucket: arXiv 1 req/3s, S2 10 req/s |
| `src/lib/literature/types.ts` | `PaperMetadata`, `LiteratureSearchResult` types |
| `POST /api/literature/search` | Search both APIs, deduplicate, merge results |
| `POST /api/literature/fetch` | Fetch by arXiv ID → download PDF → full upload pipeline → Strategist |
| `src/components/chat/PaperSearchCard.tsx` | Search result cards with Import button |
| Updated `ChatInput.tsx` | arXiv ID detection banner + "search:" command |

**User flows**:
- Paste `2301.07041` → banner appears → click "Fetch & Analyze" → paper imported
- Type `search: attention mechanism` → search results card → click "Import to VREDA"
- Both flows pipeline into existing upload → chunk → embed → Strategist Room

---

## Phase 2B: The Coder — Code Execution Sandbox — NEXT UP

**Duration**: ~1 week | **Status**: NEXT UP

**Goal**: THE differentiator. Given an approved Research Manifest, generate code, execute in E2B sandbox, self-correct. **This is the fundable demo.**

### What to build:

**Dependencies**: `@langchain/langgraph`, `e2b`, `@e2b/code-interpreter`

**Backend**
| File | What it does |
|------|-------------|
| `src/lib/sandbox/e2b.ts` | E2B wrapper: `runCode()`, `installPackages()`, sandbox lifecycle |
| `src/lib/agents/coder-room/index.ts` | Coder Room orchestrator |
| `src/lib/agents/coder-room/code-writer-agent.ts` | Writes experiment code from manifest |
| `src/lib/agents/coder-room/code-fixer-agent.ts` | Reads errors, produces fixes |
| `src/lib/agents/coder-room/prompts/` | Code generation and error diagnosis prompts |

**LangGraph State** (write → run → fix cycle):
```
write_code → execute → check_result → (success → done | error → fix_code → execute)
Max 3 iterations. Each node is a function, LangGraph manages the cycle.
```

**API Routes**
| Route | Purpose |
|-------|---------|
| `POST /api/execute/run` | Trigger execution, stream progress |
| `GET /api/execute/status` | Poll execution state |

**Frontend**
| Component | Purpose |
|-----------|---------|
| `src/components/chat/CodeEditorCard.tsx` | Code preview with syntax highlighting + Run button |
| `src/components/chat/CodeExecutionCard.tsx` | Live output stream, error display, Fix & Retry |

**Validation criteria**:
- Upload paper → brainstorm → approve budget → code generated → runs in E2B → results shown
- Failed code triggers auto-fix cycle (up to 3 attempts)
- Full quest costs < $0.50 in API calls
- **This is the fundable demo**

---

## Phase 2C: Librarian-Full — Deep Literature Integration

**Duration**: ~1 week | **Status**: PLANNED

**Goal**: Enrich literature integration with PapersWithCode, RAG over search results, citation graphs.

What to build:
- PapersWithCode API integration (map papers to GitHub repos for Scout enrichment)
- Citation graph traversal (find related papers automatically)
- RAG over fetched paper abstracts (search without downloading full PDFs)
- Database migration for paper metadata storage

---

## Phase 4: The Verifier — Scientific Validation

**Duration**: ~3 weeks | **Status**: PLANNED

**Goal**: Ensure results aren't hallucinations. LLM-based verification first, Z3/PINNs in v2.

### What to build:

| File | What it does |
|------|-------------|
| `src/lib/agents/verifier.ts` | Structured verification checks |
| `src/lib/agents/verifier-prompts.ts` | Prompts for each verification type |
| `POST /api/verify` | Trigger verification |
| `supabase/004_verifications.sql` | `verifications` table |
| `src/components/chat/VerificationCard.tsx` | Pass/fail badges, confidence score |

**v1 Verification checks (LLM-based)**:
1. Dimensional analysis — do units match?
2. Conservation laws — energy/mass/momentum preserved?
3. Statistical validity — p-values, sample sizes, confidence intervals
4. Boundary conditions — edge cases handled?
5. Order of magnitude — results in plausible range?
6. Logical consistency — no contradictions in reasoning?

**Validation criteria**:
- Execute experiment -> click "Verify" -> see structured check results
- Each check shows pass/fail with LLM reasoning

---

## Phase 5: Discovery Pack + Pipeline Orchestration

**Duration**: ~3 weeks | **Status**: PLANNED

**Goal**: Tie all four rooms together. One-click "Quest" from paper to Discovery Pack.

### What to build:

| File | What it does |
|------|-------------|
| `src/lib/pipeline/quest-graph.ts` | LangGraph top-level: Strategist -> Librarian -> Coder -> Verifier -> Package |
| `src/lib/discovery-pack/generator.ts` | Generates manuscript + code repo + verification log |
| `POST /api/quest` | One-click full pipeline, streaming progress |
| `src/components/chat/QuestProgress.tsx` | Stage-by-stage progress display |
| `src/components/chat/DiscoveryPackCard.tsx` | Final output with download |

**Validation criteria**:
- Upload paper -> click "Run Full Quest" -> watch all stages -> get Discovery Pack
- Discovery Pack is downloadable as a zip
- Total cost per quest < $0.50

---

## Phase 6: Production Readiness

**Duration**: ~2 weeks | **Status**: PLANNED

### What to build:
- **CI/CD**: `.github/workflows/ci.yml` — lint, typecheck, build, test on every push
- **Testing**: `vitest` — target 60%+ coverage on critical paths (agents, embeddings, validation)
- **Rate limiting**: `src/lib/rate-limit.ts` — 60 req/min chat, 10 req/min upload, 20 req/min search
- **Deploy**: Vercel free tier

---

## Infrastructure Budget (Free Tier)

| Service | Free Tier Limit | Our Usage | Monthly Cost |
|---------|----------------|-----------|-------------|
| Supabase | 500MB DB, 1GB storage | ~50MB, ~200MB | $0 |
| OpenRouter (Gemini Flash) | Pay-per-token | ~5M tokens | ~$0.50 |
| Gemini Embeddings | 1,500/day free | ~500/day | $0 |
| E2B Sandbox | Free tier | ~50 runs | $0 |
| Semantic Scholar | 100 req/5min | ~200 req/day | $0 |
| Vercel | 100GB bandwidth | ~5GB | $0 |
| **Total** | | | **~$0.50/mo** |

## Scaling Path (When We Have Revenue)

| Component | Free -> Paid | How |
|-----------|-------------|-----|
| Database | Supabase Free -> Pro ($25/mo) | Same API, change plan |
| Embeddings | Gemini -> OpenAI text-embedding-3 | Change model in config |
| LLM | Gemini Flash -> GPT-5 / Claude | Change model in OpenRouter |
| Sandbox | E2B Free -> Pro | Change API key |
| Vector DB | pgvector -> Pinecone | New adapter |
| Hosting | Vercel Free -> Pro ($20/mo) | Automatic |

---

## Key Milestones

| Date | Milestone | What it means |
|------|-----------|--------------|
| 2026-02-11 | Phase 0+1 complete | Secure, hardened foundation. Chat + PDF upload work. |
| 2026-02-12 | Phase 1.5 complete | Strategist Room: 4 sub-agents, state machine, UI cards |
| 2026-02-13 | Phase 2A complete | Librarian-Lite: arXiv + Semantic Scholar search + fetch |
| **~Week 4** | **Phase 2B complete** | **FUNDABLE DEMO: Paper in -> working code out via E2B** |
| ~Week 5 | Phase 2C complete | Full literature integration with PapersWithCode |
| ~Week 8 | Phase 4 complete | Code is scientifically verified before delivery |
| ~Week 11 | Phase 5 complete | One-click Quest -> complete Discovery Pack |
| ~Week 13 | Phase 6 complete | Production-ready, deployed on Vercel |

The **fundable demo moment** is end of Phase 2B — the first time a user uploads a paper and gets back working code that reproduces the experiment in a sandbox. This is the demo we show investors.
