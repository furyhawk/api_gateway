from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from starlette.requests import Request

from gateway_framework.cache import ResponseCache
from gateway_framework.config import GatewayConfig, GatewaySettings, RouteConfig, UpstreamConfig
from gateway_framework.proxy import build_target_path, proxy_request


def _make_request(
    path: str,
    query: str = "",
    headers: list[tuple[str, str]] | None = None,
    *,
    app: object | None = None,
    method: str = "GET",
) -> Request:
    encoded_headers = [
        (key.lower().encode("utf-8"), value.encode("utf-8")) for key, value in (headers or [])
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "query_string": query.encode("utf-8"),
        "headers": encoded_headers,
        "client": ("127.0.0.1", 51234),
        "server": ("gateway.local", 8000),
    }
    if app is not None:
        scope["app"] = app

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_build_target_path_uses_upstream_path_override() -> None:
    route = RouteConfig(path="/api/v1/bus", methods=["GET"], upstream="demo", upstream_path="/v2/bus")
    request = _make_request("/api/v1/bus")

    assert build_target_path(request, route) == "/v2/bus"


def test_build_target_path_applies_strip_prefix() -> None:
    route = RouteConfig(path="/api/v1/bus", methods=["GET"], upstream="demo", strip_prefix="/api")
    request = _make_request("/api/v1/bus")

    assert build_target_path(request, route) == "/v1/bus"


@pytest.mark.anyio
async def test_proxy_request_forwards_to_upstream() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["x_forwarded_proto"] = req.headers.get("x-forwarded-proto")
        seen["x_forwarded_host"] = req.headers.get("x-forwarded-host")
        seen["connection"] = req.headers.get("connection")
        return httpx.Response(
            status_code=200,
            content=b'{"ok":true}',
            headers={"content-type": "application/json", "connection": "close"},
        )

    config = GatewayConfig(
        upstreams={
            "demo": UpstreamConfig(base_url="https://example.com/", port=8443, timeout_seconds=5)
        },
        routes=[],
    )
    route = RouteConfig(path="/api/v1/bus", methods=["GET"], upstream="demo")
    request = _make_request("/api/v1/bus", query="a=1", headers=[("Connection", "keep-alive")])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await proxy_request(request=request, client=client, config=config, route=route)

    assert response.status_code == 200
    assert response.body == b'{"ok":true}'
    assert response.headers.get("connection") is None
    assert seen["url"] == "https://example.com:8443/api/v1/bus?a=1"
    assert seen["x_forwarded_proto"] == "http"
    assert seen["x_forwarded_host"] == "gateway.local"


@pytest.mark.anyio
async def test_proxy_request_cache_hit_skips_second_upstream_call() -> None:
    calls = {"count": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(
            status_code=200,
            content=b'{"cached":true}',
            headers={"content-type": "application/json"},
        )

    config = GatewayConfig(
        settings=GatewaySettings(cache_enabled=True, cache_ttl_seconds=60, cache_max_entries=100),
        upstreams={
            "demo": UpstreamConfig(base_url="https://example.com/", port=8443, timeout_seconds=5)
        },
        routes=[],
    )
    route = RouteConfig(path="/api/v1/bus", methods=["GET"], upstream="demo")
    fake_app = SimpleNamespace(state=SimpleNamespace(response_cache=ResponseCache(ttl_seconds=60, max_entries=10)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await proxy_request(
            request=_make_request("/api/v1/bus", query="a=1", app=fake_app),
            client=client,
            config=config,
            route=route,
        )
        second = await proxy_request(
            request=_make_request("/api/v1/bus", query="a=1", app=fake_app),
            client=client,
            config=config,
            route=route,
        )

    assert first.status_code == 200
    assert first.headers.get("x-gateway-cache") == "MISS"
    assert second.status_code == 200
    assert second.headers.get("x-gateway-cache") == "HIT"
    assert calls["count"] == 1


@pytest.mark.anyio
async def test_proxy_request_returns_502_when_upstream_unreachable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=req)

    config = GatewayConfig(
        upstreams={"demo": UpstreamConfig(base_url="https://example.com/", port=8443)},
        routes=[],
    )
    route = RouteConfig(path="/api/v1/bus", methods=["GET"], upstream="demo")
    request = _make_request("/api/v1/bus")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await proxy_request(request=request, client=client, config=config, route=route)

    assert response.status_code == 502
    assert b"upstream_unreachable" in response.body
