# Configuration Cheatsheet

This module runs locally today with mocked keys, but production deploys should replace the placeholder values below. The canonical template is now repo-root `.env.example` and the active file is repo-root `.env.local`.

| Capability | Placeholder | Replace With When Ready |
|------------|-------------|-------------------------|
| **Primary LLM (Proposer/Critic/Evolver/Judge)** | `K2THINK_API_KEY=your-k2think-api-key` | Claude 3.5 Sonnet or GPT-4o keys. Update root `.env.local` and optionally `LLM_PROVIDERS.md` if you swap SDKs. |
| **Fallback LLM** | `OPENROUTER_API_KEY=your-openrouter-api-key` | Direct Gemini (`GEMINI_API_KEY`) or OpenAI key. Adjust `OPENROUTER_BASE_URL`/`MODEL`. |
| **Vector Store** | Supabase fields left blank in root `.env.example` | Set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`. The vector store automatically uses pgvector (via `vecs`) once these are present. |
| **Semantic Scholar** | `SEMANTIC_SCHOLAR_API_KEY=` (empty) | Paste the real API key to unlock higher rate limits for gap analysis + novelty checks. |
| **GitHub / PapersWithCode** | No key required | If you have a GitHub token, set `GITHUB_TOKEN` to avoid low rate limits when fetching repo stats. |
| **Server** | `HOST=0.0.0.0`, `PORT=8000` | Override per environment or leave defaults for local dev. |

## Swapping Instructions

1. **Create root `.env.local`** by copying root `.env.example` and replacing placeholders.
2. **LLM Choice**: if you switch away from K2 Think or OpenRouter, edit `vreda_hypothesis/llm/provider.py` — both clients are initialized in `_init_clients()`. Swap the SDK imports and set `model_kwargs` as needed (see `LLM_PROVIDERS.md` for examples).
3. **Vector Store**: once Supabase credentials are present, the `VectorStoreClient` automatically provisions/uses the `vreda_hypothesis` collection inside pgvector. No code changes required.
4. **External APIs**: Semantic Scholar + arXiv are public, but keys let you exceed default quotas. Fill `SEMANTIC_SCHOLAR_API_KEY` to enable header-based auth. For Papers With Code, no key is required right now.

Always restart servers after updating root `.env.local` so settings reload.
