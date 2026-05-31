from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import time


@dataclass
class CachedResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    media_type: str | None
    expires_at: float


class ResponseCache:
    def __init__(self, *, ttl_seconds: float, max_entries: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: OrderedDict[str, CachedResponse] = OrderedDict()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, value in self._entries.items() if value.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

    def get(self, key: str) -> CachedResponse | None:
        self._purge_expired()
        entry = self._entries.get(key)
        if entry is None:
            return None

        self._entries.move_to_end(key)
        return entry

    def set(
        self,
        key: str,
        *,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        media_type: str | None,
    ) -> None:
        if self.ttl_seconds <= 0 or self.max_entries <= 0:
            return

        self._purge_expired()
        if key in self._entries:
            self._entries.pop(key, None)

        while len(self._entries) >= self.max_entries:
            self._entries.popitem(last=False)

        self._entries[key] = CachedResponse(
            status_code=status_code,
            headers=dict(headers),
            body=bytes(body),
            media_type=media_type,
            expires_at=time.monotonic() + self.ttl_seconds,
        )

    def clear(self) -> None:
        self._entries.clear()

    def size(self) -> int:
        self._purge_expired()
        return len(self._entries)

    def invalidate_by_contains(self, contains: list[str]) -> int:
        self._purge_expired()
        if not contains:
            return 0

        invalidated = 0
        for key in list(self._entries.keys()):
            if all(fragment in key for fragment in contains):
                self._entries.pop(key, None)
                invalidated += 1
        return invalidated
