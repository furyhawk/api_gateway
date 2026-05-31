# AGENTS.md

Instructions for AI coding agents in this workspace.

## Project Snapshot
- Primary artifact: `openapi_json/lta_datamall_openapi_v0-1-1.json`
- Repository scope today: OpenAPI specification only (no server implementation files, tests, CI, or package manager config in repo)
- Domain: LTA DataMall bus APIs exposed via a versioned API gateway

## Source of Truth
- Treat `openapi_json/lta_datamall_openapi_v0-1-1.json` as the canonical contract.
- Do not infer runtime behavior beyond what is explicitly defined in the spec.
- Link to existing spec sections instead of duplicating large API descriptions in new docs.

## Working Rules
- Keep JSON valid and consistently formatted with 2-space indentation.
- Preserve existing naming patterns unless asked to refactor:
  - Path versioning style: `/api/v1/...`
  - Health probes: `/healthz`, `/readyz`
  - FastAPI-style `operationId` names
  - Existing query parameter names, including `$skip`
- Prefer additive, backward-compatible API changes for scalability:
  - Add new optional parameters instead of changing required ones.
  - Add new endpoints or response fields rather than removing/changing existing ones.
- For configurability, make behavior explicit in schema/parameters:
  - Define parameter constraints (`minLength`, `maxLength`, `minimum`, enums, nullable) where known.
  - Document defaults and optionality in schema metadata when adding fields.

## Contract Quality Expectations
When editing or adding endpoints, prioritize these improvements:
- Reuse `components/schemas` for shared response/request shapes.
- Avoid unbounded `additionalProperties: true` on new models unless truly required.
- Include non-2xx responses (especially validation/auth/upstream failure) when behavior is known.
- Keep tag groupings coherent (`Health`, `Bus`, etc.) and summaries concise.

## Validation Checklist
Run these checks after spec edits (ad hoc, since no build system is committed):
1. JSON validity check:
   - `python -m json.tool openapi_json/lta_datamall_openapi_v0-1-1.json >/dev/null`
2. Optional structural check (if available locally):
   - `npx @redocly/cli lint openapi_json/lta_datamall_openapi_v0-1-1.json`

## Out of Scope By Default
- Do not scaffold app/server code, infra, or deployment manifests unless explicitly requested.
- Do not rename existing public endpoints/parameters in place unless explicitly requested.

## Key File
- `openapi_json/lta_datamall_openapi_v0-1-1.json`
