# Verifier Room (Planned)

Owns correctness and safety validation for generated experiments and code patches.

## Responsibilities

- Verify metric claims and experiment reproducibility.
- Run policy/safety checks before final approval.
- Emit pass/fail with evidence and required fixes.

## API (target)

- `POST /jobs`
- `GET /jobs/{id}`
- `GET /jobs/{id}/stream`
