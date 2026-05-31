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

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_response_headers(upstream_response),
        media_type=upstream_response.headers.get("content-type"),
    )
