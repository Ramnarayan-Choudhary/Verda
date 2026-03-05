# VREDA Monorepo

VREDA is organized as a service-oriented monorepo so product UI, room engines, and shared contracts evolve independently while staying aligned.

## Repository Layout

```text
apps/
  web/                     # Next.js product UI + API gateway

services/
  hypothesis-room/         # Python LangGraph hypothesis generation engine
  experiment-room/         # Planned room: experiment design/execution planning
  coder-room/              # Planned room: code synthesis/patching
  verifier-room/           # Planned room: validation, safety, regression checks

packages/
  contracts/               # Shared JSON schemas + API contracts across services

docs/
  REPO_STRUCTURE.md        # Architecture and ownership plan
```

## Current Runtime

- Web app: `apps/web`
- Hypothesis service: `services/hypothesis-room`

Legacy aliases are kept for compatibility:
- `vreda-app` -> `apps/web`
- `vreda-hypothesis` -> `services/hypothesis-room`

## Why this structure

- Keeps room logic outside the web app, so each room can scale independently.
- Prevents schema drift by centralizing contracts in `packages/contracts`.
- Makes future room onboarding predictable (same API shape, same lifecycle).

Read `docs/REPO_STRUCTURE.md` for ownership, migration, and integration rules.

## Local Development

- Start both web and hypothesis service:
  - `./scripts/dev-up.sh`
- Or run them separately:
  - Web: `cd apps/web && npm run dev`
  - Hypothesis: `cd services/hypothesis-room && source .venv/bin/activate && python -m vreda_hypothesis.server`
