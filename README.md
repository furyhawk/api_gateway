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

3. Choose a gateway profile:
- `config/gateway.yaml` targets a locally running companion backend on `127.0.0.1:8068`.
- `config/gateway.container.yaml` targets the companion backend inside the bundled compose network.
4. Run the gateway with the managed environment:

```bash
make run-local CONFIG_PROFILE=local
```

5. Open the docs:
- `http://127.0.0.1:8000/docs`

## Companion Backend Integration
This gateway is a good front door for the companion backend at `furyhawk/lta_datamall_api`.

The gateway now ships with two explicit upstream profiles:
- `config/gateway.yaml` for a local backend on `http://127.0.0.1:8068`
- `config/gateway.container.yaml` for the compose service `http://lta-datamall-api:8000`

Both profiles are aligned to the companion backend's published route surface:
- public route prefix: `/api/v1`
- backend health endpoints remain available at `/healthz` and `/readyz`

One-command profile selection:
- Local host pairing: `make run-local CONFIG_PROFILE=local`
- Containerized gateway: `make run CONFIG_PROFILE=container`
- Route parity check against the running companion backend OpenAPI: `make check-companion-parity CONFIG_PROFILE=local`

Suggested local pairing workflow:
1. Run `furyhawk/lta_datamall_api` on port `8068`.
2. Start this gateway with `make run-local CONFIG_PROFILE=local`.
3. Use this gateway for edge concerns such as admin config editing, gateway API keys, and response caching while the companion backend owns the LTA DataMall domain logic.

## Integrated Dev Compose Workflow
Use the bundled compose file when you want this repo to start both the gateway and the companion backend together.

1. Create `.env` from `.env.example` and set `DATAMALL_API_KEY`.
2. Start the stack:

```bash
make compose-up
```

3. Open the gateway at `http://127.0.0.1:8000`.

Notes:
- `make compose-up` starts the companion backend first, checks its live `/openapi.json`, then starts the gateway.
- The compose workflow uses Docker Compose because the companion backend is built directly from its Git repository.
- Tail logs with `make compose-logs` and stop the stack with `make compose-down`.

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
    port: 8443
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
- `port` overrides the upstream URL port without changing the host or scheme.

## Administrative Portal and Dashboard
- Admin UI: `GET /admin/portal`
- Admin static assets: `GET /admin/portal/assets/*`
- Admin summary: `GET /admin/dashboard`
- Get config YAML: `GET /admin/config`
- Save config YAML: `PUT /admin/config`
- List API keys: `GET /admin/api-keys`
- Create API key: `POST /admin/api-keys` with body `{"name":"client-name"}`
- Revoke API key: `DELETE /admin/api-keys/{key_id}`
- Cache status: `GET /admin/cache`
- Invalidate cache by route/query fragment: `POST /admin/cache/invalidate`
- Clear all cache entries: `DELETE /admin/cache`

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
- Admin invalidation payload example:
  - `{"path": "/api/v1/bus-arrival", "method": "GET", "query_contains": "BusStopCode=12345"}`

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
make run CONFIG_PROFILE=local
```

Gateway will be available at `http://127.0.0.1:8000`.

Use `CONFIG_PROFILE=container` when the upstream backend is running inside the compose network.

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
make run CONTAINER_ENGINE=docker PORT=8080 ENV_FILE=.env CONFIG_PROFILE=local
```

## GitHub Packages (GHCR)
- Automated image publishing is configured in `.github/workflows/release-image.yml`.
- On push of a release tag (for example `v0.2.1`), CI builds and pushes:
  - `ghcr.io/furyhawk/api_gateway:v0.2.1`
  - `ghcr.io/furyhawk/api_gateway:latest`

Pull example:
```bash
docker pull ghcr.io/furyhawk/api_gateway:v0.2.1
```
