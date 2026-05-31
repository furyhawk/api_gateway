from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import yaml
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .admin import render_admin_portal, require_admin_access
from .api_keys import ApiKeyStore
from .config import GatewayConfig, RouteConfig, load_gateway_config
from .proxy import proxy_request

DEFAULT_CONFIG_PATH = "config/gateway.yaml"


class ConfigUpdateRequest(BaseModel):
    yaml: str


class ApiKeyCreateRequest(BaseModel):
    name: str


def _resolve_config_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path
    return os.getenv("GATEWAY_CONFIG_PATH", DEFAULT_CONFIG_PATH)


def _make_proxy_handler(route: RouteConfig) -> Callable:
    async def handler(request: Request):
        config = request.app.state.gateway_config
        if config.settings.require_api_key:
            presented = request.headers.get("x-api-key", "")
            if not presented:
                return JSONResponse(status_code=401, content={"error": "missing_api_key"})
            if not request.app.state.api_key_store.verify(presented):
                return JSONResponse(status_code=403, content={"error": "invalid_api_key"})

        return await proxy_request(
            request=request,
            client=request.app.state.http_client,
            config=config,
            route=route,
        )

    return handler


def _register_dynamic_routes(app: FastAPI, config: GatewayConfig) -> None:
    for route in config.routes:
        app.add_api_route(
            path=route.path,
            endpoint=_make_proxy_handler(route),
            methods=route.methods,
            summary=route.summary,
            tags=route.tags,
            operation_id=route.operation_id,
        )


def _register_management_routes(app: FastAPI) -> None:
    @app.get("/healthz", tags=["Health"], summary="Liveness probe")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["Health"], summary="Readiness probe")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/admin/routes", tags=["Admin"], summary="List registered gateway routes")
    async def list_routes(request: Request) -> list[dict[str, object]]:
        cfg: GatewayConfig = request.app.state.gateway_config
        return [
            {
                "path": route.path,
                "methods": route.methods,
                "upstream": route.upstream,
                "upstream_path": route.upstream_path,
                "strip_prefix": route.strip_prefix,
            }
            for route in cfg.routes
        ]

    @app.get(
        "/openapi/external.json",
        tags=["Admin"],
        summary="Serve external upstream OpenAPI spec file",
    )
    async def external_openapi(request: Request):
        cfg: GatewayConfig = request.app.state.gateway_config
        openapi_file = cfg.settings.external_openapi_file
        if not openapi_file:
            return JSONResponse(
                status_code=404,
                content={"error": "external_openapi_not_configured"},
            )

        path = Path(openapi_file)
        if not path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "external_openapi_not_found", "path": openapi_file},
            )

        return JSONResponse(content=json.loads(path.read_text(encoding="utf-8")))

    @app.get("/admin/portal", tags=["Admin"], include_in_schema=False)
    async def admin_portal() -> HTMLResponse:
        return HTMLResponse(render_admin_portal())

    @app.get("/admin/dashboard", tags=["Admin"], summary="Admin dashboard summary")
    async def admin_dashboard(request: Request) -> dict[str, object]:
        require_admin_access(request)
        cfg: GatewayConfig = request.app.state.gateway_config
        return {
            "title": cfg.settings.title,
            "version": cfg.settings.version,
            "require_api_key": cfg.settings.require_api_key,
            "admin_api_key_required": bool(request.app.state.admin_api_key),
            "upstreams": sorted(cfg.upstreams.keys()),
            "routes_count": len(cfg.routes),
            "api_keys_file": str(request.app.state.api_key_store.path),
        }

    @app.get("/admin/config", tags=["Admin"], summary="Get active gateway YAML config")
    async def get_admin_config(request: Request) -> dict[str, str]:
        require_admin_access(request)
        config_path: Path = request.app.state.gateway_config_path
        return {"yaml": config_path.read_text(encoding="utf-8")}

    @app.put("/admin/config", tags=["Admin"], summary="Validate and save gateway YAML config")
    async def update_admin_config(
        request: Request,
        payload: ConfigUpdateRequest = Body(...),
    ) -> dict[str, str]:
        require_admin_access(request)
        config_path: Path = request.app.state.gateway_config_path
        previous_yaml = config_path.read_text(encoding="utf-8")

        try:
            parsed = yaml.safe_load(payload.yaml)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid_yaml: {exc}") from exc

        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="invalid_yaml_root")

        # Validate with existing loader by writing candidate content first.
        config_path.write_text(payload.yaml, encoding="utf-8")
        try:
            reloaded = load_gateway_config(config_path)
        except Exception as exc:
            config_path.write_text(previous_yaml, encoding="utf-8")
            raise HTTPException(status_code=400, detail=f"invalid_config: {exc}") from exc

        request.app.state.gateway_config = reloaded
        request.app.state.api_key_store = ApiKeyStore(Path(reloaded.settings.api_keys_file))
        request.app.state.api_key_store.ensure_exists()
        request.app.state.admin_api_key = os.getenv(reloaded.settings.admin_api_key_env, "")
        return {"status": "saved"}

    @app.get("/admin/api-keys", tags=["Admin"], summary="List API keys metadata")
    async def list_api_keys(request: Request) -> dict[str, object]:
        require_admin_access(request)
        keys = request.app.state.api_key_store.list_keys()
        safe = [{k: v for k, v in item.items() if k != "hash"} for item in keys]
        return {"keys": safe}

    @app.post("/admin/api-keys", tags=["Admin"], summary="Create API key")
    async def create_api_key(
        request: Request,
        payload: ApiKeyCreateRequest = Body(...),
    ) -> dict[str, object]:
        require_admin_access(request)
        api_key, metadata = request.app.state.api_key_store.create_key(name=payload.name)
        return {"api_key": api_key, "metadata": metadata}

    @app.delete("/admin/api-keys/{key_id}", tags=["Admin"], summary="Revoke API key")
    async def revoke_api_key(key_id: str, request: Request) -> dict[str, object]:
        require_admin_access(request)
        revoked = request.app.state.api_key_store.revoke_key(key_id)
        return {"revoked": revoked}


def create_app(config_path: str | None = None) -> FastAPI:
    resolved_path = _resolve_config_path(config_path)
    gateway_config = load_gateway_config(resolved_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.gateway_config = gateway_config
        app.state.gateway_config_path = Path(resolved_path)
        app.state.http_client = httpx.AsyncClient()
        app.state.api_key_store = ApiKeyStore(Path(gateway_config.settings.api_keys_file))
        app.state.api_key_store.ensure_exists()
        app.state.admin_api_key = os.getenv(gateway_config.settings.admin_api_key_env, "")
        try:
            yield
        finally:
            await app.state.http_client.aclose()

    app = FastAPI(
        title=gateway_config.settings.title,
        version=gateway_config.settings.version,
        description=gateway_config.settings.description,
        lifespan=lifespan,
    )

    _register_management_routes(app)
    _register_dynamic_routes(app, gateway_config)
    return app
