import sqlite3
import pytest
from db import schema, cache


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    schema.init_db(c)
    return c


def test_fetch_when_missing(conn):
    calls = []

    def fetch():
        calls.append(1)
        return {"v": 1}
    out = cache.get_or_fetch(conn, "k", ttl=100, fetch_fn=fetch, now=0)
    assert out == {"v": 1} and len(calls) == 1


def test_hit_within_ttl_skips_fetch(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)

    def boom():
        raise AssertionError("should not fetch")
    out = cache.get_or_fetch(conn, "k", 100, boom, now=50)
    assert out == {"v": 1}


def test_refetch_after_ttl(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)
    out = cache.get_or_fetch(conn, "k", 100, lambda: {"v": 2}, now=200)
    assert out == {"v": 2}


def test_stale_fallback_on_fetch_error(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)

    def boom():
        raise RuntimeError("api down")
    out = cache.get_or_fetch(conn, "k", 100, boom, now=999)
    assert out == {"v": 1}  # 過期但抓取失敗 → 回舊資料


def test_raises_when_no_cache_and_fetch_fails(conn):
    def boom():
        raise RuntimeError("api down")
    with pytest.raises(RuntimeError):
        cache.get_or_fetch(conn, "k", 100, boom, now=0)
