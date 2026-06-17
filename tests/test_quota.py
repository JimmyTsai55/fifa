import sqlite3
import pytest
from db import schema, quota


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    schema.init_db(c)
    return c


def test_default_remaining_is_daily_quota(conn):
    assert quota.remaining(conn, "2026-06-17") == 100


def test_record_header_sets_remaining(conn):
    quota.record_response(conn, "2026-06-17",
                          {"x-ratelimit-requests-remaining": "57"})
    assert quota.remaining(conn, "2026-06-17") == 57


def test_new_day_resets(conn):
    quota.record_response(conn, "2026-06-17",
                          {"x-ratelimit-requests-remaining": "3"})
    assert quota.remaining(conn, "2026-06-18") == 100


def test_decrement_when_no_header(conn):
    quota.record_response(conn, "2026-06-17", {})  # 無 header → -1
    assert quota.remaining(conn, "2026-06-17") == 99


def test_rate_limiter_allows_up_to_max(conn):
    rl = quota.RateLimiter(max_per_min=2)
    assert rl.allow(now=0.0) is True
    assert rl.allow(now=1.0) is True
    assert rl.allow(now=2.0) is False         # 第3次在同一分鐘 → 擋
    assert rl.allow(now=61.0) is True         # 60s 後窗口滑出 → 放行
