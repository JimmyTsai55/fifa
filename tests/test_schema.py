import sqlite3
from db import schema


def test_init_creates_tables(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    schema.init_db(conn)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"cache_meta", "kv"} <= names


def test_wal_enabled(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    schema.init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
