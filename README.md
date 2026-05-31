# OpenAPI API Gateway Framework

This repository now includes a lightweight, configurable API gateway framework built with FastAPI.

## What It Provides
- Dynamic gateway routes loaded from YAML (`config/gateway.yaml`)
- Configurable upstream targets and per-upstream timeout settings
- OpenAPI docs for gateway endpoints via FastAPI (`/docs`)
- Optional serving of an external OpenAPI contract (`/openapi/external.json`)
- Built-in management endpoints:
  - `GET /healthz`
  - `GET /readyz`
  - `GET /admin/routes`

## Project Structure
- `src/gateway_framework/app.py`: app factory and dynamic route registration
- `src/gateway_framework/proxy.py`: request forwarding/proxy logic
- `src/gateway_framework/config.py`: config schema and loader
- `src/gateway_framework/main.py`: ASGI entrypoint
- `config/gateway.yaml`: route and upstream configuration
- `openapi_json/lta_datamall_openapi_v0-1-1.json`: external OpenAPI contract

## Quick Start
1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -e .
```

3. Update `config/gateway.yaml` with real upstream URLs.
4. Run the gateway:

```bash
uvicorn gateway_framework.main:app --reload --app-dir src
```

5. Open the docs:
- `http://127.0.0.1:8000/docs`

## Configuration Model
`config/gateway.yaml` uses this model:

```yaml
settings:
  title: string
  version: string
  description: string
  external_openapi_file: path/to/openapi.json

upstreams:
  service_name:
    base_url: https://service.example.com/
    timeout_seconds: 15

routes:
  - path: /api/v1/resource
    methods: [GET, POST]
    upstream: service_name
    upstream_path: /v2/resource
    strip_prefix: /api
    summary: Optional operation summary
    tags: [Gateway]
    operation_id: gateway_resource_get
```

Notes:
- `path` is the public gateway path.
- `upstream_path` overrides forwarded path.
- `strip_prefix` removes a leading path segment before forwarding.

## Scaling and Configurability Guidance
- Add routes through config, not code, for repeatable deployments.
- Split large configurations into environment-specific files and set `GATEWAY_CONFIG_PATH`.
- Keep route changes backward compatible (`/api/v1` stability) for client safety.
- Define explicit timeout values per upstream to isolate slow dependencies.

## Next Steps
- Add auth/rate limiting middleware for production.
- Add OpenAPI linting in CI (for example, Redocly CLI).
- Add contract tests for every configured route.
