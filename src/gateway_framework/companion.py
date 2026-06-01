from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from .config import GatewayConfig, load_gateway_config

DEFAULT_COMPANION_OPENAPI = "http://127.0.0.1:8068/openapi.json"
DEFAULT_PATH_PREFIX = "/api/v1"


@dataclass(frozen=True)
class RouteParityReport:
    missing_in_gateway: tuple[str, ...]
    extra_in_gateway: tuple[str, ...]

    @property
    def is_aligned(self) -> bool:
        return not self.missing_in_gateway and not self.extra_in_gateway


def gateway_route_paths(config: GatewayConfig, prefix: str = DEFAULT_PATH_PREFIX) -> set[str]:
    return {route.path for route in config.routes if route.path.startswith(prefix)}


def openapi_route_paths(document: dict[str, object], prefix: str = DEFAULT_PATH_PREFIX) -> set[str]:
    raw_paths = document.get("paths")
    if not isinstance(raw_paths, dict):
        raise ValueError("OpenAPI document must contain an object-valued 'paths' field")

    return {
        path
        for path in raw_paths
        if isinstance(path, str) and path.startswith(prefix)
    }


def compare_route_sets(gateway_paths: set[str], openapi_paths: set[str]) -> RouteParityReport:
    return RouteParityReport(
        missing_in_gateway=tuple(sorted(openapi_paths - gateway_paths)),
        extra_in_gateway=tuple(sorted(gateway_paths - openapi_paths)),
    )


def compare_gateway_to_openapi(
    config: GatewayConfig,
    document: dict[str, object],
    prefix: str = DEFAULT_PATH_PREFIX,
) -> RouteParityReport:
    return compare_route_sets(
        gateway_route_paths(config, prefix=prefix),
        openapi_route_paths(document, prefix=prefix),
    )


def load_openapi_document(source: str, *, timeout_seconds: float = 15.0) -> dict[str, object]:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        response = httpx.get(source, timeout=timeout_seconds)
        response.raise_for_status()
        payload = yaml.safe_load(response.text)
    else:
        payload = yaml.safe_load(Path(source).read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must deserialize to an object")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a gateway config profile against the companion backend OpenAPI document.",
    )
    parser.add_argument(
        "--config",
        default="config/gateway.yaml",
        help="Path to the gateway YAML config to validate.",
    )
    parser.add_argument(
        "--openapi",
        default=DEFAULT_COMPANION_OPENAPI,
        help="Path or URL to the companion OpenAPI document.",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PATH_PREFIX,
        help="Only compare paths under this prefix.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = load_gateway_config(args.config)
    document = load_openapi_document(args.openapi)
    report = compare_gateway_to_openapi(config, document, prefix=args.prefix)

    if report.is_aligned:
        print(
            f"Gateway config '{args.config}' matches companion OpenAPI '{args.openapi}' for prefix '{args.prefix}'."
        )
        return 0

    if report.missing_in_gateway:
        print("Missing gateway routes:")
        for path in report.missing_in_gateway:
            print(path)

    if report.extra_in_gateway:
        print("Extra gateway routes:")
        for path in report.extra_in_gateway:
            print(path)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
