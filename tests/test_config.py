from __future__ import annotations

from pathlib import Path

import pytest

from gateway_framework.config import load_gateway_config


def test_load_gateway_config_success(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
settings:
  title: Test Gateway
upstreams:
  demo:
    base_url: https://example.com/
    port: 8443
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    config = load_gateway_config(config_file)

    assert config.settings.title == "Test Gateway"
    assert "demo" in config.upstreams
    assert config.routes[0].path == "/api/v1/demo"
    assert config.upstreams["demo"].port == 8443
    assert config.settings.gateway_port == 8000


def test_load_gateway_config_unknown_upstream(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  known:
    base_url: https://example.com/
    port: 8443
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: unknown
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown upstreams"):
        load_gateway_config(config_file)


def test_load_gateway_config_invalid_route_path(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  demo:
    base_url: https://example.com/
    port: 8443
routes:
  - path: api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="route path must start"):
        load_gateway_config(config_file)


def test_load_gateway_config_expands_env_with_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GATEWAY_UPSTREAM_HOST", raising=False)
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  demo:
    base_url: http://${GATEWAY_UPSTREAM_HOST:-host.docker.internal}/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    config = load_gateway_config(config_file)

    assert str(config.upstreams["demo"].base_url) == "http://host.docker.internal/"


def test_load_gateway_config_expands_env_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_UPSTREAM_HOST", "host.containers.internal")
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  demo:
    base_url: http://${GATEWAY_UPSTREAM_HOST:-host.docker.internal}/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    config = load_gateway_config(config_file)

    assert str(config.upstreams["demo"].base_url) == "http://host.containers.internal/"


def test_load_gateway_config_missing_required_env_var_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GATEWAY_UPSTREAM_HOST", raising=False)
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  demo:
    base_url: http://${GATEWAY_UPSTREAM_HOST}/
routes:
  - path: /api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing required environment variable"):
        load_gateway_config(config_file)


def test_sample_gateway_config_matches_companion_backend_route_set() -> None:
  config = load_gateway_config(Path("config/gateway.yaml"))

  assert {route.path for route in config.routes} == {
    "/api/v1/bus-arrival",
    "/api/v1/bus-services",
    "/api/v1/bus-routes",
    "/api/v1/bus-stops",
    "/api/v1/passenger-volume/bus",
    "/api/v1/passenger-volume/od-bus",
    "/api/v1/planned-bus-routes",
  }


def test_container_gateway_config_matches_local_route_set() -> None:
  local_config = load_gateway_config(Path("config/gateway.yaml"))
  container_config = load_gateway_config(Path("config/gateway.container.yaml"))

  assert {route.path for route in local_config.routes} == {
    route.path for route in container_config.routes
  }
  assert local_config.settings.gateway_port == container_config.settings.gateway_port
  assert container_config.upstreams["lta_datamall"].port is not None
