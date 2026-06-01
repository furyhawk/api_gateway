from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, field_validator


class GatewaySettings(BaseModel):
    title: str = "OpenAPI API Gateway"
    version: str = "0.1.0"
    description: str = "Configurable API gateway"
    gateway_port: int = Field(default=8000, ge=1, le=65535)
    external_openapi_file: str | None = None
    cache_enabled: bool = False
    cache_ttl_seconds: float = Field(default=30.0, ge=1.0, le=3600.0)
    cache_max_entries: int = Field(default=500, ge=1, le=10000)
    require_api_key: bool = False
    api_keys_file: str = "config/api_keys.json"
    admin_api_key_env: str = "ADMIN_API_KEY"


class UpstreamConfig(BaseModel):
    base_url: AnyHttpUrl
    port: int | None = Field(default=None, ge=1, le=65535)
    timeout_seconds: float = Field(default=15.0, ge=0.1, le=120.0)

    def resolved_base_url(self) -> str:
        url = urlsplit(str(self.base_url))
        if self.port is None:
            return str(self.base_url)

        host = url.hostname or ""
        if url.username:
            auth = url.username
            if url.password:
                auth = f"{auth}:{url.password}"
            host = f"{auth}@{host}"
        netloc = f"{host}:{self.port}"
        return urlunsplit((url.scheme, netloc, url.path, url.query, url.fragment))


class RouteConfig(BaseModel):
    path: str
    methods: list[Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]]
    upstream: str
    upstream_path: str | None = None
    strip_prefix: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=lambda: ["Gateway"])
    operation_id: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            msg = "route path must start with '/'"
            raise ValueError(msg)
        return value

    @field_validator("upstream_path")
    @classmethod
    def validate_upstream_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("/"):
            msg = "upstream_path must start with '/'"
            raise ValueError(msg)
        return value

    @field_validator("strip_prefix")
    @classmethod
    def validate_strip_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("/"):
            msg = "strip_prefix must start with '/'"
            raise ValueError(msg)
        return value.rstrip("/")


class GatewayConfig(BaseModel):
    settings: GatewaySettings = Field(default_factory=GatewaySettings)
    upstreams: dict[str, UpstreamConfig]
    routes: list[RouteConfig]


_ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_env_placeholders(value: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        if var_name in os.environ:
            return os.environ[var_name]
        if default_value is not None:
            return default_value
        raise ValueError(f"Missing required environment variable: {var_name}")

    return _ENV_PLACEHOLDER_PATTERN.sub(replacer, value)


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_env_placeholders(value)
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    return value


def load_gateway_config(config_path: str | Path) -> GatewayConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Gateway config was not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Gateway config must be a YAML object")

    raw = _resolve_env_placeholders(raw)

    try:
        config = GatewayConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid gateway config: {exc}") from exc

    unknown_upstreams = {route.upstream for route in config.routes} - set(config.upstreams)
    if unknown_upstreams:
        names = ", ".join(sorted(unknown_upstreams))
        raise ValueError(f"Routes reference unknown upstreams: {names}")

    return config
