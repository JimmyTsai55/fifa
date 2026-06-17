import time
from collections import deque
import config


def _get(conn, key):
    r = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def _set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES (?,?)",
                 (key, str(value)))
    conn.commit()


def _ensure_day(conn, today: str):
    if _get(conn, "quota_date") != today:
        _set(conn, "quota_date", today)
        _set(conn, "quota_remaining", config.DAILY_QUOTA)


def remaining(conn, today: str) -> int:
    _ensure_day(conn, today)
    return int(_get(conn, "quota_remaining"))


def record_response(conn, today: str, headers: dict):
    _ensure_day(conn, today)
    hdr = headers.get("x-ratelimit-requests-remaining")
    if hdr is not None:
        _set(conn, "quota_remaining", int(hdr))
    else:
        _set(conn, "quota_remaining", max(0, remaining(conn, today) - 1))


class RateLimiter:
    def __init__(self, max_per_min: int = config.PER_MIN, now_fn=time.monotonic):
        self.max = max_per_min
        self.now_fn = now_fn
        self._hits = deque()

    def allow(self, now=None) -> bool:
        now = self.now_fn() if now is None else now
        while self._hits and now - self._hits[0] >= 60:
            self._hits.popleft()
        if len(self._hits) < self.max:
            self._hits.append(now)
            return True
        return False
