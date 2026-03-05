# Experiment Room (Planned)

Owns experiment planning and execution graph generation from approved manifests.

## Responsibilities

- Convert selected hypothesis into execution-ready experiment DAG.
- Build dataset/runtime/tool requirements.
- Estimate runtime and checkpoint plan.

## API (target)

- `POST /jobs`
- `GET /jobs/{id}`
- `GET /jobs/{id}/stream`
