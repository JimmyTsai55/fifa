import pytest
from services.quota_service import QuotaService, QuotaExhausted


class FakeStore:
    def __init__(self, rem): self._rem = rem; self.recorded = []
    def remaining(self): return self._rem
    def record_response(self, h): self.recorded.append(h)


class FakeRL:
    def __init__(self, ok): self._ok = ok
    def allow(self): return self._ok


def test_preflight_ok_when_quota_and_rate_ok():
    QuotaService(FakeStore(5), rate_limiter=FakeRL(True)).check_preflight()  # 不丟例外


def test_preflight_raises_when_quota_zero():
    with pytest.raises(QuotaExhausted):
        QuotaService(FakeStore(0), rate_limiter=FakeRL(True)).check_preflight()


def test_preflight_raises_when_rate_limited():
    with pytest.raises(QuotaExhausted):
        QuotaService(FakeStore(5), rate_limiter=FakeRL(False)).check_preflight()


def test_record_delegates_to_store():
    s = FakeStore(5)
    QuotaService(s, rate_limiter=FakeRL(True)).record({"h": "1"})
    assert s.recorded == [{"h": "1"}]
