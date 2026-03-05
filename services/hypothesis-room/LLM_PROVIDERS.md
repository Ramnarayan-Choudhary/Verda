# LLM Provider Configuration — Tiered Routing Guide

## Architecture: Role-Based Model Routing

VREDA Hypothesis uses **tiered LLM routing** — each agent role is mapped to its ideal model tier. When that model isn't configured, the system automatically falls back through the priority chain.

**When only ChatAnywhere is configured, ALL tiers are covered via one API key.**

## Tier Strategy

| Tier | Agent Roles | ChatAnywhere Model | Why |
|------|-------------|-------------------|-----|
| **REASONING** | Critic, Meta-Reviewer, Tournament Judge, Gap Analysis | `deepseek-r1-0528` | Deep analytical thinking, finds flaws |
| **CREATIVE** | Proposer, Evolver, Seed Generation | `deepseek-v3` | Fast divergent thinking + novel recombination |
| **FAST** | Paper Extraction, Verifiability, Filtering | `gpt-4o-mini-ca` | Speed + structured JSON output, low cost |
| **UNIVERSAL** | Default / anything else | `deepseek-v3` | Good all-around creative model |

## Fallback Chains

Each tier has a priority chain. The system uses the first available provider:

```
REASONING:  ChatAnywhere/deepseek-r1 → Anthropic Claude → DeepSeek direct → ChatAnywhere/deepseek-v3 → K2Think → OpenRouter
CREATIVE:   ChatAnywhere/deepseek-v3 → DeepSeek direct → OpenAI → ChatAnywhere/deepseek-r1 → K2Think → OpenRouter
FAST:       ChatAnywhere/gpt-4o-mini → OpenRouter/Gemini → K2Think → ChatAnywhere/deepseek-v3 → OpenAI → DeepSeek
UNIVERSAL:  ChatAnywhere/deepseek-v3 → K2Think → OpenRouter → ChatAnywhere/gpt-4o-mini → DeepSeek → OpenAI
```

## Provider Matrix

| Provider | Env Prefix | Default Model(s) | API Format |
|----------|-----------|-------------------|------------|
| **ChatAnywhere** (primary) | `CHATANYWHERE_` | `deepseek-r1-0528`, `deepseek-v3`, `gpt-4o-mini-ca` | OpenAI-compatible |
| **K2Think** | `K2THINK_` | `MBZUAI-IFM/K2-Think-v2` | OpenAI-compatible |
| **OpenRouter** | `OPENROUTER_` | `google/gemini-2.0-flash-001` | OpenAI-compatible |
| **DeepSeek** | `DEEPSEEK_` | `deepseek-reasoner` | OpenAI-compatible |
| **OpenAI** | `OPENAI_` | `gpt-4o` | Native OpenAI |
| **Anthropic** | `ANTHROPIC_` | `anthropic/claude-sonnet-4-5-20250929` | Via OpenRouter |

## Setup Scenarios

### Minimal (ChatAnywhere only) — RECOMMENDED FOR GETTING STARTED
```env
CHATANYWHERE_API_KEY=your-key
CHATANYWHERE_BASE_URL=https://api.chatanywhere.tech/v1
```
One API key covers all 3 tiers. Each agent uses its ideal model class:
- REASONING agents → `deepseek-r1-0528`
- CREATIVE agents → `deepseek-v3`
- FAST agents → `gpt-4o-mini-ca`

### Enhanced (ChatAnywhere + Gemini Flash)
```env
CHATANYWHERE_API_KEY=your-key
OPENROUTER_API_KEY=your-openrouter-key
```
FAST tier can also use Gemini Flash as an alternative.

### Maximum Quality (ChatAnywhere + Claude)
```env
CHATANYWHERE_API_KEY=your-key
ANTHROPIC_API_KEY=your-openrouter-key-for-claude
ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
```
REASONING tier upgrades to Claude Sonnet for the strongest critique.

### All Providers
```env
CHATANYWHERE_API_KEY=your-key
K2THINK_API_KEY=your-key
OPENROUTER_API_KEY=your-openrouter-key
DEEPSEEK_API_KEY=your-deepseek-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-openrouter-key-for-claude
```

## How to Add a New Provider

1. Add env vars to `.env`:
   ```env
   DEEPSEEK_API_KEY=your-key
   # DEEPSEEK_BASE_URL and DEEPSEEK_MODEL have sane defaults
   ```

2. Restart the server. The provider auto-registers and the tier chains update.

3. Check which models are active:
   ```bash
   curl http://localhost:8000/healthz
   ```

## Provider Comparison

| Provider | Reasoning | Creativity | Speed | Cost/1M tokens | JSON Reliability |
|----------|-----------|-----------|-------|----------------|-----------------|
| ChatAnywhere/deepseek-r1 | **Strong** | Good | Slow (~2min) | $0.55/$2.19 | Good (no json_object mode) |
| ChatAnywhere/deepseek-v3 | Good | **Strong** | Fast (~10s) | $0.27/$1.10 | **Excellent** |
| ChatAnywhere/gpt-4o-mini | Moderate | Moderate | **Fast** (~2s) | $0.15/$0.60 | **Excellent** |
| Gemini Flash | Moderate | Moderate | **Fast** | $0.075/$0.30 | **Excellent** |
| K2Think | Good | Good | Moderate | ~$0.50/$2.00 | Good |
| GPT-4o | Strong | Strong | Fast | $2.50/$10.00 | Excellent |
| Claude Sonnet | **Strongest** | Strong | Moderate | $3.00/$15.00 | Good |

## Cost Tracking

The pipeline automatically tracks token usage and estimated costs per run. After each pipeline execution, you'll see a log entry like:

```
pipeline.token_usage  prompt_tokens=15000  completion_tokens=8000  total_tokens=23000  estimated_cost_usd=0.0125
```

Cost estimation uses known per-model rates. When the API doesn't report token counts (some proxied endpoints), the system estimates tokens from character counts (~4 chars/token).

## Important Notes

- **deepseek-r1-0528** does NOT support `response_format: {"type": "json_object"}`. The provider is configured without it, and JSON is extracted from the raw response via regex parsing.
- **ChatAnywhere** may not return token usage metadata in all responses. The system falls back to character-based estimation for cost tracking.
- All providers use the OpenAI-compatible API format via `langchain-openai`'s `ChatOpenAI`.
