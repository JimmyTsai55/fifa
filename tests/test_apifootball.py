import sqlite3
import pytest
from db import schema
import tools.apifootball as af


@pytest.fixture
def conn(tmp_path, monkeypatch):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    schema.init_db(c)
    return c


def test_request_returns_response_and_records_quota(conn, monkeypatch):
    def fake_get(url, params):
        return 200, {"response": [{"id": 1}]}, {"x-ratelimit-requests-remaining": "42"}
    monkeypatch.setattr(af, "_http_get", fake_get)
    from db import quota
    out = af._request(conn, "2026-06-17", "/teams", {"league": 1})
    assert out == [{"id": 1}]
    assert quota.remaining(conn, "2026-06-17") == 42


def test_request_blocked_when_quota_zero(conn, monkeypatch):
    from db import quota
    quota.record_response(conn, "2026-06-17", {"x-ratelimit-requests-remaining": "0"})
    monkeypatch.setattr(af, "_http_get",
                        lambda u, p: (_ for _ in ()).throw(AssertionError("no call")))
    with pytest.raises(af.QuotaExhausted):
        af._request(conn, "2026-06-17", "/teams", {"league": 1})


def test_request_raises_on_200_with_errors_body(conn, monkeypatch):
    # API-Football 認證錯誤 → HTTP 200 + 非空 errors，必須擋下不快取
    def fake_get(url, params):
        return 200, {"errors": {"token": "invalid key"}, "response": []}, \
               {"x-ratelimit-requests-remaining": "41"}
    monkeypatch.setattr(af, "_http_get", fake_get)
    with pytest.raises(RuntimeError, match="errors"):
        af._request(conn, "2026-06-17", "/teams", {"league": 1})


def test_request_ok_when_errors_empty_list(conn, monkeypatch):
    # 成功時 errors 為空 list，不應誤判
    def fake_get(url, params):
        return 200, {"errors": [], "response": [{"id": 1}]}, {}
    monkeypatch.setattr(af, "_http_get", fake_get)
    assert af._request(conn, "2026-06-17", "/teams", {"league": 1}) == [{"id": 1}]


def test_live_ttl_divides_remaining_window(conn):
    # 還剩 7200s 到午夜、保留 80 配額 → 90s
    ttl = af.live_ttl(seconds_to_reset=7200, reserved_quota=80)
    assert 89 <= ttl <= 91


def test_live_ttl_floor(conn):
    # 配額 0 不可除 → 回安全大值
    assert af.live_ttl(seconds_to_reset=3600, reserved_quota=0) >= 600
