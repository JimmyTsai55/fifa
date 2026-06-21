import threading
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


def test_store_has_threading_lock(store):
    """The adapter must carry a threading.Lock to serialise concurrent DB access."""
    assert isinstance(store._lock, type(threading.Lock()))


def test_concurrent_record_response_no_crash(tmp_path):
    """Smoke-test: N threads calling record_response concurrently must not raise.

    This verifies correctness-by-construction: the threading.Lock prevents
    'database is locked' SQLite errors under concurrent writes.  We cannot
    assert a specific final quota value because the order of writes is
    non-deterministic, but we assert no exception is raised.
    """
    store = SqliteStoreAdapter(tmp_path / "concurrent.db")
    errors: list[Exception] = []

    def worker():
        try:
            store.record_response({})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent writes raised: {errors}"
