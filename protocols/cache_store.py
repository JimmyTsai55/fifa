from typing import Protocol, Callable


class CacheStoreProtocol(Protocol):
    def get_or_fetch(self, key: str, ttl: int,
                     fetch_fn: Callable[[], dict], now: float | None = None) -> dict: ...
    def peek(self, key: str) -> dict | None: ...
