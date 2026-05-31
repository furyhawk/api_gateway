# OpenAPI API Gateway Framework

This repository now includes a lightweight, configurable API gateway framework built with FastAPI.

## What It Provides
- Dynamic gateway routes loaded from YAML (`config/gateway.yaml`)
- Configurable upstream targets and per-upstream timeout settings
- OpenAPI docs for gateway endpoints via FastAPI (`/docs`)
- Optional serving of an external OpenAPI contract (`/openapi/external.json`)
- Administrative portal at `/admin/portal`
- Runtime configuration editor via admin endpoints
- API key creation/list/revocation with optional route protection
- Built-in management endpoints:
  - `GET /healthz`
  - `GET /readyz`
  - `GET /admin/routes`

## Project Structure
- `src/gateway_framework/app.py`: app factory and dynamic route registration
- `src/gateway_framework/proxy.py`: request forwarding/proxy logic
- `src/gateway_framework/config.py`: config schema and loader
- `src/gateway_framework/main.py`: ASGI entrypoint
- `src/gateway_framework/static/admin/`: scalable portal frontend assets (`index.html`, `styles.css`, `app.js`)
- `config/gateway.yaml`: route and upstream configuration
- `openapi_json/lta_datamall_openapi_v0-1-1.json`: external OpenAPI contract

## Quick Start
1. Install `uv` if not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Sync dependencies and create the project virtual environment:

```bash
uv sync
```

3. Update `config/gateway.yaml` with real upstream URLs.
4. Run the gateway with the managed environment:

```bash
uv run uvicorn gateway_framework.main:app --reload --app-dir src
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
  cache_enabled: false
  cache_ttl_seconds: 30
  cache_max_entries: 500
  require_api_key: false
  api_keys_file: config/api_keys.json
  admin_api_key_env: ADMIN_API_KEY

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

## Administrative Portal and Dashboard
- Admin UI: `GET /admin/portal`
- Admin static assets: `GET /admin/portal/assets/*`
- Admin summary: `GET /admin/dashboard`
- Get config YAML: `GET /admin/config`
- Save config YAML: `PUT /admin/config`
- List API keys: `GET /admin/api-keys`
- Create API key: `POST /admin/api-keys` with body `{"name":"client-name"}`
- Revoke API key: `DELETE /admin/api-keys/{key_id}`

Optional admin auth:
- Set environment variable `ADMIN_API_KEY` before startup.
- Send header `x-admin-key: <your-admin-key>` to admin endpoints.

## API Key Protection for Gateway Routes
- Enable gateway key checks by setting `settings.require_api_key: true`.
- Clients then must send `x-api-key: <key>` on proxied route requests.
- Create keys from the admin portal or `POST /admin/api-keys`.

## Response Cache
- Enable cache with `settings.cache_enabled: true`.
- Configure TTL with `settings.cache_ttl_seconds`.
- Configure memory bound with `settings.cache_max_entries`.
- Cache currently applies to proxied `GET`/`HEAD` responses with `2xx` status.
- Gateway adds `x-gateway-cache: MISS` for first fetch and `x-gateway-cache: HIT` for cached responses.

## Scaling and Configurability Guidance
- Add routes through config, not code, for repeatable deployments.
- Split large configurations into environment-specific files and set `GATEWAY_CONFIG_PATH`.
- Keep route changes backward compatible (`/api/v1` stability) for client safety.
- Define explicit timeout values per upstream to isolate slow dependencies.

## Next Steps
- Add auth/rate limiting middleware for production.
- Add OpenAPI linting in CI (for example, Redocly CLI).
- Add contract tests for every configured route.

## Common uv Commands
- Run tests: `uv run pytest`
- Run lint: `uv run ruff check .`
- Add dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`

## Container (Docker or Podman) + Makefile
The repository includes a containerized workflow via `Dockerfile` and `Makefile`.

### Prerequisites
- Install either Docker or Podman.
- By default, Makefile uses Podman when available; otherwise Docker.

### Build Image
```bash
make build
```

### Run Container
```bash
make run
```

Gateway will be available at `http://127.0.0.1:8000`.

### Stop and Inspect
```bash
make logs
make stop
```

### Useful Variables
- `CONTAINER_ENGINE=docker` (or `podman`)
- `PORT=8080`
- `IMAGE_NAME=openapi-api-gateway`
- `IMAGE_TAG=latest`
- `ENV_FILE=.env`

Example:
```bash
make build CONTAINER_ENGINE=docker IMAGE_TAG=dev
make run CONTAINER_ENGINE=docker PORT=8080 ENV_FILE=.env
```

## GitHub Packages (GHCR)
- Automated image publishing is configured in `.github/workflows/release-image.yml`.
- On push of a release tag (for example `v0.2.0`), CI builds and pushes:
  - `ghcr.io/furyhawk/api_gateway:v0.2.0`
  - `ghcr.io/furyhawk/api_gateway:latest`

Pull example:
```bash
docker pull ghcr.io/furyhawk/api_gateway:v0.2.0
```
