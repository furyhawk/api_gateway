from __future__ import annotations

import json

from gateway_framework.companion import compare_gateway_to_openapi, load_openapi_document
from gateway_framework.config import load_gateway_config


def test_compare_gateway_to_openapi_detects_matching_route_set() -> None:
    config = load_gateway_config("config/gateway.yaml")
    document = {
        "openapi": "3.0.3",
        "paths": {
            "/api/v1/bus-arrival": {},
            "/api/v1/bus-services": {},
            "/api/v1/bus-routes": {},
            "/api/v1/bus-stops": {},
            "/api/v1/passenger-volume/bus": {},
            "/api/v1/passenger-volume/od-bus": {},
            "/api/v1/planned-bus-routes": {},
            "/healthz": {},
        },
    }

    report = compare_gateway_to_openapi(config, document)

    assert report.is_aligned is True
    assert report.missing_in_gateway == ()
    assert report.extra_in_gateway == ()


def test_compare_gateway_to_openapi_detects_missing_route() -> None:
    config = load_gateway_config("config/gateway.yaml")
    document = {
        "openapi": "3.0.3",
        "paths": {
            "/api/v1/bus-arrival": {},
        },
    }

    report = compare_gateway_to_openapi(config, document)

    assert report.is_aligned is False
    assert report.missing_in_gateway == ()
    assert "/api/v1/bus-services" in report.extra_in_gateway


def test_load_openapi_document_reads_local_file(tmp_path) -> None:
    openapi_file = tmp_path / "companion-openapi.json"
    openapi_file.write_text(json.dumps({"openapi": "3.0.3", "paths": {"/api/v1/bus-arrival": {}}}), encoding="utf-8")

    loaded = load_openapi_document(str(openapi_file))

    assert loaded["paths"]["/api/v1/bus-arrival"] == {}
