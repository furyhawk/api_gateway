from __future__ import annotations

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


def test_load_gateway_config_unknown_upstream(tmp_path) -> None:
    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
upstreams:
  known:
    base_url: https://example.com/
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
routes:
  - path: api/v1/demo
    methods: [GET]
    upstream: demo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="route path must start"):
        load_gateway_config(config_file)
