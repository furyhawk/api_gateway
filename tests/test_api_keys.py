from __future__ import annotations

from gateway_framework.api_keys import ApiKeyStore


def test_api_key_store_create_verify_revoke(tmp_path) -> None:
    store = ApiKeyStore(tmp_path / "api_keys.json")
    store.ensure_exists()

    api_key, meta = store.create_key(name="integration-client")
    assert api_key.startswith("ak_")
    assert meta["name"] == "integration-client"

    assert store.verify(api_key) is True
    assert store.verify("ak_invalid") is False

    revoked = store.revoke_key(meta["id"])
    assert revoked is True
    assert store.verify(api_key) is False
