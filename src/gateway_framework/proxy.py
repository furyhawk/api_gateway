from __future__ import annotations

from urllib.parse import urljoin

import httpx
from fastapi import Request
from starlette.responses import Response

from .config import GatewayConfig, RouteConfig

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}


def _cache_key(request: Request, target_url: str) -> str:
    params = "&".join(f"{k}={v}" for k, v in request.query_params.multi_items())
    vary_accept = request.headers.get("accept", "")
    vary_auth = request.headers.get("authorization", "")
    return f"{request.method}|{target_url}|{params}|{vary_accept}|{vary_auth}"


def _get_cache_from_request(request: Request):
    app = request.scope.get("app")
    if app is None:
        return None
    state = getattr(app, "state", None)
    if state is None:
        return None
    return getattr(state, "response_cache", None)


def build_target_path(request: Request, route: RouteConfig) -> str:
    incoming_path = request.url.path

    if route.upstream_path:
        return route.upstream_path

    if route.strip_prefix and incoming_path.startswith(route.strip_prefix):
        stripped = incoming_path[len(route.strip_prefix) :]
        return stripped if stripped.startswith("/") else f"/{stripped}"

    return incoming_path


def _forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS:
            continue
        headers[key] = value

    headers["x-forwarded-proto"] = request.url.scheme
    headers["x-forwarded-host"] = request.url.hostname or ""
    headers["x-forwarded-for"] = request.client.host if request.client else ""
    return headers


def _response_headers(upstream: httpx.Response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in upstream.headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        headers[key] = value
    return headers


async def proxy_request(
    *,
    request: Request,
    client: httpx.AsyncClient,
    config: GatewayConfig,
    route: RouteConfig,
) -> Response:
    upstream = config.upstreams[route.upstream]
    target_path = build_target_path(request, route)
    target_url = urljoin(str(upstream.base_url), target_path.lstrip("/"))

    cache = None
    cache_key = ""
    cache_enabled = (
        config.settings.cache_enabled and request.method in {"GET", "HEAD"}
    )
    if cache_enabled:
        cache = _get_cache_from_request(request)
        if cache is not None:
            cache_key = _cache_key(request, target_url)
            cached = cache.get(cache_key)
            if cached is not None:
                headers = dict(cached.headers)
                headers["x-gateway-cache"] = "HIT"
                return Response(
                    content=cached.body,
                    status_code=cached.status_code,
                    headers=headers,
                    media_type=cached.media_type,
                )

    try:
        upstream_response = await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            content=await request.body(),
            headers=_forward_headers(request),
            timeout=upstream.timeout_seconds,
        )
    except httpx.RequestError as exc:
        return Response(
            content=(
                '{"error":"upstream_unreachable","detail":"'
                + str(exc)
                + '"}'
            ).encode("utf-8"),
            status_code=502,
            media_type="application/json",
        )

    headers = _response_headers(upstream_response)
    if cache_enabled:
        headers["x-gateway-cache"] = "MISS"

    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=headers,
        media_type=upstream_response.headers.get("content-type"),
    )

    if cache_enabled and cache is not None and 200 <= upstream_response.status_code < 300:
        cache.set(
            cache_key,
            status_code=upstream_response.status_code,
            headers=_response_headers(upstream_response),
            body=upstream_response.content,
            media_type=upstream_response.headers.get("content-type"),
        )

    return response
