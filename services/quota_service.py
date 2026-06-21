import config
from db.quota import RateLimiter
from protocols.quota_store import QuotaStoreProtocol


class QuotaExhausted(Exception):
    pass


class QuotaService:
    def __init__(self, store: QuotaStoreProtocol,
                 per_min: int = config.PER_MIN, rate_limiter=None):
        self._store = store
        self._rl = rate_limiter or RateLimiter(per_min)

    def check_preflight(self) -> None:
        if self._store.remaining() <= 0:
            raise QuotaExhausted("daily-quota")
        if not self._rl.allow():
            raise QuotaExhausted("rate-limit/min")

    def record(self, headers: dict) -> None:
        self._store.record_response(headers)

    def remaining(self) -> int:
        return self._store.remaining()
