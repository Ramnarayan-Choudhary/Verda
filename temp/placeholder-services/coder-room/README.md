# Coder Room (Planned)

Owns repository-aware code synthesis and patch generation for approved experiments.

## Responsibilities

- Generate code patches from experiment plans.
- Run static checks and targeted tests.
- Produce change sets with risk annotations.

## API (target)

- `POST /jobs`
- `GET /jobs/{id}`
- `GET /jobs/{id}/stream`
