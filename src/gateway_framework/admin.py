from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

ADMIN_STATIC_DIR = Path(__file__).resolve().parent / "static" / "admin"


def require_admin_access(request: Request) -> None:
    expected_key = request.app.state.admin_api_key
    if not expected_key:
        return

    presented = request.headers.get("x-admin-key")
    if presented != expected_key:
        raise HTTPException(status_code=401, detail="invalid_admin_api_key")


def get_admin_assets_dir() -> Path:
    return ADMIN_STATIC_DIR


def render_admin_portal() -> str:
    index_file = ADMIN_STATIC_DIR / "index.html"
    if not index_file.exists():
        return "<html><body><h1>Admin portal assets missing</h1></body></html>"
    return index_file.read_text(encoding="utf-8")
