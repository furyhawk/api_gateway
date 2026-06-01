from __future__ import annotations

from gateway_framework.main import _resolve_runtime_port


def test_resolve_runtime_port_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_PORT", "18080")

    assert _resolve_runtime_port() == 18080


def test_resolve_runtime_port_from_config_when_env_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GATEWAY_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    config_file = tmp_path / "gateway.yaml"
    config_file.write_text(
        """
settings:
  gateway_port: 19090
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
    monkeypatch.setenv("GATEWAY_CONFIG_PATH", str(config_file))

    assert _resolve_runtime_port() == 19090
