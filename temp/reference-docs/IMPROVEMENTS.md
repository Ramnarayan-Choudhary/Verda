# VREDA.ai — Improvement Tracker

> Living document. Remove items as they're completed. Last updated: 2026-02-11.

---

## How to Use This File

- **DONE items** → delete the entire block
- **In-progress** → move to top of its section, add `[WIP]` prefix
- **New improvement discovered** → add to the relevant section with priority tag

Priority tags: `[P0]` Critical, `[P1]` High, `[P2]` Medium, `[P3]` Nice-to-have

---

## 1. PDF Text Extraction — Currently WEAK

**Current**: `pdf-parse` — basic text-only extraction.

### Problems
- Loses all structural information (sections, headings, figure captions)
- Tables rendered as garbled text
- Multi-column layouts get interleaved incorrectly
- Mathematical equations become garbage (LaTeX symbols lost)
- Scanned/image-based PDFs return nothing

### Improvements

#### `[P1]` Switch to Marker PDF
- **What**: Replace `pdf-parse` with `marker-pdf` (Python library)
- **Why**: Preserves structure, extracts tables as markdown, handles equations
- **How**: Run as Python microservice or subprocess from Node.js
- **Effort**: Medium — requires Python sidecar, Docker for deployment
- **Impact**: HIGH — garbage in = garbage out for entire pipeline

#### `[P2]` Add OCR Fallback for Image-Based PDFs
- **What**: Detect image-only PDFs and route through Nougat (Meta) or Tesseract
- **Why**: Some papers are scanned PDFs with zero extractable text
- **How**: Check if extracted text is empty/short → trigger OCR pipeline
- **Research**: Nougat (Meta) — neural OCR trained specifically on academic papers, outputs clean markdown with LaTeX
- **Effort**: Medium
- **Impact**: MEDIUM — unlocks papers that currently fail completely

#### `[P3]` Docling (IBM) for Document Understanding
- **What**: Full document understanding with layout analysis
- **Why**: Can identify figures, tables, equations, citations as first-class objects
- **Research**: IBM Docling — document intelligence, goes beyond text extraction
- **Effort**: High — significant integration work
- **Impact**: HIGH but long-term

---

## 2. Chunking Strategy — Currently MODERATE

**Current**: 1000-char chunks, 200-char overlap, recursive character splitting.

### Improvements

#### `[P1]` Section-Aware Chunking
- **What**: Parse paper sections first (Abstract, Methods, Results, etc.), chunk within each section, tag chunks with section name
- **Why**: Current chunking mixes abstract text with methodology — confuses retrieval
- **How**: Use heading detection from PDF extraction, split by section, then apply recursive chunking within each section. Store `section` field in `document_chunks` table
- **Effort**: Medium — needs better PDF extraction first (see Section 1)
- **Impact**: HIGH — agents get cleaner, contextually coherent chunks

#### `[P1]` Contextual Retrieval (Anthropic Technique)
- **What**: Before embedding each chunk, prepend a short context sentence explaining where this chunk fits in the paper
- **Why**: Anthropic research showed **49% fewer retrieval failures** with this technique
- **How**: For each chunk, make a cheap LLM call: "Summarize this chunk's role in the paper in 1 sentence" → prepend to chunk → then embed
- **Cost**: ~$0.001 extra per paper (one cheap LLM call per chunk)
- **Research**: https://www.anthropic.com/news/contextual-retrieval
- **Effort**: Low-Medium
- **Impact**: VERY HIGH — single biggest RAG quality improvement available

#### `[P2]` Parent-Child Chunking
- **What**: Store large chunks (1500 chars) AND small chunks (500 chars). Retrieve by small chunk similarity, but return the parent chunk for context
- **Why**: Small chunks match queries better, large chunks give agents more context
- **How**: Add `parent_chunk_id` column to `document_chunks`, retrieve small → lookup parent
- **Effort**: Medium
- **Impact**: MEDIUM — improves context quality for agents

#### `[P3]` Semantic Chunking
- **What**: Use sentence embeddings to detect topic shifts, split at natural semantic boundaries instead of character count
- **Why**: Fixed-size chunking often cuts mid-argument
- **How**: Embed each sentence, compute cosine similarity between consecutive sentences, split where similarity drops below threshold
- **Effort**: Medium-High
- **Impact**: MEDIUM

---

## 3. Vector Search & RAG Retrieval — Currently MODERATE

**Current**: HNSW index, cosine similarity top-K, single query, no reranking.

### Improvements

#### `[P1]` Hybrid Search (BM25 + Vector)
- **What**: Combine keyword matching (BM25/tsvector) with semantic vector search, merge results using Reciprocal Rank Fusion
- **Why**: Pure semantic search misses exact keyword matches (e.g., searching "BERT" won't match if embedding is about "transformer models"). BM25 catches these
- **How**:
  1. Add `tsvector` column to `document_chunks` table
  2. Create GIN index on tsvector column
  3. Query both: `ts_rank()` for keyword score + `1 - cosine_distance` for semantic score
  4. Merge using RRF: `score = 1/(k + rank_bm25) + 1/(k + rank_vector)`
- **SQL Migration needed**: Add `search_vector tsvector` column, trigger to auto-populate
- **Effort**: Medium
- **Impact**: HIGH — catches queries that pure semantic search misses

#### `[P1]` Multi-Query Retrieval
- **What**: For each user query, generate 3-5 query variants using LLM, search all of them, deduplicate and merge results
- **Why**: Single query misses multi-faceted questions. "What datasets and training methods were used?" needs separate retrieval for "datasets" and "training methods"
- **How**: Quick LLM call to generate query variants → parallel vector searches → merge by document ID → take top-K unique
- **Cost**: 1 extra LLM call per query (~$0.0005)
- **Effort**: Low-Medium
- **Impact**: HIGH for complex questions

#### `[P2]` Reranking with Cross-Encoder
- **What**: Retrieve top-20 chunks by vector search, then use a cross-encoder model to rerank and return top-5
- **Why**: Bi-encoder (embedding) search is fast but approximate. Cross-encoder compares query+document together for higher precision
- **How**: Use Cohere Rerank API or open-source `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Effort**: Medium
- **Impact**: HIGH — significantly better relevance for top results

#### `[P3]` Metadata Filtering
- **What**: Add section name, page number, and content type (text/table/equation) to chunks, allow filtered retrieval
- **Why**: When user asks about "methodology", only retrieve from Methods section
- **How**: Extend `document_chunks` schema with metadata columns, add filters to `match_chunks` function
- **Effort**: Medium — needs section-aware chunking first
- **Impact**: MEDIUM

---

## 4. Strategist Room Agents — Currently GOOD

**Current**: 4 agents with per-agent temperature tuning, JSON output, retry logic.

### Improvements

#### `[P1]` Pre-Extraction Tools for Scout Agent
- **What**: Before calling Scout LLM, use regex to extract all URLs, GitHub links, and email addresses from paper text. Pass these as structured input to Scout
- **Why**: Scout currently relies on LLM to find URLs in text — hallucination-prone. Regex is 100% accurate for URL detection
- **How**: Add `extractUrls(text)` utility, run before Scout call, pass extracted URLs in prompt
- **Effort**: Low
- **Impact**: HIGH — eliminates URL hallucination entirely

#### `[P2]` Self-Consistency Check for Parser
- **What**: Run Parser twice with slightly different temperatures, compare outputs, flag disagreements
- **Why**: Parser might hallucinate datasets or metrics that aren't in the paper. Two runs help catch inconsistencies
- **How**: `runParserAgent()` twice (temp 0.1 and 0.15), compare key fields, flag differences as `low_confidence`
- **Cost**: Doubles Parser cost (~$0.001 extra)
- **Effort**: Medium
- **Impact**: MEDIUM — catches hallucinations before they propagate

#### `[P2]` Streaming Progress Feedback
- **What**: Send SSE events to frontend during multi-agent orchestration: "Parser running...", "Parser complete. Scout running..."
- **Why**: Upload currently shows a spinner with no feedback for 10-15 seconds. Users think it's stuck
- **How**: Use `ReadableStream` with SSE format in upload route, frontend listens for progress events
- **Effort**: Medium
- **Impact**: MEDIUM — much better UX, looks more professional

#### `[P2]` Confidence Scores per Agent
- **What**: Each agent returns a `confidence: 0-100` field alongside its output
- **Why**: Low confidence signals that the agent is uncertain — UI can show warnings, user can retry
- **How**: Add `confidence` to each agent's prompt instructions and output type
- **Effort**: Low
- **Impact**: LOW-MEDIUM — better UX, informs downstream decisions

#### `[P3]` LLM-as-Judge Verification
- **What**: After Parser extracts claims, run a verification pass that checks each claim against the source text
- **Why**: Catches hallucinated claims before they reach the user
- **Research**: "LLM-as-judge" pattern — use a separate LLM call to verify another LLM's output
- **Effort**: Medium
- **Impact**: MEDIUM — reduces hallucination in displayed results

---

## 5. LLM Strategy — Currently MODERATE

**Current**: Gemini 2.0 Flash for all agents via OpenRouter.

### Improvements

#### `[P2]` Tiered Model Selection
- **What**: Use different models per agent based on task requirements
- **Why**: Brainstormer needs creative scientific reasoning (stronger model), Parser just needs extraction (Flash is fine)
- **Recommended Tiering**:
  | Agent | Model | Why |
  |-------|-------|-----|
  | Parser | Gemini 2.0 Flash | Extraction task, Flash excels |
  | Scout | Gemini 2.0 Flash | Classification, Flash fine |
  | Brainstormer | Claude Sonnet or GPT-4o | Creative scientific reasoning |
  | Accountant | Gemini 2.0 Flash | Arithmetic/estimation |
  | Chat (RAG) | Gemini 2.0 Flash | Streaming speed |
- **How**: Add optional `model` parameter to `makeAgentCall()`, each agent passes its preferred model
- **Cost**: ~$0.01 extra per session for stronger Brainstormer model
- **Effort**: Low
- **Impact**: MEDIUM — better hypotheses for investor demo

#### `[P3]` LLM Response Caching
- **What**: Cache identical or near-identical LLM calls (same paper + same query = cached result)
- **Why**: Re-running Parser on the same paper wastes tokens and money
- **How**: Hash (prompt + model + temperature) → check cache before calling → store result with TTL
- **Effort**: Medium
- **Impact**: LOW — saves money at scale, not critical for MVP

#### `[P3]` Fallback Model Chain
- **What**: If primary model fails or returns bad output, automatically try a different model
- **Why**: Single model dependency is fragile. OpenRouter outages, rate limits, etc.
- **How**: Extend `makeAgentCall()` retry logic: on final failure, try fallback model
- **Effort**: Low
- **Impact**: LOW — reliability improvement

---

## 6. Observability & Cost Tracking — Currently MISSING

**Current**: `logger.info/warn/error` — good for debugging, no structured metrics.

### Improvements

#### `[P2]` Structured Agent Metrics
- **What**: Log structured data for every LLM call: tokens in/out, duration, model, cost
- **Why**: Need real data for: Accountant accuracy, cost optimization, investor metrics
- **Format**:
  ```json
  {
    "agent": "ParserAgent",
    "model": "gemini-2.0-flash",
    "tokens_in": 3200,
    "tokens_out": 800,
    "duration_ms": 2400,
    "cost_usd": 0.0042,
    "document_id": "uuid",
    "session_id": "uuid"
  }
  ```
- **How**: Wrap `makeAgentCall()` to capture OpenRouter response headers (include token counts)
- **Effort**: Low-Medium
- **Impact**: MEDIUM — essential before Phase 3 scaling

#### `[P2]` Per-Session Cost Dashboard
- **What**: Track actual cost per paper upload (sum of all LLM calls in session)
- **Why**: Investor demo: "Each research quest costs $0.008". Accountant agent should use real data
- **How**: Store cost per session in `strategist_sessions.state`, expose via API
- **Effort**: Medium
- **Impact**: MEDIUM — impressive for demo

#### `[P3]` Error Analytics
- **What**: Track which papers fail most often, at which stage, and why
- **Why**: Identify patterns (e.g., "multi-column PDFs always fail at extraction")
- **How**: Add `error_logs` table or extend `strategist_sessions` with structured error data
- **Effort**: Low
- **Impact**: LOW — useful for debugging patterns at scale

---

## 7. Frontend & UX — Currently MODERATE

**Current**: Redesigned PaperAnalysis/CodePath cards, dark theme, responsive layout.

### Improvements

#### `[P2]` LaTeX Equation Rendering
- **What**: Render equations as proper mathematical notation instead of raw LaTeX strings
- **Why**: Raw LaTeX like `\sqrt{1-\beta_{t}}` is unreadable for most users
- **How**: Integrate KaTeX (lightweight, fast) — `npm install katex`, render in PaperAnalysisCard
- **Effort**: Low
- **Impact**: MEDIUM — dramatically better visual quality for equations

#### `[P2]` Paper Upload Progress Bar
- **What**: Multi-step progress indicator: Upload → Extract → Chunk → Embed → Analyze
- **Why**: Current upload shows a generic spinner for 10-15 seconds with no feedback
- **How**: Use SSE from upload route (see agent streaming above), frontend renders step-by-step progress
- **Effort**: Medium
- **Impact**: MEDIUM — much better UX

#### `[P3]` Hypothesis Comparison View
- **What**: Side-by-side comparison of 3 hypotheses with visual diff highlighting
- **Why**: Current HypothesisSelector shows cards vertically — hard to compare
- **How**: Three-column layout with aligned fields, color-coded feasibility/confidence bars
- **Effort**: Low-Medium
- **Impact**: LOW — aesthetic improvement

#### `[P3]` Dark/Light Theme Toggle
- **What**: Allow users to switch between dark and light themes
- **Why**: Some users prefer light theme, especially for reading papers
- **How**: CSS custom properties already in place, add theme toggle in header
- **Effort**: Medium
- **Impact**: LOW — nice-to-have

---

## Completed Improvements (Archive)

> Move completed items here with date for historical reference.

| Date | Area | Improvement | Details |
|------|------|-------------|---------|
| 2026-02-11 | Embeddings | Task-type parameters | `RETRIEVAL_DOCUMENT` for storage, `RETRIEVAL_QUERY` for search |
| 2026-02-11 | Agents | Temperature tuning per agent | Parser: 0.1, Scout: 0.15, Brainstormer: 0.7, Accountant: 0.1 |
| 2026-02-11 | Vector Search | HNSW index migration | Replaced IVFFlat with HNSW (better recall) |
| 2026-02-11 | Chunking | Larger chunks + overlap | 500→1000 chars, 50→200 char overlap |
| 2026-02-11 | UI | PaperAnalysisCard redesign | Title cleanup, 2-column grid, collapsible equations, smart metrics |
| 2026-02-11 | UI | CodePathCard redesign | Compact layout, stats row, algorithm list with badges |

---

## Priority Execution Order

When funding arrives, execute in this order for maximum demo impact:

| Order | Item | Section | Effort | Why First |
|-------|------|---------|--------|-----------|
| 1 | Contextual Retrieval | 2 | Low-Med | 49% fewer retrieval failures (Anthropic research) |
| 2 | Hybrid Search (BM25 + Vector) | 3 | Medium | Catches keyword matches semantic search misses |
| 3 | Pre-extraction tools for Scout | 4 | Low | Eliminates URL hallucination |
| 4 | Multi-Query Retrieval | 3 | Low-Med | Better results for complex questions |
| 5 | Structured Agent Metrics | 6 | Low-Med | Need real cost data before Phase 3 |
| 6 | LaTeX Equation Rendering | 7 | Low | Dramatically better visual quality |
| 7 | Marker PDF extraction | 1 | Medium | Foundation-level improvement |
| 8 | Reranking | 3 | Medium | Significant retrieval quality jump |
| 9 | Tiered Model Selection | 5 | Low | Better hypotheses for demo |
| 10 | Streaming Progress | 4 | Medium | Professional UX |
