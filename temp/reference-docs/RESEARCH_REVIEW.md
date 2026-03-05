# VREDA Phase 2 — Research Review & Strategic Improvement Plan

> Research conducted: Feb 2026 | Covers state-of-art through early 2026

---

## 1. Competitive Landscape: Where We Stand

### The Players

| System | What It Does | Strength | Weakness | Relevance to VREDA |
|--------|-------------|----------|----------|---------------------|
| **Elicit** | Literature screening + evidence synthesis | Systematic review automation, data extraction | No hypothesis generation, no code execution | Competes with our Librarian |
| **Consensus** | Answers research questions via paper analysis | Shows scientific consensus with citations | Read-only — no ideation, no experimentation | Competes with our chat RAG |
| **SciSpace** | 280M paper access + chat with papers | Broad coverage, journal matching | No multi-agent pipeline, no experiment design | Competes with our Librarian |
| **OpenAI Deep Research** | Multi-step web research agent | Deep synthesis, clarification questions | Black box, no paper-specific analysis, no code execution | Different paradigm (web-first) |
| **Google NotebookLM** | Source-grounded AI (upload docs) | Excellent grounding, audio summaries | Closed ecosystem, no hypothesis generation | Competes with our RAG |
| **AI Scientist v1** (Sakana, Aug 2024) | End-to-end: idea → code → paper | Full pipeline proof-of-concept | Relied on code templates, hallucinated results | Direct competitor to VREDA's vision |
| **AI Scientist v2** (Sakana, Mar 2025) | Agentic tree search, no templates needed | First AI-generated peer-reviewed workshop paper at ICLR | ML-only, $15-20/run, still workshop-level quality | **Closest competitor** |
| **SciMON** (ACL 2024) | Literature-grounded ideation optimized for novelty | Explicit novelty optimization via iterative comparison | No execution, no verification | Directly informs our Brainstormer |
| **ResearchAgent** (2024) | Iterative idea generation with critic agent | Gap identification via entity-relation graphs | Ideas rated less feasible than human ideas | Informs our agent architecture |
| **FunSearch** (DeepMind, 2024) | LLM + evolutionary search for math discovery | Genuinely novel mathematical results | Extremely narrow domain (cap set problem) | Inspirational but different scope |
| **Coscientist** (CMU, 2024) | Multi-LLM system for autonomous chemistry experiments | Actually ran physical experiments on robotic lab equipment | Chemistry-only, requires physical lab integration | Future inspiration for wet-lab support |

### VREDA's Unique Position

**What nobody else does (our moat):**
1. **Paper → Hypothesis → Budget → Code → Verify** — No system connects ALL these steps
2. **Real external data in the reasoning loop** — Our Research Intelligence pulls GitHub repos, citations, Papers With Code data and feeds it INTO the agents (not just showing it in UI)
3. **Budget-aware experimentation** — The Accountant agent estimates costs BEFORE execution; AI Scientist just runs and bills
4. **Anti-gravity verification** — Planned physics/logic validation is a gap NO competitor fills well

**What competitors do better (our gaps):**
1. **Elicit/Consensus**: Vastly better literature coverage (200M+ papers searchable vs. our single-paper analysis)
2. **AI Scientist v2**: Actually executes experiments end-to-end; we stop at hypothesis
3. **SciMON**: Explicit, measurable novelty optimization; our Brainstormer generates hypotheses but doesn't formally optimize for novelty
4. **Deep Research**: Better at multi-source web synthesis; our system only uses arXiv + Semantic Scholar

---

## 2. Key Research Findings by Area

### A. Hypothesis Generation (The Brainstormer Gap)

**The Stanford Study (Si et al., 2024, arXiv:2409.04109):**
- 100+ NLP researchers compared AI vs human ideas in blind evaluation
- **AI scored higher on novelty (5.64/10 vs 4.84/10, p < 0.05)**
- **AI scored lower on feasibility** (human ideas were more practical)
- **LLMs are bad at self-evaluation** — unreliable at judging their own ideas
- **Implication for VREDA**: Our Brainstormer generates novel ideas, but we need a separate Critic agent to evaluate feasibility. Same-model self-review doesn't work.

**SciMON's Novelty Optimization (ACL 2024):**
- Retrieves "inspiration" papers, generates hypothesis, then iteratively compares against prior work
- If too similar to existing papers → re-generates with explicit "be more different" signal
- Uses semantic similarity graphs + citation networks + knowledge graphs
- **Implication for VREDA**: We should add a novelty check loop — embed generated hypotheses, compare against S2 corpus, iterate if similarity > threshold

**AI Scientist v2 (Sakana, 2025):**
- Eliminated code templates — uses agentic tree search to explore hypothesis space
- Dedicated "Experiment Manager" agent orchestrates exploration
- First AI-generated paper accepted at ICLR workshop
- **Still ML-only**, costs $15-20/run, workshop-level quality (not main conference)
- **Implication for VREDA**: Tree search over hypothesis space is more powerful than our current "generate 3 and pick one" approach

**Open Problem — The Novelty-Feasibility Tradeoff:**
- No system solves this. Novel ideas are impractical; practical ideas are incremental.
- Best current approach: Generate diverse candidates, then have a separate feasibility-checking agent with real-world constraints.

### B. RAG for Scientific Papers (The Librarian Gap)

**Vision-Guided Chunking (2025, arXiv:2506.16035):**
- Current text-only extraction **completely ignores figures, charts, tables, and layout**
- New approach: Use LMMs (Large Multimodal Models) to process PDF pages as images
- Maintains contextual continuity across page boundaries
- **Implication for VREDA**: Our chunker (`src/lib/pdf/chunker.ts`) does naive 1000-char text splitting. We miss ALL visual content — equations, figures, tables.

**Advanced Chunking Strategies (2025, arXiv:2504.19754):**
- Fixed-length chunks split concepts and add noise
- **Semantic chunking** groups text by meaning (better coherence)
- **Late chunking**: Embed the full document first, then chunk the embeddings (preserves global context)
- **Contextual retrieval**: Prepend document-level context to each chunk before embedding
- **Implication for VREDA**: Moving from fixed-size to semantic chunking would improve retrieval quality significantly.

**Scientific Embedding Models:**
- **SPECTER2** (Allen AI): Purpose-built for scientific papers. Trained on 6M citation triplets across 23 fields. Has task-specific adapters (proximity, classification, search).
- **Gemini embedding-001** (what we use): General-purpose, 768-dim. Cheaper but not specialized for science.
- SPECTER2 exhibits "score saturation" for scientific text — very high similarity scores for related papers, needs stricter thresholds.
- **Implication for VREDA**: For scientific paper similarity and retrieval, SPECTER2 embeddings (free via S2 API) would outperform our Gemini embeddings. We could use S2's pre-computed SPECTER2 vectors for paper-level similarity, and keep Gemini for chunk-level RAG.

**HiPerRAG (2025):**
- Scalable exploration of 3.6M+ scientific papers for cross-domain knowledge discovery
- Uses multimodal parsing ("Oreo") + domain-adapted retrieval ("ColTrast")
- **Implication**: Cross-document RAG at scale is achievable but requires specialized retrieval models

### C. Multi-Agent Orchestration (The Strategist Architecture)

**Key Pattern: Structured Artifacts over Free-Form Chat (MetaGPT lesson):**
- Agents that produce typed JSON outputs are far more reliable than agents that chat freely
- VREDA already does this (agents return typed StrategistRoomState) — good architectural choice
- But we should add **Zod validation** at each agent boundary to catch malformed outputs

**The "3-7 Agents" Sweet Spot:**
- Research consensus: 3-7 well-defined agents > 10+ micro-agents
- VREDA has 4 (Parser, Scout, Brainstormer, Accountant) — right range
- **Missing role: Critic/Reviewer agent** — every top system has one

**Self-Reflection Patterns:**
- **Reflexion** (2023): Agent stores reflections from past failures, reads them on retry
- **Self-Refine** (2023): Same model critiques itself — but this has blind spot problems
- **Cross-model critique is superior**: Use a different model (or different temperature) for the critic
- **Implication for VREDA**: Our "refine hypotheses" flow should use a distinct Critic agent, not just re-run the Brainstormer

**Human-in-the-Loop Patterns:**
- Best pattern: Pause at 2-3 strategic decision points (not every step)
- VREDA does this well (select hypothesis → approve budget → approve manifest)
- Could improve: Add "interrupt and edit" — let user modify agent output before passing to next step

**Error Recovery (critical gap in VREDA):**
- **Checkpointing is non-negotiable** for multi-step pipelines
- LangGraph saves state at every node transition
- Our current approach: If one agent fails, the entire pipeline fails
- **Must add**: Pipeline checkpoint saving after each successful step

### D. Literature Discovery (The Librarian Expansion)

**OpenAlex — Major Untapped Resource:**
- 250M+ works, fully open (CC0 license), free API (100K credits/day with key)
- Has hierarchical topic/concept taxonomy (65K concepts linked to Wikidata)
- Better metadata than S2: institutions, funders, topic hierarchy
- **Key capability we're missing**: `concepts` and `topics` fields enable trend analysis and gap detection
- The `related_works` field is algorithmically computed (recent papers with most shared concepts)

**Citation Graph Analysis Techniques We Should Implement:**
1. **Bibliographic coupling** — find papers that share references (conceptual neighbors)
2. **Co-citation analysis** — find papers frequently cited together (intellectual structure)
3. **Structural hole detection** — find gaps between citation clusters (research opportunities)
4. **Citation burst detection** — identify papers with suddenly accelerating citations (emerging frontiers)

**Semantic Scholar's Untapped Features:**
- `influentialCitationCount` — distinguishes meaningful citations from incidental ones
- `/recommendations/v1/papers/` POST endpoint — seed-based paper recommendations
- Pre-computed SPECTER2 embeddings via `fields=embedding`
- These are all free and we're not using any of them

**Papers With Code (partially integrated):**
- We query for code repos — good
- **Missing**: benchmark/SOTA tables, method taxonomies, dataset links
- The `/papers/{id}/results/` endpoint gives state-of-the-art performance tables

---

## 3. Identified Research Problems & Improvement Areas

### PROBLEM 1: Hypothesis Quality is Unmeasured (Critical)

**Current state**: Brainstormer generates 3 hypotheses. User picks one. No quality measurement.

**What the research says**: The Si et al. study proves LLMs generate novel ideas but with low feasibility. SciMON shows iterative novelty optimization works. AI Scientist v2 uses tree search.

**The gap**: We have no novelty scoring, no feasibility checking, no iterative refinement loop.

**Solution — Novelty-Optimized Hypothesis Pipeline:**
1. Generate N candidate hypotheses (not just 3 — generate 10 internally)
2. Embed each hypothesis using SPECTER2 or our existing embeddings
3. Compare against retrieved paper corpus (max cosine similarity)
4. Score: novelty (inverse similarity), feasibility (Critic agent), impact (citation context)
5. Return top 3 diverse hypotheses with scores and evidence
6. If user says "refine" → iterate with explicit "increase novelty" signal (SciMON approach)

### PROBLEM 2: Single-Paper Tunnel Vision (High Impact)

**Current state**: Each conversation analyzes ONE paper. Hypotheses are grounded in one paper's context.

**What the research says**: Real scientific discovery happens at the intersection of multiple papers. Citation graph analysis, co-citation, bibliographic coupling all require multi-paper context.

**The gap**: No cross-paper reasoning. No citation graph navigation.

**Solution — Multi-Paper Research Context:**
1. When a paper is imported, automatically fetch its references and citations (1-hop) via S2 API
2. Use S2 recommendations endpoint to find related papers
3. Build a local "research neighborhood" graph (stored in DB)
4. When generating hypotheses, RAG across ALL papers in the neighborhood
5. Use bibliographic coupling to identify conceptual clusters and gaps between them

### PROBLEM 3: RAG Quality is Naive (Medium Impact)

**Current state**: 1000-char fixed chunks, Gemini general-purpose embeddings, text-only extraction.

**What the research says**: Semantic chunking, vision-guided chunking, and domain-specific embeddings all significantly improve retrieval quality.

**The gap**: We miss figures, tables, equations. Chunks split mid-concept. General embeddings miss scientific nuance.

**Solution — Scientific-Grade RAG:**
1. **Phase 1 (quick win)**: Switch to semantic chunking (split at paragraph/section boundaries, not character count)
2. **Phase 2**: Add S2 SPECTER2 embeddings for paper-level similarity (complement our chunk-level Gemini embeddings)
3. **Phase 3 (ambitious)**: Vision-guided chunking using multimodal models to extract tables/figures as structured data

### PROBLEM 4: No Verification Layer (The Biggest Missing Piece)

**Current state**: Hypotheses are generated and budgeted. No one checks if they violate known science.

**What the research says**: LLM-only verification fails (models confidently assert wrong physics). Tool-augmented verification (code execution, symbolic math, database lookup) is essential. SciFact (Allen AI) provides claim verification against abstracts.

**The gap**: Our "anti_gravity_check" field exists in the schema but is always empty/placeholder.

**Solution — Lightweight Verification Agent (before full Verifier Room):**
1. **Claim extraction**: Extract testable claims from each hypothesis
2. **Literature check**: For each claim, retrieve relevant papers and check for SUPPORT/CONTRADICT/NEUTRAL (SciFact approach)
3. **Dimensional analysis**: If hypothesis involves quantities, verify unit consistency
4. **LLM sanity check**: Separate model call asking "does this violate conservation laws, basic physics, or known results?"
5. **Output**: Verification score + specific flags (no false "looks good" — list exactly what was checked)

### PROBLEM 5: State Recovery is Missing (UX Critical)

**Current state**: Refreshing the page loses strategist state. Phase, session ID, and UI context are gone.

**What the research says**: Checkpointing is "non-negotiable" for multi-step pipelines (every production system does this).

**The gap**: We store state in DB (`strategist_sessions`) but never read it back on page load.

**Solution**: On page load, query `strategist_sessions` for the active conversation. Restore phase + session ID. Re-render the correct UI cards. This is ~30 lines of code but transforms UX.

### PROBLEM 6: No Agent Output Validation (Reliability)

**Current state**: If an LLM returns malformed JSON, the pipeline crashes or shows empty cards.

**What the research says**: MetaGPT's key lesson — structured artifacts with validation at every boundary. Zod schemas for agent outputs.

**The gap**: We parse JSON from LLM responses with no schema validation. Malformed output → silent failure.

**Solution**: Add Zod schemas for every agent's expected output. On validation failure, retry once with "fix your JSON" prompt. This catches 90% of empty-card bugs.

---

## 4. Phase Goals — Making Strategist + Librarian World-Class

### Phase 2A+ Goal Statement

> Make VREDA's Strategist + Librarian the most rigorous AI research ideation system available — where every hypothesis is evidence-grounded, novelty-scored, feasibility-checked, and backed by real citation data from the global research graph.

### Priority Ranking

| Priority | Improvement | Impact | Effort | Why |
|----------|------------|--------|--------|-----|
| **P0** | State recovery on page load | UX-critical | Low (30 lines) | Users can't even use the system reliably without this |
| **P0** | Zod validation for agent outputs | Reliability | Low-Medium | Empty cards and crashes destroy trust |
| **P1** | Novelty-optimized hypothesis generation | Core differentiator | Medium | This is what SciMON does and we don't |
| **P1** | Critic/Reviewer agent | Quality assurance | Medium | Every top system has a critic; we don't |
| **P1** | Multi-paper context (citation neighborhood) | Fundamental capability | Medium | Single-paper analysis is a toy; real research is multi-paper |
| **P2** | OpenAlex integration (topics, trends) | Research landscape | Medium | Enables gap detection, trend analysis |
| **P2** | Semantic chunking | RAG quality | Medium | Replace naive 1000-char chunks |
| **P2** | Lightweight verification agent | Scientific rigor | Medium-High | Fill the anti_gravity_check placeholder |
| **P2** | S2 SPECTER2 embeddings for paper similarity | Discovery quality | Low | Free pre-computed vectors via API |
| **P3** | Pipeline checkpointing | Resilience | Medium | Failure at step 4 shouldn't lose steps 1-3 |
| **P3** | Vision-guided chunking (tables/figures) | RAG completeness | High | Ambitious but scientifically important |
| **P3** | Research gap detection (structural holes) | Unique feature | High | Nobody does this well — research frontier |

---

## 5. Research Problems Worth Publishing

These improvements touch on genuine research problems where VREDA could contribute:

1. **Novelty-Feasibility Balanced Hypothesis Generation**: No system solves the tradeoff. A system that uses real citation data + code availability + budget constraints to balance novelty with practical feasibility would be a contribution.

2. **Citation-Graph-Informed Research Gap Detection**: Using structural holes in citation networks + OpenAlex topic co-occurrence to automatically identify under-explored research intersections. Applied to hypothesis generation, this could be novel.

3. **Multi-Agent Scientific Verification Without Execution**: Verifying scientific hypotheses using literature retrieval + dimensional analysis + symbolic constraint checking (Z3) BEFORE code execution. Most systems verify AFTER execution (if at all).

4. **Budget-Aware Experiment Design**: No system considers computational cost as a design constraint during hypothesis formulation. VREDA's Accountant agent is unique — formalizing this into a "cost-constrained hypothesis optimization" framework could be publishable.

---

## 6. References

### Key Papers
- Si et al., "Can LLMs Generate Novel Research Ideas?" (arXiv:2409.04109, 2024)
- Lu et al., "The AI Scientist-v2" (arXiv:2504.08066, Sakana AI, 2025)
- Wang & Downey, "SciMON: Scientific Inspiration Machines Optimized for Novelty" (ACL 2024)
- Baek et al., "ResearchAgent: Iterative Research Idea Generation" (2024)
- Hong et al., "MetaGPT: Meta Programming for Multi-Agent Collaborative Framework" (2023)
- Du et al., "Improving Factuality through Multiagent Debate" (2023)
- Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023)
- Tripathi et al., "Vision-Guided Chunking for RAG" (arXiv:2506.16035, 2025)
- "Reconstructing Context: Evaluating Advanced Chunking Strategies" (arXiv:2504.19754, 2025)

### Systems & Tools
- [Elicit](https://elicit.com) — Literature screening
- [Consensus](https://consensus.app) — Scientific consensus search
- [SciSpace](https://scispace.com) — Paper analysis + chat
- [OpenAlex](https://openalex.org) — Open scholarly graph (250M+ works)
- [Semantic Scholar API](https://api.semanticscholar.org) — Citations, SPECTER2, recommendations
- [Papers With Code API](https://paperswithcode.com/api/v1/) — Code repos, benchmarks, SOTA tables
- [SPECTER2](https://huggingface.co/allenai/specter2) — Scientific document embeddings
- [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2) — Open source automated discovery
