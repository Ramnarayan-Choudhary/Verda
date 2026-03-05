# VREDA Contracts

Shared API contracts across `apps/web` and room services.

## Scope

- Request/response schemas for room services.
- Progress event schema used for NDJSON streaming.
- Versioned snapshots for backward compatibility.

## Conventions

- Additive changes only for minor versions.
- Breaking changes require a new major folder version.
- Keep TypeScript and Python adapters generated/validated from the same schema files.

## Initial Schemas

- `schemas/room-progress-event.v1.json`
- `schemas/hypothesis-generate-request.v1.json`
- `schemas/hypothesis-generate-response.v1.json`
