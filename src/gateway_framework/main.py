from __future__ import annotations

import os

import uvicorn

from .app import create_app
from .config import load_gateway_config

app = create_app()


def _resolve_runtime_port() -> int:
	override = os.getenv("GATEWAY_PORT") or os.getenv("PORT")
	if override:
		try:
			port = int(override)
		except ValueError as exc:
			raise ValueError("GATEWAY_PORT must be an integer") from exc
		if not 1 <= port <= 65535:
			raise ValueError("GATEWAY_PORT must be between 1 and 65535")
		return port

	config_path = os.getenv("GATEWAY_CONFIG_PATH", "config/gateway.yaml")
	return load_gateway_config(config_path).settings.gateway_port


def run() -> None:
	host = os.getenv("GATEWAY_HOST", "0.0.0.0")
	port = _resolve_runtime_port()
	uvicorn.run("gateway_framework.main:app", host=host, port=port)


if __name__ == "__main__":
	run()
