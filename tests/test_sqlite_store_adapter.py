import pytest
from adapters.sqlite_store_adapter import SqliteStoreAdapter


@pytest.fixture
def store(tmp_path):
    return SqliteStoreAdapter(tmp_path / "t.db")


def test_get_or_fetch_caches(store):
    calls = []
    def fetch():
        calls.append(1)
        return {"v": 1}
    assert store.get_or_fetch("k", 999, fetch, now=100.0) == {"v": 1}
    assert store.get_or_fetch("k", 999, fetch, now=100.5) == {"v": 1}
    assert len(calls) == 1  # 第二次命中快取


def test_peek_returns_none_when_absent(store):
    assert store.peek("missing") is None


def test_record_response_decrements_when_no_header(store):
    start = store.remaining()
    store.record_response({})
    assert store.remaining() == start - 1


def test_record_response_uses_header(store):
    store.record_response({"x-ratelimit-requests-remaining": "42"})
    assert store.remaining() == 42
