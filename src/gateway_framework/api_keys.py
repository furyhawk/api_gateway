from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class ApiKeyStore:
    path: Path

    def ensure_exists(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"keys": []}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        self.ensure_exists()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("API key store must be a JSON object")
        keys = raw.get("keys")
        if not isinstance(keys, list):
            raise ValueError("API key store must contain a 'keys' array")
        return raw

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_keys(self) -> list[dict[str, Any]]:
        payload = self._load()
        return list(payload["keys"])

    def create_key(self, *, name: str) -> tuple[str, dict[str, Any]]:
        payload = self._load()

        secret = f"ak_{secrets.token_urlsafe(24)}"
        metadata = {
            "id": secrets.token_hex(8),
            "name": name,
            "prefix": secret[:10],
            "hash": _hash_key(secret),
            "created_at": _utc_now_iso(),
            "revoked": False,
        }
        payload["keys"].append(metadata)
        self._save(payload)

        safe_metadata = {k: v for k, v in metadata.items() if k != "hash"}
        return secret, safe_metadata

    def revoke_key(self, key_id: str) -> bool:
        payload = self._load()
        updated = False
        for item in payload["keys"]:
            if item.get("id") == key_id and not item.get("revoked", False):
                item["revoked"] = True
                item["revoked_at"] = _utc_now_iso()
                updated = True
                break
        if updated:
            self._save(payload)
        return updated

    def verify(self, presented_key: str) -> bool:
        if not presented_key:
            return False
        hashed = _hash_key(presented_key)
        payload = self._load()
        for item in payload["keys"]:
            if item.get("revoked", False):
                continue
            if item.get("hash") == hashed:
                return True
        return False
