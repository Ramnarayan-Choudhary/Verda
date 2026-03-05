# VREDA Hypothesis Room — Architecture Diagram

## 1. Full Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         VREDA HYPOTHESIS GENERATION PIPELINE                         │
│                    arXiv:2502.18864 + arXiv:2510.09901 + arXiv:2409.04109           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   INPUT                                                                             │
│   ┌──────────┐    ┌──────────┐                                                     │
│   │ arXiv ID │ OR │ PDF File │                                                     │
│   └────┬─────┘    └────┬─────┘                                                     │
│        └───────┬───────┘                                                            │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 1: PAPER INGESTION                              [FAST Tier: Gemini]  ║   │
│  ║  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  ║   │
│  ║  │ Fetch Paper  │──▶│ Extract PDF  │──▶│ Chunk Text   │──▶│ LLM Extract  │  ║   │
│  ║  │ (arXiv API)  │   │ (PyMuPDF)    │   │ (1500 words  │   │ PaperSummary │  ║   │
│  ║  │              │   │              │   │  200 overlap) │   │ + Init KG    │  ║   │
│  ║  └─────────────┘   └──────────────┘   └──────────────┘   └──────────────┘  ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                │  PaperSummary, PaperMetadata, text_chunks, KnowledgeGraph          │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 2: EXTERNAL GROUNDING                        [REASONING Tier: Claude] ║   │
│  ║                                                                               ║   │
│  ║  ┌─────────────────────────────────────────────┐                              ║   │
│  ║  │          asyncio.gather (parallel)           │                              ║   │
│  ║  │  ┌────────────┐ ┌───────────┐ ┌──────────┐  │   ┌──────────────────────┐  ║   │
│  ║  │  │ Semantic    │ │ PwC       │ │ PwC      │  │──▶│ Gap Analysis (LLM)   │  ║   │
│  ║  │  │ Scholar     │ │ Datasets  │ │ Repos    │  │   │ 3-5 research gaps    │  ║   │
│  ║  │  │ (30 papers) │ │ (5 max)   │ │ (5 max)  │  │   │ + landscape summary  │  ║   │
│  ║  │  └────────────┘ └───────────┘ └──────────┘  │   └──────────────────────┘  ║   │
│  ║  └─────────────────────────────────────────────┘                              ║   │
│  ║       │              │                                                        ║   │
│  ║       ▼              ▼                                                        ║   │
│  ║  ┌──────────┐  ┌──────────────┐                                               ║   │
│  ║  │ Enrich   │  │ Vector Store │                                               ║   │
│  ║  │ KG nodes │  │ + RAG search │                                               ║   │
│  ║  └──────────┘  └──────────────┘                                               ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                │  GapAnalysis, related_papers, enriched KG + VectorStore             │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 3: SEED OVERGENERATION                       [CREATIVE Tier: DeepSeek]║   │
│  ║                                                                               ║   │
│  ║  7 Diversity Tags × ~30 seeds each = ~200 seeds                               ║   │
│  ║                                                                               ║   │
│  ║  ┌──────────────────────────────────────────────────────┐                     ║   │
│  ║  │  Tags: architecture_crossover │ modality_pivot │     │                     ║   │
│  ║  │        resource_constrained   │ analogical     │     │                     ║   │
│  ║  │        dataset_remix │ failure_inversion │ param │    │                     ║   │
│  ║  └──────────────────────────────────────────────────────┘                     ║   │
│  ║              │                                                                ║   │
│  ║              ▼  Parallel batches of 3                                         ║   │
│  ║  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐          ║   │
│  ║  │ LLM → SeedBatch  │   │ LLM → SeedBatch  │   │ LLM → SeedBatch  │          ║   │
│  ║  │ (structured JSON) │   │ (structured JSON) │   │ (structured JSON) │          ║   │
│  ║  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘          ║   │
│  ║           └──────────────┬───────┘──────────────────────┘                     ║   │
│  ║                          ▼                                                    ║   │
│  ║              ┌──────────────────────┐                                         ║   │
│  ║              │ Cosine Dedup (0.85)  │  all-MiniLM-L6-v2 (384-dim)            ║   │
│  ║              │ ~200 → ~120 unique   │                                         ║   │
│  ║              └──────────────────────┘                                         ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                │  ~120 unique HypothesisSeed objects                                │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 4: PARALLEL FILTERING                           [FAST Tier: Gemini]  ║   │
│  ║                                                                               ║   │
│  ║  asyncio.gather + Semaphore(15) — all seeds scored in parallel                ║   │
│  ║                                                                               ║   │
│  ║  For each seed:                                                               ║   │
│  ║  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   ║   │
│  ║  │ Novelty Score     │  │ Budget Estimate   │  │ Verifiability (LLM)     │   ║   │
│  ║  │ = 1 - max(        │  │ = GPU heuristics  │  │ = LLM score 1-10       │   ║   │
│  ║  │   KG_overlap,     │  │   (RunPod rates)  │  │   "How falsifiable?"   │   ║   │
│  ║  │   vector_sim)     │  │                   │  │                         │   ║   │
│  ║  └───────┬───────────┘  └────────┬──────────┘  └────────────┬────────────┘   ║   │
│  ║          └──────────────┬────────┘──────────────────────────┘                 ║   │
│  ║                         ▼                                                     ║   │
│  ║          combined = novelty×0.4 + verifiability×0.3 + budget×0.3             ║   │
│  ║                         │                                                     ║   │
│  ║                         ▼                                                     ║   │
│  ║              ┌──────────────────────────┐                                     ║   │
│  ║              │ Sort + Top-K × 5 cutoff  │                                     ║   │
│  ║              │ ~120 → ~50 ScoredSeeds   │                                     ║   │
│  ║              └──────────────────────────┘                                     ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║                                                                               ║   │
│  ║  STAGE 5: MULTI-AGENT REFINEMENT LOOP        3-5 cycles (auto-convergence)   ║   │
│  ║  ═══════════════════════════════════════════════════════════════════════════   ║   │
│  ║                                                                               ║   │
│  ║                    ┌──────────────────────────────────────┐                   ║   │
│  ║                    │         SEED POOL (round-robin)       │                   ║   │
│  ║                    │   Never depletes — cycles reuse seeds │                   ║   │
│  ║                    └───────────────┬──────────────────────┘                   ║   │
│  ║                                    │ batch of 6-12 seeds                      ║   │
│  ║                                    ▼                                          ║   │
│  ║  ┌─────────────────────────────────────────────────────────────────────────┐  ║   │
│  ║  │                                                                         │  ║   │
│  ║  │   ┌─────────────────┐      [CREATIVE Tier: DeepSeek]                   │  ║   │
│  ║  │   │   PROPOSER      │      T=0.55                                      │  ║   │
│  ║  │   │   Expand seed → │──┐   LLM-evaluated scores (not hardcoded)        │  ║   │
│  ║  │   │   full hypothesis│  │   Returns: HypothesisDraft with 6-dim scores  │  ║   │
│  ║  │   └─────────────────┘  │                                                │  ║   │
│  ║  │         ╱ parallel ╲   │                                                │  ║   │
│  ║  │                        ▼                                                │  ║   │
│  ║  │   ┌─────────────────┐      [REASONING Tier: Claude]                    │  ║   │
│  ║  │   │   CRITIC         │      T=0.2                                      │  ║   │
│  ║  │   │   Stress-test    │──┐   Adversarial review                         │  ║   │
│  ║  │   │   novelty +      │  │   Revises ALL 6 dimension scores             │  ║   │
│  ║  │   │   feasibility    │  │   Verdict: strong | viable | weak            │  ║   │
│  ║  │   └─────────────────┘  │                                                │  ║   │
│  ║  │         ╱ parallel ╲   │                                                │  ║   │
│  ║  │                        ▼                                                │  ║   │
│  ║  │   ┌─────────────────┐  │   Elo adjustments:                            │  ║   │
│  ║  │   │   ELO UPDATE     │  │   strong → +25                               │  ║   │
│  ║  │   │   Per hypothesis  │◀┘   viable → +0                                │  ║   │
│  ║  │   │                  │      weak   → -25                               │  ║   │
│  ║  │   └────────┬────────┘                                                  │  ║   │
│  ║  │            │                                                            │  ║   │
│  ║  │            ▼                                                            │  ║   │
│  ║  │   ┌─────────────────┐      [REASONING Tier: Claude]                    │  ║   │
│  ║  │   │  META-REVIEWER   │      T=0.3                                      │  ║   │
│  ║  │   │  Pattern analysis│      Observes critic patterns                   │  ║   │
│  ║  │   │  across cycle    │──┐   Emits directives for next cycle            │  ║   │
│  ║  │   │  + risk alerts   │  │   E.g. "needs more baselines"               │  ║   │
│  ║  │   └─────────────────┘  │                                                │  ║   │
│  ║  │                        │                                                │  ║   │
│  ║  │            ┌───────────┘                                                │  ║   │
│  ║  │            ▼                                                            │  ║   │
│  ║  │   ┌─────────────────┐      [CREATIVE Tier: DeepSeek]                   │  ║   │
│  ║  │   │   EVOLVER        │                                                  │  ║   │
│  ║  │   │   Crossover /    │      Takes top-5 hypotheses                     │  ║   │
│  ║  │   │   Mutation /     │──────▶ New seeds added to pool                  │  ║   │
│  ║  │   │   Simplify /     │      (scored by LLM verifiability)              │  ║   │
│  ║  │   │   Invert         │                                                  │  ║   │
│  ║  │   └─────────────────┘                                                  │  ║   │
│  ║  │                                                                         │  ║   │
│  ║  └──────────────────────────────┬──────────────────────────────────────────┘  ║   │
│  ║                                 │                                             ║   │
│  ║           ┌─────────────────────┴──────────────────────┐                     ║   │
│  ║           │  CONVERGENCE CHECK                          │                     ║   │
│  ║           │  avg |Δ Elo| < 5.0 across all hypotheses?  │                     ║   │
│  ║           │                                             │                     ║   │
│  ║           │  YES → exit loop early                      │                     ║   │
│  ║           │  NO  → next cycle (up to max_cycles)        │                     ║   │
│  ║           └─────────────────────────────────────────────┘                     ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                │  ~24-48 refined EnhancedHypothesis objects with Elo ratings         │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 6: TOURNAMENT RANKING                        [REASONING Tier: Claude] ║   │
│  ║                                                                               ║   │
│  ║  Parallelized pairwise judging — Semaphore(8)                                ║   │
│  ║                                                                               ║   │
│  ║  ┌────────────────────────────────────────────────────────────────────────┐   ║   │
│  ║  │  Proximity-based pairing (similar Elo → competitive matches)          │   ║   │
│  ║  │  3 rounds × N/2 pairs = ~36-72 pairwise debates                      │   ║   │
│  ║  │                                                                        │   ║   │
│  ║  │  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐    │   ║   │
│  ║  │  │ A vs B   │     │ C vs D   │     │ E vs F   │     │ G vs H   │    │   ║   │
│  ║  │  │ Judge    │     │ Judge    │     │ Judge    │     │ Judge    │    │   ║   │
│  ║  │  │ (LLM)   │     │ (LLM)   │     │ (LLM)   │     │ (LLM)   │    │   ║   │
│  ║  │  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘    │   ║   │
│  ║  │       ▼                ▼                ▼                ▼           │   ║   │
│  ║  │  winner/loser/tie → Standard Elo update (K=32)                       │   ║   │
│  ║  └────────────────────────────────────────────────────────────────────────┘   ║   │
│  ║                                                                               ║   │
│  ║  Criteria: Novelty > Impact > Feasibility > Excitement                        ║   │
│  ║  Sort by final Elo rating → ranked list                                       ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                ▼                                                                    │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗   │
│  ║  STAGE 7: STRUCTURED OUTPUT                                                  ║   │
│  ║                                                                               ║   │
│  ║  Top-K hypotheses (default 10) → GeneratorOutput JSON                         ║   │
│  ║  Matches TypeScript HypothesisSelector.tsx format exactly                     ║   │
│  ║                                                                               ║   │
│  ║  Output includes: hypotheses[], reasoning_context, gap_analysis_used,         ║   │
│  ║                    reflection_rounds, generation_strategy                      ║   │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝   │
│                │                                                                    │
│                ▼                                                                    │
│          ┌──────────────────────────────────────────┐                               │
│          │  NDJSON Stream → Next.js Frontend         │                               │
│          │  HypothesisSelector.tsx renders results    │                               │
│          └──────────────────────────────────────────┘                               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Tiered LLM Routing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TIERED LLM ROUTING SYSTEM                            │
│                                                                             │
│  Each agent role maps to an IDEAL model. When that model's API key          │
│  isn't configured, the system falls back through the priority chain.        │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════     │
│                                                                             │
│  REASONING TIER ──── Deep analytical thinking                               │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  Agents: Critic, Meta-Reviewer, Tournament Judge, Gap Analysis  │       │
│  │                                                                  │       │
│  │  Chain: Claude ──▶ DeepSeek ──▶ OpenAI ──▶ K2Think ──▶ Gemini  │       │
│  │         ┬─────    ┬────────    ┬──────    ┬───────    ┬──────   │       │
│  │         │IDEAL    │fallback1   │fallback2 │fallback3  │last     │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  CREATIVE TIER ──── Divergent thinking + novelty                            │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  Agents: Proposer, Evolver, Seed Generation                     │       │
│  │                                                                  │       │
│  │  Chain: DeepSeek ──▶ OpenAI ──▶ Claude ──▶ K2Think ──▶ Gemini  │       │
│  │         ┬────────    ┬──────    ┬─────    ┬───────    ┬──────   │       │
│  │         │IDEAL       │fallback1 │fallback2│fallback3  │last     │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  FAST TIER ──── Speed + structured output, low cost                         │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  Agents: Paper Extraction, Verifiability, Filtering             │       │
│  │                                                                  │       │
│  │  Chain: Gemini ──▶ K2Think ──▶ OpenAI ──▶ DeepSeek ──▶ Claude  │       │
│  │         ┬──────    ┬───────    ┬──────    ┬────────    ┬─────   │       │
│  │         │IDEAL     │fallback1  │fallback2 │fallback3   │last    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  UNIVERSAL TIER ──── General purpose fallback                               │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  Agents: Default (anything else)                                │       │
│  │                                                                  │       │
│  │  Chain: K2Think ──▶ Gemini ──▶ DeepSeek ──▶ OpenAI ──▶ Claude  │       │
│  │         ┬───────    ┬──────    ┬────────    ┬──────    ┬─────   │       │
│  │         │IDEAL      │fallback1 │fallback2   │fallback3 │last    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════     │
│                                                                             │
│  YOUR CURRENT SETUP (K2Think + Gemini):                                     │
│                                                                             │
│  REASONING → K2Think        (will upgrade to Claude when key is added)      │
│  CREATIVE  → K2Think        (will upgrade to DeepSeek when key is added)    │
│  FAST      → Gemini Flash   ✓ already using ideal model                     │
│  UNIVERSAL → K2Think        ✓ already using ideal model                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. Knowledge Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE INFRASTRUCTURE                             │
│                                                                             │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐ │
│  │  KNOWLEDGE GRAPH (NetworkX)      │   │  VECTOR STORE (Supabase pgvec) │ │
│  │                                  │   │                                 │ │
│  │  Nodes:                          │   │  Embeddings:                    │ │
│  │  ┌──────────┐  ┌──────────┐    │   │  all-MiniLM-L6-v2 (384-dim)    │ │
│  │  │ Paper    │  │ Paper    │    │   │                                 │ │
│  │  │ (primary)│──│ (related)│    │   │  ┌──────────────────────────┐  │ │
│  │  │          │  │          │    │   │  │ Paper chunks             │  │ │
│  │  │ entities:│  │ entities:│    │   │  │ (1500 words, 200 overlap)│  │ │
│  │  │ [clip,   │  │ [bert,   │    │   │  └──────────────────────────┘  │ │
│  │  │  lora,   │  │  glue,   │    │   │                                 │ │
│  │  │  imagenet│  │  distill]│    │   │  ┌──────────────────────────┐  │ │
│  │  │  ...]    │  │          │    │   │  │ Related paper snippets   │  │ │
│  │  └──────────┘  └──────────┘    │   │  └──────────────────────────┘  │ │
│  │       │              │          │   │                                 │ │
│  │       └──── cites ───┘          │   │  Used for:                     │ │
│  │                                  │   │  • Seed deduplication (>0.85)  │ │
│  │  Entity vocabulary: 100+ terms   │   │  • Novelty scoring (sim check)│ │
│  │  Categories:                     │   │  • RAG context for prompts    │ │
│  │  • architectures (transformer…)  │   │                                 │ │
│  │  • training (lora, rlhf…)        │   │  Backend:                      │ │
│  │  • models (gpt-4, llama…)        │   │  Supabase + vecs (postgres)   │ │
│  │  • datasets (imagenet, glue…)    │   │  Fallback: InMemoryVectorStore│ │
│  │  • metrics (bleu, accuracy…)     │   │                                 │ │
│  │  • concepts (scaling law…)       │   │                                 │ │
│  └─────────────────────────────────┘   └─────────────────────────────────┘ │
│                                                                             │
│  USED BY:                                                                   │
│  Stage 2 (Grounding) → Populates KG with related papers                    │
│  Stage 4 (Filtering) → KG overlap_ratio + vector similarity → novelty      │
│  Stage 5 (Refinement) → Critic checks novelty_signal from KG               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. Scoring & Ranking System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HYPOTHESIS SCORING SYSTEM                              │
│                                                                             │
│  6-DIMENSION SCORES (0-100 each)                                            │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │   Novelty ─────── 25%  ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░     │     │
│  │   Feasibility ─── 20%  ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░     │     │
│  │   Impact ──────── 20%  ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░     │     │
│  │   Grounding ───── 15%  ▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░     │     │
│  │   Testability ─── 10%  ▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │     │
│  │   Clarity ──────── 10%  ▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │     │
│  │                                                                    │     │
│  │   Composite = weighted sum → single 0-100 score                   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  SCORING FLOW:                                                              │
│                                                                             │
│  Proposer (LLM-evaluated)     Critic (revised)        Tournament (Elo)      │
│  ┌──────────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ Self-assessment       │───▶│ Adversarial      │───▶│ Pairwise judging │  │
│  │ + seed signal blend   │    │ revision of ALL  │    │ Standard Elo K=32│  │
│  │                       │    │ 6 dimensions     │    │ ΔElo from debates│  │
│  │ novelty = 0.6×LLM    │    │                  │    │                  │  │
│  │         + 0.4×seed    │    │ Verdict gates:   │    │ Proximity pairing│  │
│  │                       │    │ strong: Elo+25   │    │ for competitive  │  │
│  │ feasibility = 0.6×LLM│    │ viable: Elo+0    │    │ matchups         │  │
│  │            + 0.4×cost │    │ weak:   Elo-25   │    │                  │  │
│  └──────────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. External Services & Rate Limiting

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES + RATE LIMITING                         │
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐  │
│  │  arXiv API            │  │  Semantic Scholar     │  │  PapersWithCode │  │
│  │  ─────────            │  │  ────────────────     │  │  ──────────────  │  │
│  │  Rate: 1 req / 3s     │  │  Rate: 10 req / 1s   │  │  Rate: 5 req/1s │  │
│  │                        │  │                       │  │                  │  │
│  │  • fetch_metadata()    │  │  • fetch_paper()      │  │  • datasets()   │  │
│  │  • download_pdf()      │  │  • fetch_related()    │  │  • repositories │  │
│  │                        │  │  • keyword_search()   │  │                  │  │
│  │  Caching: 30 min TTL   │  │  Caching: 15 min TTL  │  │  Caching: 15min │  │
│  └──────────────────────┘  └──────────────────────┘  └─────────────────┘  │
│                                                                             │
│  All API calls use:                                                         │
│  • AsyncRateLimiter (token bucket) — prevents 429 errors                   │
│  • AsyncCache (TTL) — prevents redundant calls across stages               │
│  • httpx.AsyncClient — async HTTP with 30s timeout                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6. Data Flow Summary

```
arXiv ID / PDF
      │
      ▼
 ┌──────────┐    PaperSummary + PaperMetadata
 │ Stage 1  │─── text_chunks → VectorStore
 │ Ingest   │─── entities → KnowledgeGraph
 └────┬─────┘
      │
      ▼
 ┌──────────┐    GapAnalysis (3-5 gaps)
 │ Stage 2  │─── related_papers → KG
 │ Ground   │─── snippets → VectorStore
 └────┬─────┘
      │
      ▼
 ┌──────────┐    ~120 unique HypothesisSeed
 │ Stage 3  │─── structured JSON (not regex)
 │ Generate │─── cosine dedup (0.85)
 └────┬─────┘
      │
      ▼
 ┌──────────┐    ~50 ScoredSeed
 │ Stage 4  │─── parallel scoring (15 concurrent)
 │ Filter   │─── novelty + budget + verifiability
 └────┬─────┘
      │
      ▼
 ┌──────────┐    ~24-48 EnhancedHypothesis
 │ Stage 5  │─── Proposer → Critic → Meta → Evolver
 │ Refine   │─── convergence detection
 └────┬─────┘
      │
      ▼
 ┌──────────┐    Elo-ranked hypotheses
 │ Stage 6  │─── parallel pairwise judging
 │ Tournament│─── 36-72 LLM debates
 └────┬─────┘
      │
      ▼
 ┌──────────┐    GeneratorOutput (top 10)
 │ Stage 7  │─── JSON → NDJSON → Frontend
 │ Output   │
 └──────────┘
```

## 7. Where to Improve Next

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMPROVEMENT ROADMAP                                 │
│                                                                             │
│  PRIORITY 1 — API Keys (immediate quality upgrade)                          │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  ☐ Add DeepSeek API key   → Proposer + Evolver quality ↑↑↑       │     │
│  │  ☐ Add Claude API key     → Critic + Judge quality ↑↑↑↑          │     │
│  │  ☐ Add OpenAI API key     → Creative fallback ↑↑                 │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  PRIORITY 2 — Quality (state-of-the-art output)                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  ☐ Domain-specific prompt variants (CV vs NLP vs Bio prompts)     │     │
│  │  ☐ Citation verification (check if cited papers actually exist)   │     │
│  │  ☐ Human-in-the-loop: let user approve/reject after Stage 4      │     │
│  │  ☐ Multi-paper input (compare 2-3 papers for gap analysis)       │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  PRIORITY 3 — Robustness (production hardening)                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  ☐ Integration tests with mocked LLM responses                    │     │
│  │  ☐ Stage-level timeouts (prevent infinite hangs)                  │     │
│  │  ☐ Token counting (replace char truncation with tiktoken)         │     │
│  │  ☐ Persistent run state (resume interrupted pipelines)            │     │
│  │  ☐ Cost tracking per pipeline run                                 │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  PRIORITY 4 — Scale (handling more papers)                                  │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  ☐ Batch pipeline (process N papers in parallel)                  │     │
│  │  ☐ Redis caching (shared across workers)                          │     │
│  │  ☐ Persistent KG storage (not in-memory per run)                  │     │
│  │  ☐ WebSocket streaming (replace NDJSON polling)                   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
