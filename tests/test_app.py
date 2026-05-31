from __future__ import annotations

import json

import httpx
import pytest

from gateway_framework.app import create_app
from gateway_framework.config import load_gateway_config


@pytest.mark.anyio
async def test_management_endpoints_and_external_openapi(tmp_path) -> None:
    external_openapi = tmp_path / "external-openapi.json"
    external_openapi.write_text(
        json.dumps({"openapi": "3.1.0", "info": {"title": "Upstream", "version": "1.0.0"}}),
        encoding="utf-8",
    )

    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        f"""
settings:
  title: Test Gateway
  version: 9.9.9
  description: test gateway
  external_openapi_file: {external_openapi}
upstreams:
  demo:
    base_url: https://example.com/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
    upstream_path: /api/v1/demo
""".strip(),
        encoding="utf-8",
    )

    app = create_app(str(config_file))
    app.state.gateway_config = load_gateway_config(config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = await client.get("/healthz")
        ready = await client.get("/readyz")
        routes = await client.get("/admin/routes")
        external = await client.get("/openapi/external.json")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert routes.status_code == 200
    assert routes.json()[0]["path"] == "/api/v1/demo"
    assert external.status_code == 200
    assert external.json()["info"]["title"] == "Upstream"


@pytest.mark.anyio
async def test_external_openapi_not_configured(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  demo:
    base_url: https://example.com/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    app = create_app(str(config_file))
    app.state.gateway_config = load_gateway_config(config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi/external.json")

    assert response.status_code == 404
    assert response.json()["error"] == "external_openapi_not_configured"
