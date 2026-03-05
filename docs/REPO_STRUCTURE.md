# Repo Structure Plan

## Goals

1. Keep UI concerns and AI room execution concerns separate.
2. Reuse one contract model across TypeScript and Python.
3. Make new rooms (Experiment, Coder, Verifier) follow the same scaffold.
4. Preserve backward compatibility during migration.

## Current Ownership

- `apps/web`
  - User-facing product, auth, chat UX, session state, streaming UI.
  - Acts as API gateway and orchestration entrypoint.

- `services/hypothesis-room`
  - Paper ingestion, external grounding, seed generation, refinement loop, tournament ranking.
  - Exposes `POST /generate` and NDJSON progress stream.

- `packages/contracts`
  - Source-of-truth request/response schemas and event shapes.
  - Service APIs should version from this package.

## Service Contract Pattern (for all rooms)

Each room follows the same endpoint model:

- `POST /jobs` create job
- `GET /jobs/{id}` poll status and output
- `GET /jobs/{id}/stream` progress stream

Room-specific payload lives inside job input/output schemas, but endpoint shape stays consistent.

## Migration Rules

1. No room-specific heavy logic inside `apps/web`.
2. Any schema change starts in `packages/contracts`, then propagated to:
   - TypeScript validators in `apps/web`
   - Pydantic models in room services
3. Keep `vreda-app` and `vreda-hypothesis` path aliases until all scripts/CI references are updated.
4. Add one room at a time with identical skeleton (`README`, `src`, `tests`, `.env.example`).

## Immediate Next Integration Step

Wire `apps/web/src/app/api/strategist/hypothesize/route.ts` to call the hypothesis service behind a feature flag:

- `HYPOTHESIS_ENGINE_MODE=ts|python`
- `HYPOTHESIS_SERVICE_URL=http://127.0.0.1:8000`

Default to `ts` for safe rollout, then switch to `python` after parity checks.

## Quality Gates

- Room service must have unit tests and smoke API tests.
- Contracts package must provide schema fixtures.
- Web gateway must include adapter tests for room response mapping.
