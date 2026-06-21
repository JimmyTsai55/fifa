import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from db import cache, quota
from db.schema import init_db


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class SqliteStoreAdapter:
    """實作 CacheStoreProtocol + QuotaStoreProtocol，包現有 db/ 低層 helper。

    A single sqlite3 connection is shared across threadpool workers
    (QAService offloads to threads; Cloud Run --concurrency 50), so all
    DB access is serialised with a threading.Lock to prevent "database is
    locked" errors and quota-counter corruption under concurrent writes.
    """

    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        init_db(self._conn)

    # --- CacheStoreProtocol ---
    def get_or_fetch(self, key, ttl, fetch_fn, now=None):
        with self._lock:
            return cache.get_or_fetch(self._conn, key, ttl, fetch_fn, now)

    def peek(self, key):
        with self._lock:
            return cache.cache_get(self._conn, key)

    # --- QuotaStoreProtocol ---
    def remaining(self):
        with self._lock:
            return quota.remaining(self._conn, _today())

    def record_response(self, headers):
        with self._lock:
            quota.record_response(self._conn, _today(), headers)
