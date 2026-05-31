from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from gateway_framework.api_keys import ApiKeyStore
from gateway_framework.app import create_app
from gateway_framework.cache import ResponseCache
from gateway_framework.config import load_gateway_config


def _prepare_state(app, config_file: Path) -> None:
  def failing_upstream(req: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("upstream unavailable", request=req)

  app.state.gateway_config = load_gateway_config(config_file)
  app.state.gateway_config_path = Path(config_file)
  app.state.admin_api_key = ""
  app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(failing_upstream))
  app.state.response_cache = ResponseCache(ttl_seconds=60, max_entries=100)
  store = ApiKeyStore(Path(config_file.parent / "api_keys.json"))
  store.ensure_exists()
  app.state.api_key_store = store


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
    _prepare_state(app, config_file)
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
    _prepare_state(app, config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi/external.json")

    assert response.status_code == 404
    assert response.json()["error"] == "external_openapi_not_configured"


@pytest.mark.anyio
async def test_admin_portal_and_assets_are_served(tmp_path) -> None:
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
    _prepare_state(app, config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        portal = await client.get("/admin/portal")
        css = await client.get("/admin/portal/assets/styles.css")
        js = await client.get("/admin/portal/assets/app.js")

    assert portal.status_code == 200
    assert "Gateway Portal" in portal.text
    assert css.status_code == 200
    assert "metrics-grid" in css.text
    assert js.status_code == 200
    assert "bootstrap" in js.text


@pytest.mark.anyio
async def test_admin_api_key_lifecycle(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
settings:
  api_keys_file: PLACEHOLDER
upstreams:
  demo:
    base_url: https://example.com/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip().replace("PLACEHOLDER", str(tmp_path / "api_keys.json")),
        encoding="utf-8",
    )

    app = create_app(str(config_file))
    _prepare_state(app, config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/admin/api-keys", json={"name": "portal-user"})
        assert created.status_code == 200
        payload = created.json()
        assert payload["api_key"].startswith("ak_")

        listed = await client.get("/admin/api-keys")
        assert listed.status_code == 200
        assert len(listed.json()["keys"]) == 1
        key_id = listed.json()["keys"][0]["id"]

        revoked = await client.delete(f"/admin/api-keys/{key_id}")
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] is True


@pytest.mark.anyio
async def test_proxy_route_requires_api_key_when_enabled(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    api_keys_file = tmp_path / "api_keys.json"
    config_file.write_text(
        f"""
settings:
  require_api_key: true
  api_keys_file: {api_keys_file}
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
    _prepare_state(app, config_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing = await client.get("/api/v1/demo")
        assert missing.status_code == 401
        assert missing.json()["error"] == "missing_api_key"

        created = await client.post("/admin/api-keys", json={"name": "client"})
        api_key = created.json()["api_key"]

        invalid = await client.get("/api/v1/demo", headers={"x-api-key": "ak_bad"})
        assert invalid.status_code == 403
        assert invalid.json()["error"] == "invalid_api_key"

        valid = await client.get("/api/v1/demo", headers={"x-api-key": api_key})
        assert valid.status_code == 502


@pytest.mark.anyio
async def test_admin_cache_controls(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
settings:
  cache_enabled: true
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
    _prepare_state(app, config_file)
    app.state.response_cache.set(
        "GET|https://example.com/api/v1/demo|a=1||",
        status_code=200,
        headers={"content-type": "application/json"},
        body=b"{}",
        media_type="application/json",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        status_before = await client.get("/admin/cache")
        assert status_before.status_code == 200
        assert status_before.json()["entries"] == 1

        invalidated = await client.post(
            "/admin/cache/invalidate",
            json={"path": "/api/v1/demo", "method": "GET"},
        )
        assert invalidated.status_code == 200
        assert invalidated.json()["invalidated_entries"] == 1

        app.state.response_cache.set(
            "GET|https://example.com/api/v1/demo|a=2||",
            status_code=200,
            headers={"content-type": "application/json"},
            body=b"{}",
            media_type="application/json",
        )

        cleared = await client.delete("/admin/cache")
        assert cleared.status_code == 200
        assert cleared.json()["cleared_entries"] == 1

        status_after = await client.get("/admin/cache")
        assert status_after.status_code == 200
        assert status_after.json()["entries"] == 0
