from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import GatewayConfig, RouteConfig, load_gateway_config
from .proxy import proxy_request

DEFAULT_CONFIG_PATH = "config/gateway.yaml"


def _resolve_config_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path
    return os.getenv("GATEWAY_CONFIG_PATH", DEFAULT_CONFIG_PATH)


def _make_proxy_handler(route: RouteConfig) -> Callable:
    async def handler(request: Request):
        return await proxy_request(
            request=request,
            client=request.app.state.http_client,
            config=request.app.state.gateway_config,
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


def create_app(config_path: str | None = None) -> FastAPI:
    resolved_path = _resolve_config_path(config_path)
    gateway_config = load_gateway_config(resolved_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.gateway_config = gateway_config
        app.state.http_client = httpx.AsyncClient()
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
