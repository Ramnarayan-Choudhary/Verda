# Hypo-GPT

Standalone GPT-focused hypothesis generation engine.

## Run

```bash
cd services/hypothesis-room/hypo-gpt
PYTHONPATH=src:.. python -m hypo_gpt.server
```

## Endpoints

- `GET /healthz`
- `POST /generate` (NDJSON stream)
