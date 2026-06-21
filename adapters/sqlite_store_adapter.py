import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from db import cache, quota
from db.schema import init_db


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class SqliteStoreAdapter:
    """實作 CacheStoreProtocol + QuotaStoreProtocol，包現有 db/ 低層 helper。"""

    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        init_db(self._conn)

    # --- CacheStoreProtocol ---
    def get_or_fetch(self, key, ttl, fetch_fn, now=None):
        return cache.get_or_fetch(self._conn, key, ttl, fetch_fn, now)

    def peek(self, key):
        return cache.cache_get(self._conn, key)

    # --- QuotaStoreProtocol ---
    def remaining(self):
        return quota.remaining(self._conn, _today())

    def record_response(self, headers):
        quota.record_response(self._conn, _today(), headers)
