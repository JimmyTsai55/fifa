import json
import time
import sqlite3


def cache_get(conn: sqlite3.Connection, key: str):
    return conn.execute(
        "SELECT fetched_at, payload_json FROM cache_meta WHERE cache_key=?",
        (key,)).fetchone()


def cache_set(conn: sqlite3.Connection, key: str, payload: dict, now: float):
    conn.execute(
        "INSERT OR REPLACE INTO cache_meta(cache_key, fetched_at, payload_json) "
        "VALUES (?,?,?)",
        (key, now, json.dumps(payload)))
    conn.commit()


def get_or_fetch(conn, key, ttl, fetch_fn, now=None):
    now = time.time() if now is None else now
    row = cache_get(conn, key)
    if row is not None and (now - row["fetched_at"]) < ttl:
        return json.loads(row["payload_json"])
    try:
        data = fetch_fn()
    except Exception:
        if row is not None:
            return json.loads(row["payload_json"])  # stale fallback
        raise
    cache_set(conn, key, data, now)
    return data
