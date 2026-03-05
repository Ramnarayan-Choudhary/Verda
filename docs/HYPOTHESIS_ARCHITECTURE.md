# Hypothesis Generation Pipeline — Architecture

> 8-stage LangGraph-orchestrated multi-agent pipeline that transforms academic papers into structured, debate-ranked research hypotheses.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                               │
│   POST /api/strategist/hypothesize  →  route.ts (TS adapter)           │
│   ├─ Auth + session load (Supabase)                                    │
│   ├─ Resolve input (arXiv ID or download PDF from Supabase storage)    │
│   ├─ Health check Python service (/healthz)                            │
│   ├─ POST http://localhost:8000/generate  ← NDJSON streaming           │
│   ├─ Map Python types → TS frontend types                              │
│   └─ Save state to Supabase, return to UI                              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP (NDJSON stream)
┌──────────────────────────────▼──────────────────────────────────────────┐
│                  Python Hypothesis Service (FastAPI)                     │
│                  services/hypothesis-room/                               │
│                                                                         │
│   server.py  →  main.py (LangGraph)  →  8 stages  →  GeneratorOutput  │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    LangGraph Pipeline                            │  │
│   │                                                                  │  │
│   │  START → Ingestion → Grounding → Overgeneration → Filtering     │  │
│   │          → Refinement → Tournament → Portfolio Audit → Output   │  │
│   │          → END                                                   │  │
│   └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
services/hypothesis-room/
├── src/vreda_hypothesis/
│   ├── main.py                        # LangGraph pipeline orchestrator
│   ├── models.py                      # Pydantic schemas (100+ models)
│   ├── config.py                      # Settings (6 LLM providers)
│   ├── runtime.py                     # PipelineRuntime dataclass
│   ├── server.py                      # FastAPI /generate endpoint
│   │
│   ├── stages/                        # 8 pipeline stages
│   │   ├── ingestion.py               # Stage 1: PDF → text → PaperSummary → ResearchFrame
│   │   ├── grounding.py               # Stage 2: S2 + arXiv + web → iterative gap synthesis
│   │   ├── overgeneration.py          # Stage 3: gaps × archetypes → seeds (up to 200)
│   │   ├── filtering.py               # Stage 4: novelty + budget + verifiability scoring
│   │   ├── refinement.py              # Stage 5: propose → critic → evolve loop (4 cycles)
│   │   ├── tournament.py              # Stage 6: Elo-ranked pairwise judging
│   │   ├── portfolio_audit.py         # Stage 7: coverage + redundancy + execution order
│   │   └── output.py                  # Stage 8: select UI finalists + SOTA payload
│   │
│   ├── agents/                        # Multi-agent debate system
│   │   └── __init__.py                # ProposerAgent, CriticAgent, EvolverAgent,
│   │                                  # MetaReviewerAgent, TournamentJudge
│   │
│   ├── llm/                           # LLM abstraction layer
│   │   ├── provider.py                # Role-based tiered routing + fallback chains
│   │   └── prompts/                   # Per-stage system prompts
│   │       ├── paper_extraction.py    # PaperSummary extraction
│   │       ├── research_frame.py      # ResearchFrame (atomic operators)
│   │       ├── gap_synthesis.py       # 3-round gap identify → validate → refine
│   │       ├── literature_search.py   # Targeted S2 query generation
│   │       ├── archetype_seeds.py     # Seed generation per gap×archetype
│   │       ├── archetype_proposer.py  # IF/THEN/BECAUSE + MVE synthesis
│   │       ├── archetype_critic.py    # Adversarial review
│   │       └── reflection.py          # S2-grounded hypothesis reflection
│   │
│   ├── external/                      # External API clients
│   │   ├── arxiv.py                   # arXiv metadata + PDF download
│   │   ├── semantic_scholar.py        # S2 graph API + keyword search
│   │   ├── paperswithcode.py          # Datasets + code repos
│   │   ├── tavily.py                  # Web literature search
│   │   └── openai_web_search.py       # OpenAI Responses API web search
│   │
│   ├── knowledge/                     # Knowledge graph + vector store
│   │   ├── graph.py                   # PaperKnowledgeGraph (NetworkX)
│   │   └── vector_store.py            # Supabase pgvector + in-memory fallback
│   │
│   └── utils/                         # Utilities
│       ├── elo.py                     # Elo rating system
│       ├── cost.py                    # GPU cost estimation
│       ├── dedup.py                   # Cosine similarity deduplication
│       ├── cache.py                   # In-memory API response cache
│       └── rate_limiter.py            # Token bucket (arXiv 1/3s, S2 10/s)
│
└── tests/                            # 15+ test files
```

---

## Pipeline Stages

### Stage 1: Ingestion (120s timeout)

**File**: `stages/ingestion.py`

**Purpose**: Download/extract paper, build structured summary and deep mechanistic decomposition.

```
Input: arxiv_id or pdf_path
  │
  ├─ _resolve_source()
  │   ├─ arXiv ID → fetch metadata + download PDF
  │   └─ PDF path → load file + create minimal metadata
  │
  ├─ _extract_pdf_text()      → raw text (PyMuPDF)
  ├─ _chunk_text()             → sliding-window chunks (1500 tokens, 200 overlap)
  │
  ├─ LLM: paper_extraction_prompts()
  │   └─ → PaperSummary (title, methods, results, limitations, domain, datasets)
  │
  ├─ LLM: research_frame_prompt()         [AI-Researcher pattern]
  │   └─ → ResearchFrame (core_operators, claimed_gains, assumptions,
  │                        explicit_limits, implicit_limits,
  │                        missing_baselines, untested_axes)
  │
  └─ Initialize: PaperKnowledgeGraph + VectorStoreClient

Output → PipelineState:
  paper_metadata, paper_summary, paper_text, text_chunks, research_frame
```

### Stage 2: Grounding (210s timeout, gracefully degradable)

**File**: `stages/grounding.py`

**Purpose**: Discover related work, generate targeted search queries, run 3-round iterative gap validation.

```
Input: paper_metadata, paper_summary, research_frame
  │
  ├─ Phase 1: Parallel External Retrieval
  │   ├─ S2 fetch_related()          → citation graph (refs + citations)
  │   ├─ PapersWithCode datasets()   → associated datasets
  │   └─ PapersWithCode repos()      → code implementations
  │
  ├─ Phase 2: LLM-Driven Targeted Search      [AI-Scientist-v2 pattern]
  │   ├─ LLM generates 4 targeted queries from ResearchFrame
  │   └─ S2 keyword_search() per query → dedup + merge
  │
  ├─ Phase 2.5: Web Search (optional)
  │   ├─ Tavily: academic domain search
  │   └─ OpenAI web search: broader discovery
  │
  ├─ Phase 3: Build Deep Snippets
  │   └─ Full abstracts + dataset + repo metadata → vector store
  │
  ├─ Phase 4: Legacy Gap Analysis (backward compat)
  │   └─ LLM: gap_analysis_prompts() → GapAnalysis
  │
  └─ Phase 5: Iterative Gap Synthesis          [open_deep_research pattern]
      ├─ Round 1: Identify 8-10 candidate gaps
      ├─ Round 2: Validate against literature (filter solved gaps)
      └─ Round 3: Refine and sharpen → list[MetaGap]
      └─ Fallback: _heuristic_meta_gaps() if LLM fails

Output → PipelineState:
  related_papers, gap_analysis, meta_gaps, grounding_activity
```

**Timeout Behavior**: If grounding times out → append `StageError(recoverable=True)`, continue with `related_papers=[], meta_gaps=[]`.

### Stage 3: Overgeneration (180s timeout)

**File**: `stages/overgeneration.py`

**Purpose**: Generate many hypothesis seeds (up to 200) mapped to gaps × archetypes. Live novelty validation.

```
Input: paper_summary, research_frame, meta_gaps, related_papers
  │
  ├─ Archetype-Mapped Generation
  │   └─ For each (gap, archetype) pair:
  │       └─ LLM: archetype_seed_prompt() → HypothesisSeed[]
  │
  ├─ Live Novelty Validation               [AI-Scientist-v2]
  │   ├─ Batch seeds (5 at a time)
  │   ├─ S2 keyword search per batch
  │   └─ LLM overlap assessment (0-1 score)
  │
  ├─ Cosine Deduplication (threshold 0.85)
  │
  ├─ Diversity Filtering (by archetype + type)
  │
  └─ Fallback: heuristic seed generation if no unique seeds

Output → PipelineState:
  seeds: list[HypothesisSeed]  (1-200 seeds)
```

**5 Hypothesis Archetypes**:

| Archetype | Pattern | Example |
|-----------|---------|---------|
| `mechanistic_probe` | Ablate mechanism | "Remove attention → measure drop" |
| `regime_flip` | Apply to opposite regime | "Test on low-resource instead of high" |
| `baseline_closure` | Missing SOTA comparison | "Compare against [latest method]" |
| `failure_inversion` | Boundary conditions | "Push to failure at extreme scale" |
| `operator_injection` | Import from related paper | "Replace module X with Y from [paper]" |

### Stage 4: Filtering (120s timeout)

**File**: `stages/filtering.py`

**Purpose**: Score seeds on 4 dimensions. Filter to top-K × 5 for refinement.

```
Input: seeds, knowledge_graph, paper_summary
  │
  ├─ Parallel Scoring (semaphore max=15)
  │   ├─ Novelty:       1.0 - max(KG overlap, vector similarity)
  │   ├─ Budget:         GPU cost estimate → 0-1 score
  │   ├─ Verifiability:  LLM quick check (0-10 → normalized)
  │   └─ Concreteness:   MVE feasibility (real dataset? quantitative prediction?)
  │
  ├─ Combined Score
  │   score = novelty×0.3 + verifiability×0.25 + budget×0.2 + concreteness×0.25
  │   Penalties: no real dataset (×0.8), no quantitative prediction (×0.85)
  │
  ├─ Discard: combined_score < 0.2 or (not mve_feasible and concreteness < 0.3)
  │
  └─ Rescue: if all discarded → keep top-K from discarded

Output → PipelineState:
  filtered_seeds: list[ScoredSeed]  (max 100)
```

### Stage 5: Refinement (300s timeout)

**File**: `stages/refinement.py` + `agents/__init__.py`

**Purpose**: Multi-cycle debate-evolve loop. Seeds become full hypotheses through proposal, critique, evolution.

```
Input: filtered_seeds, research_frame, meta_gaps, related_papers
  │
  └─ Cycle Loop (max 4 cycles, convergence detection)
      │
      ├─ SELECT batch (round-robin, batch_size = min(12, max(6, top_k*2)))
      │
      ├─ PROPOSE (parallel)
      │   └─ ProposerAgent.propose(seed) → EnhancedHypothesis
      │       ├─ IF/THEN/BECAUSE statement
      │       ├─ 5-step MVE (Minimum Viable Experiment)
      │       ├─ Falsification threshold ("Dead if: ...")
      │       ├─ ExperimentSpec, ResourceSpec, AdversarialDefense
      │       └─ 6-dimensional scores (novelty, feasibility, impact, ...)
      │
      ├─ REFLECT (parallel)                    [AI-Scientist-v2]
      │   ├─ S2 search for closest related work
      │   └─ LLM strengthens hypothesis against literature
      │
      ├─ CRITIQUE (parallel)
      │   └─ CriticAgent.review(hypothesis) → CriticAssessment
      │       ├─ Verdict: "strong" / "viable" / "weak"
      │       ├─ MVE executable? Falsification valid?
      │       └─ Elo adjustment: strong +25, weak -25
      │
      ├─ WRONG-EXAMPLE-BANK                   [HypoRefine pattern]
      │   └─ Weak hypotheses → FailedSeed (failure_reason, gap_id)
      │       → Next cycle avoids these patterns
      │
      ├─ META-REVIEW
      │   └─ MetaReviewerAgent.reflect() → directives + risk_alerts
      │
      ├─ EVOLVE
      │   └─ EvolverAgent.evolve(top_5, mutation_style, failed_seeds)
      │       → New HypothesisSeeds for next cycle
      │
      └─ CONVERGENCE: avg Elo change < 5.0 → break early

Output → PipelineState:
  refined_hypotheses, elo_ratings, refinement_cycle,
  meta_review_notes, wrong_example_bank
```

**Multi-Agent Roles**:

| Agent | LLM Tier | Purpose |
|-------|----------|---------|
| ProposerAgent | CREATIVE | Expand seed → full structured hypothesis |
| CriticAgent | REASONING | Adversarial review (MVE, falsification, budget) |
| EvolverAgent | CREATIVE | Mutate top hypotheses, avoid failed patterns |
| MetaReviewerAgent | REASONING | Aggregate critic feedback across cycle |

### Stage 6: Tournament (120s timeout)

**File**: `stages/tournament.py`

**Purpose**: Pairwise LLM-judged ranking using Elo rating system.

```
Input: refined_hypotheses, elo_ratings
  │
  ├─ Select Pairs (proximity-based, N rounds default=3)
  │
  ├─ Parallel Judging (semaphore max=8)
  │   └─ TournamentJudge.decide(hyp_a, hyp_b) → TournamentDecision
  │       ├─ Overall winner (a / b / tie)
  │       ├─ Dimension winners: novelty, excitement, feasibility, impact
  │       └─ Reasoning trace
  │
  ├─ Elo Updates (K=32, standard formula)
  │
  └─ Sort by final Elo (descending)

Output → PipelineState:
  tournament_results, elo_ratings
```

### Stage 7: Portfolio Audit (30s timeout)

**File**: `stages/portfolio_audit.py`

**Purpose**: Quality assurance across the hypothesis set.

```
Input: tournament_results
  │
  ├─ Coverage Check
  │   └─ Ensure tags span: {empirical, robustness, scaling, theoretical}
  │
  ├─ Redundancy Detection
  │   └─ Find hypotheses testing same variable or gap
  │
  └─ Execution Order
      └─ Sort by (gpu_hours, -composite_score) for optimal resource use

Output → PipelineState:
  portfolio_audit: { coverage, redundancies, execution_order }
```

### Stage 8: Output (10s timeout)

**File**: `stages/output.py`

**Purpose**: Select UI finalists, quality-gate, build SOTA payload.

```
Input: tournament_results (or refined_hypotheses fallback)
  │
  ├─ Select Candidates (prefer tournament_results)
  │
  ├─ Quality Gate
  │   ├─ archetype ∈ allowed set?
  │   ├─ MVE has 5 steps?
  │   ├─ Statement is non-empty?
  │   └─ Reject: unclear archetype, missing MVE, sparse critic
  │
  ├─ Emergency Fill (if fewer than top_K)
  │   └─ Generate hypotheses from paper_summary + gaps
  │
  ├─ SOTA Payload
  │   └─ research_frame + meta_gaps + hypotheses + portfolio_audit
  │
  └─ Reasoning Context (multi-line trace)

Output → PipelineState:
  final_output: GeneratorOutput {
    hypotheses, reasoning_context, gap_analysis_used,
    reflection_rounds, generation_strategy, portfolio_audit, sota_payload
  }
```

---

## Key Data Models

### PipelineState (LangGraph Central State)

```
┌─────────────────────────────────────────────────────────────┐
│ PipelineState                                               │
├─────────────────────────────────────────────────────────────┤
│ INPUT                                                       │
│   arxiv_id, pdf_path, config: PipelineConfig                │
├─────────────────────────────────────────────────────────────┤
│ STAGE 1: paper_metadata, paper_summary, paper_text,         │
│          text_chunks, research_frame                        │
├─────────────────────────────────────────────────────────────┤
│ STAGE 2: related_papers, gap_analysis, meta_gaps,           │
│          grounding_activity                                 │
├─────────────────────────────────────────────────────────────┤
│ STAGE 3: seeds: list[HypothesisSeed]                        │
├─────────────────────────────────────────────────────────────┤
│ STAGE 4: filtered_seeds: list[ScoredSeed]                   │
├─────────────────────────────────────────────────────────────┤
│ STAGE 5: refined_hypotheses, elo_ratings, refinement_cycle, │
│          meta_review_notes, wrong_example_bank              │
├─────────────────────────────────────────────────────────────┤
│ STAGE 6: tournament_results, elo_ratings                    │
├─────────────────────────────────────────────────────────────┤
│ STAGE 7: portfolio_audit                                    │
├─────────────────────────────────────────────────────────────┤
│ STAGE 8: final_output: GeneratorOutput                      │
├─────────────────────────────────────────────────────────────┤
│ INFRA: knowledge_graph, vector_store_client,                │
│        progress_callback, token_usage, errors               │
└─────────────────────────────────────────────────────────────┘
```

### ResearchFrame (AI-Researcher Pattern)

```python
ResearchFrame:
  task_family: "vision" | "nlp" | "rl" | "theory" | "systems" | "bio" | "other"
  core_operators: list[str]        # "STE", "LoRA", "sparse attention"
  core_mechanism: str              # One-sentence intervention description
  claimed_gains: list[ClaimedGain] # "+5% on task_y under condition_z"
  assumptions: list[str]           # "IID data", ">40GB VRAM"
  explicit_limits: list[str]
  implicit_limits: list[str]
  missing_baselines: list[str]
  untested_axes: list[str]         # "scale", "OOD", "multilingual"
```

### MetaGap (3-Round Validated)

```python
MetaGap:
  gap_id: str
  gap_type: "empirical" | "theoretical" | "robustness" | "scaling" | "application"
  statement: str               # "No work tests [X] under [Y] on [Z]"
  why_it_matters: str
  nearest_prior_work: str
  already_solved: bool
  iteration_history: list[str] # Tracks across 3 validation rounds
```

### EnhancedHypothesis (Full Output)

```python
EnhancedHypothesis:
  id, type, title, description
  archetype: HypothesisArchetype
  statement: str                    # IF/THEN/BECAUSE
  mve: list[str]                    # 5-step Minimum Viable Experiment
  falsification_threshold: str      # "Dead if: [condition]"
  experiment_spec: ExperimentSpec   # intervention, dataset, metric, prediction
  resources: ResourceSpec           # model, gpu_hours
  adversarial: AdversarialDefense   # kill_switch, defense
  novelty_spec: NoveltySpec         # closest_paper, why_distinct
  portfolio_tag: str                # empirical | robustness | scaling | theoretical
  scores: DimensionScores           # 6 dimensions (0-100 each)
  composite_score: int              # Weighted aggregate
  elo_rating: float                 # From tournament
  critic_assessment: CriticAssessment | None
  addresses_gap_id: str | None
```

### DimensionScores

```
novelty × 0.25 + feasibility × 0.20 + impact × 0.20
+ grounding × 0.15 + testability × 0.10 + clarity × 0.10
= composite_score (0-100)
```

---

## LLM Provider Architecture

### Role-Based Tiering

```
┌───────────────────────────────────────────────────────┐
│ AgentRole              │ Tier       │ Agents          │
├────────────────────────┼────────────┼─────────────────┤
│ CRITIC, META_REVIEWER  │ REASONING  │ DeepSeek-R1     │
│ TOURNAMENT_JUDGE       │            │                 │
│ GAP_ANALYSIS           │            │                 │
├────────────────────────┼────────────┼─────────────────┤
│ PROPOSER, EVOLVER      │ CREATIVE   │ DeepSeek-V3     │
│ SEED_GENERATION        │            │                 │
├────────────────────────┼────────────┼─────────────────┤
│ PAPER_EXTRACTION       │ FAST       │ GPT-4o-mini     │
│ VERIFIABILITY          │            │                 │
│ FILTERING              │            │                 │
├────────────────────────┼────────────┼─────────────────┤
│ DEFAULT                │ UNIVERSAL  │ DeepSeek-V3     │
└────────────────────────┴────────────┴─────────────────┘
```

### Fallback Chains

```
REASONING: ChatAnywhere/deepseek-r1 → Claude Sonnet → DeepSeek direct → K2Think
CREATIVE:  ChatAnywhere/deepseek-v3 → DeepSeek direct → GPT-4o → K2Think
FAST:      ChatAnywhere/gpt-4o-mini → OpenRouter/Gemini → K2Think
UNIVERSAL: ChatAnywhere/deepseek-v3 → K2Think → OpenRouter
```

### LLMProvider Interface

```python
LLMProvider:
  generate(system, user, temperature, role) → str
  generate_json(system, user, model_class, temperature, role) → BaseModel
  generate_batch(prompts, temperature, role, max_concurrent) → list[str]
  token_usage → TokenUsage  # tracks prompt/completion/cost across all calls
```

---

## External API Clients

| Client | API | Rate Limit | Purpose |
|--------|-----|------------|---------|
| `ArxivClient` | arXiv Atom API | 1 req/3s | Metadata + PDF download |
| `SemanticScholarClient` | S2 Graph API | 10 req/s | Citation graph + keyword search |
| `PapersWithCodeClient` | PwC API | — | Datasets + code repos |
| `TavilySearchClient` | Tavily API | 2 req/s | Web literature discovery |
| `OpenAIWebSearchClient` | OpenAI Responses | — | Broader web search |

---

## Knowledge Layer

### PaperKnowledgeGraph (`knowledge/graph.py`)

- **Backend**: NetworkX MultiDiGraph
- **Entity vocabulary**: 100+ terms (architectures, training methods, models, datasets, metrics)
- **Functions**: `add_paper()`, `novelty_signal(seed_text) → NoveltySignal`
- **Used by**: Filtering (novelty scoring), Critic (overlap detection)

### VectorStoreClient (`knowledge/vector_store.py`)

- **Primary backend**: Supabase pgvector (384-dim, HNSW index)
- **Fallback**: In-memory numpy cosine similarity
- **Embedding model**: `all-MiniLM-L6-v2` (SentenceTransformer)
- **Functions**: `add_chunks(doc_id, chunks)`, `similarity_search(query, k)`
- **Used by**: Grounding (RAG context), Filtering (similarity scoring)

---

## Server & Transport

### FastAPI Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Health check + active providers |
| `/generate` | POST | Run pipeline, stream NDJSON progress |

### NDJSON Streaming Protocol

```json
{"type": "progress", "step": "Paper Ingestion", "message": "...", "current": 1, "total": 8}
{"type": "progress", "step": "External Grounding", "message": "...", "current": 2, "total": 8}
{"type": "warning", "step": "External Grounding", "message": "2 warnings"}
...
{"type": "complete", "step": "pipeline", "data": {"output": GeneratorOutput}}
```

Or on failure:
```json
{"type": "error", "step": "pipeline", "message": "..."}
```

### Stage Timeouts

| Stage | Default | Degradable? |
|-------|---------|-------------|
| Ingestion | 120s | No |
| Grounding | 210s | Yes — continues with empty context |
| Overgeneration | 180s | No |
| Filtering | 120s | No |
| Refinement | 300s | No |
| Tournament | 120s | No |
| Portfolio Audit | 30s | No |
| Output | 10s | No |

---

## TypeScript Route Handler

**File**: `apps/web/src/app/api/strategist/hypothesize/route.ts`

```
POST /api/strategist/hypothesize
  │
  ├─ Verify auth + load session from Supabase
  ├─ Recover paper_analysis if missing (re-run Parser + Scout)
  ├─ Parse user message for requested hypothesis count
  ├─ Health check Python service (/healthz)
  │
  ├─ Resolve input:
  │   ├─ arXiv ID → pass directly
  │   └─ Uploaded PDF → download from Supabase storage → write temp file → pass path
  │
  ├─ POST http://localhost:8000/generate
  │   ├─ Body: { arxiv_id?, pdf_path?, config: PipelineConfig }
  │   └─ Parse NDJSON stream until "complete" or "error"
  │
  ├─ Map Python GeneratorOutput → TS types:
  │   ├─ brainstormer_output: BrainstormerOutput (hypotheses array)
  │   ├─ hypothesis_pipeline_output: GeneratorOutput
  │   └─ critic_output: CriticOutput
  │
  ├─ Save state + session to Supabase
  │
  └─ Return JSON { session_id, phase, brainstormer_output, ... }
```

---

## Resilience & Error Handling

### Stage-Level
- Timeout → `StageError(recoverable=True/False)`
- Grounding timeout → graceful degradation (empty related_papers/meta_gaps)
- Other stage timeout → propagate as 500 to client

### Seed-Level
- No seeds after generation → heuristic fallback seed generation
- No seeds after filtering → rescue discarded seeds
- No hypotheses after refinement → fallback synthesis from summary + gaps

### LLM-Level
- JSON validation failure → retry with fix prompt (max 2 retries)
- Provider unavailable → fallback to next tier in chain
- Sparse output → recover from seed/context

### External API-Level
- Rate limit (429) → skip, log warning, continue
- Upstream error (5xx) → skip, log warning, continue
- Timeout → skip, log warning, continue

---

## Startup & Commands

```bash
# Start Python service
cd services/hypothesis-room
pip install -e .
python -m vreda_hypothesis.server
# → http://localhost:8000

# Health check
curl http://localhost:8000/healthz

# Start web app
cd apps/web
npm run dev
# → http://localhost:3000
```

### Required Environment Variables

```bash
# LLM Providers (at least one required)
CHATANYWHERE_API_KEY=...
OPENAI_API_KEY=...          # optional fallback
ANTHROPIC_API_KEY=...       # optional fallback

# External APIs
SEMANTIC_SCHOLAR_API_KEY=...
TAVILY_API_KEY=...          # optional

# Supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_POSTGRES_URL=...   # direct Postgres for pgvector
```
