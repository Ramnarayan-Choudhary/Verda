# VREDA Hypothesis Module

State-of-the-art hypothesis generation pipeline (LangGraph + multi-agent debate) for the Strategist Room. It ingests an ML/AI paper, over-generates hypotheses, filters for novelty/feasibility, refines via a proposer/critic/evolver/meta loop, runs an Elo tournament, and streams structured hypotheses back to the Next.js app.

## Features
- **Tech stack**: Python 3.12, LangGraph, LangChain, Sentence-Transformers, NetworkX, FastAPI.
- **External grounding**: arXiv, Semantic Scholar, Papers With Code, Tavily, and OpenAI web-search clients with async caching/fallbacks.
- **Knowledge infra**: pgvector-ready vector store (Supabase) with in-memory fallback + lightweight knowledge graph for novelty checks.
- **Multi-agent refinement**: Proposer → Critic → Evolver → Meta Reviewer with Elo tracking and tournament judge prompts based on arXiv:2409.04109 / 2502.18864 / 2510.09901.
- **Practical scoring**: GPU budget heuristics (RunPod rates), verifiability scoring, deduplication, cost-aware filtering.
- **Server**: FastAPI endpoint `/generate` streams NDJSON progress events; `vreda_hypothesis.server:main` boots uvicorn.

## Quickstart
1. `cp .env.example .env` and fill in real keys (see `CONFIG_SETUP.md` + `LLM_PROVIDERS.md`).
2. For stable runs, keep `LLM_FORCE_OPENAI_ONLY=true` so all agent roles use `OPENAI_MODEL` (`gpt-4o` by default).
3. Install dependencies: `pip install -e .[dev]`.
4. Run tests: `pytest`.
5. Start server: `python -m vreda_hypothesis.server` (streams progress + final output).

### Programmatic Usage
```python
import asyncio
from vreda_hypothesis import generate_hypotheses

async def main():
    output = await generate_hypotheses(arxiv_id="2401.12345")
    for hyp in output.hypotheses:
        print(hyp.title, hyp.elo_rating)

asyncio.run(main())
```

## Testing & Quality
- `pytest` covers utilities (cost, dedup, Elo), ingestion chunking, and vector-store fallbacks.
- Ruff config lives in `pyproject.toml` (run `ruff check .`).
- Structured logging via `structlog` across components.

## Folder Map
```
src/vreda_hypothesis/
  agents/        # Proposer, Critic, Evolver, Meta Reviewer, Judge
  external/      # arXiv, Semantic Scholar, PapersWithCode clients
  knowledge/     # NetworkX graph + vector store client
  llm/           # Provider + prompts
  stages/        # Stage implementations (1–7)
  utils/         # Cost, cache, dedup, Elo
  main.py        # LangGraph pipeline
  server.py      # FastAPI streaming server
```

See `ARCHITECTURE.md` (repo root) for the broader Strategist Room context.
