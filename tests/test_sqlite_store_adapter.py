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


def test_store_has_threading_rlock(store):
    """The adapter must carry a threading.RLock (reentrant) to serialise concurrent
    DB access without deadlocking when fetch_fn calls back into remaining() /
    record_response() on the same thread."""
    assert isinstance(store._lock, type(threading.RLock()))


def test_concurrent_record_response_no_crash(tmp_path):
    """Smoke-test: N threads calling record_response concurrently must not raise.

    This verifies correctness-by-construction: the threading.RLock prevents
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


def test_get_or_fetch_reentrant_fetch_fn(tmp_path):
    """Regression test: fetch_fn that calls back into remaining() and
    record_response() on the SAME thread must not deadlock.

    With a plain threading.Lock this test hangs forever (>5 s timeout →
    assert fails).  With RLock the re-entrant acquisitions succeed and the
    test completes well within the timeout.

    Design: run store.get_or_fetch() in a worker thread and join with a
    5-second timeout.  If the thread is still alive after the timeout, the
    lock is non-reentrant and a deadlock occurred.
    """
    store = SqliteStoreAdapter(tmp_path / "reentrant.db")
    result: list = []
    errors: list[Exception] = []

    def fetch_fn():
        # Simulate ApiFootballAdapter._request calling back into the store
        # while get_or_fetch already holds the lock.
        _ = store.remaining()           # re-entrant acquire #1
        store.record_response({})       # re-entrant acquire #2
        return {"data": "fetched"}

    def worker():
        try:
            value = store.get_or_fetch("reentrant-key", 999, fetch_fn, now=1.0)
            result.append(value)
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=5)

    assert not t.is_alive(), (
        "Deadlock detected: get_or_fetch did not complete within 5 s. "
        "The lock is likely non-reentrant — change threading.Lock to threading.RLock."
    )
    assert errors == [], f"fetch_fn callback raised: {errors}"
    assert result == [{"data": "fetched"}], f"Unexpected result: {result}"
    # Confirm the value is now cached (fetch_fn should NOT be called again)
    second = store.get_or_fetch("reentrant-key", 999, lambda: (_ for _ in ()).throw(AssertionError("cache miss")), now=2.0)
    assert second == {"data": "fetched"}
