import pytest
from adapters.apifootball_adapter import ApiFootballAdapter, live_ttl
from services.quota_service import QuotaService, QuotaExhausted


class FakeStore:
    def __init__(self, rem=100): self._rem = rem; self.recorded = []
    def get_or_fetch(self, key, ttl, fetch_fn, now=None): return fetch_fn()
    def peek(self, key): return None
    def remaining(self): return self._rem
    def record_response(self, h): self.recorded.append(h)


class FakeRL:
    def allow(self): return True


def make(rem=100, http_get=None):
    store = FakeStore(rem)
    qs = QuotaService(store, rate_limiter=FakeRL())
    return ApiFootballAdapter(store, qs, http_get=http_get), store


def test_squad_returns_response_and_records_quota():
    def http_get(url, params):
        return 200, {"response": [{"id": 1}], "errors": []}, {"x": "1"}
    af, store = make(http_get=http_get)
    assert af.squad(10) == [{"id": 1}]
    assert store.recorded  # 有記錄額度


def test_request_blocked_when_quota_zero():
    af, _ = make(rem=0, http_get=lambda u, p: (200, {"response": []}, {}))
    with pytest.raises(QuotaExhausted):
        af.squad(10)


def test_raises_on_200_with_errors_body():
    def http_get(url, params):
        return 200, {"errors": {"token": "bad"}}, {}
    af, _ = make(http_get=http_get)
    with pytest.raises(RuntimeError):
        af.squad(10)


def test_squad_rejects_bad_team_id():
    af, _ = make()
    out = af.squad(0)
    assert out and "error" in out[0]


def test_live_ttl_floor():
    assert live_ttl(120, 5) == 60   # max(60, 24) -> 60
    assert live_ttl(600, 0) == 600
