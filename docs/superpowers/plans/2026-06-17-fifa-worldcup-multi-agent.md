# FIFA 2026 世界盃 Multi-Agent 系統 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 OpenAI Agents SDK 打造可查詢 2026 世界盃陣容/賽程/球星/看點的 multi-agent 系統（Triage + 4 專責 agent handoff），資料來自 API-Football（含 TTL 快取與配額管理）+ Tavily 新聞搜尋 + 建置期 Wikipedia 球星建檔。

**Architecture:** 由下而上分層：`db`（SQLite 快取/配額）→ `tools`（API-Football / Tavily / 實體解析，皆為 `@function_tool`）→ `agents`（4 專責 + Triage handoff）→ `main`。所有 API 呼叫經快取層，免費額度（100/天、10/分）由配額模組與自適應 live TTL 守住。

**Tech Stack:** Python 3.11+、`openai-agents`、`openai`、`httpx`、`sqlite3`、`python-dotenv`、`pytest`。

對應設計文件：`docs/superpowers/specs/2026-06-17-fifa-worldcup-multi-agent-design.md`

---

## 檔案結構

| 檔案 | 職責 |
|------|------|
| `config.py` | 常數：LEAGUE_ID/SEASON/TTL/網域/額度/路徑 + 讀 env |
| `db/schema.py` | 建表 + WAL + 連線單例 |
| `db/cache.py` | `get_or_fetch` / `cache_get` / `cache_set`（含 stale fallback） |
| `db/quota.py` | 每日配額（讀 ratelimit header）+ 每分鐘 RateLimiter |
| `tools/apifootball.py` | API-Football 請求 + 快取 + 6 個 `@function_tool` |
| `tools/web.py` | Tavily `web_search`（include_domains） |
| `tools/resolve.py` | `resolve_entity`（中文名→id） |
| `tools/stars.py` | 載入 `data/star_players.json` 的 `get_star_profile` |
| `wc_agents/prompts.py` | 5 份 XML 結構 system prompt 常數 |
| `wc_agents/specialists.py` | Squad / Fixture / Star / Insight 四個 Agent |
| `wc_agents/triage.py` | Triage Agent（handoffs） |
| `init_db.py` | 一次性初始化（節流 + 續跑） |
| `build_stars.md` | 給 Claude Code agent 的球星建檔指示（產出 json） |
| `main.py` | 進入點 |
| `tests/...` | 對應單元測試 |

> 與 spec 的小調整：prompt 改放單一模組 `wc_agents/prompts.py`（XML 字串常數），非 `agents/prompts/` 目錄，減少載入樣板。
> **重要命名**：本地 agent 套件命名為 `wc_agents/`（**不可叫 `agents/`**），否則會遮蔽 OpenAI Agents SDK 的 `agents` 套件。SDK 匯入（`from agents import Agent/Runner/function_tool`）一律保持 `agents`；本地匯入用 `wc_agents`。

---

## Phase 0：專案設定

### Task 0: 初始化專案骨架

**Files:**
- Create: `.gitignore`, `requirements.txt`, `.env.example`, `config.py`, `tests/test_config.py`

- [ ] **Step 1: 初始化 git 與虛擬環境**

```bash
cd /Users/Jimmy_1/fifa
git init
python3 -m venv .venv
source .venv/bin/activate
```

- [ ] **Step 2: 寫 `requirements.txt`**

```
openai-agents
openai
httpx
python-dotenv
pytest
```

- [ ] **Step 3: 安裝**

Run: `pip install -r requirements.txt`
Expected: 安裝成功，無錯誤。

- [ ] **Step 4: 寫 `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
data/cache.db
.pytest_cache/
```

- [ ] **Step 5: 寫 `.env.example`**

```
OPENAI_API_KEY=sk-...
APIFOOTBALL_KEY=...
TAVILY_KEY=tvly-...
```

- [ ] **Step 6: 寫失敗測試 `tests/test_config.py`**

```python
import config

def test_core_constants():
    assert config.LEAGUE_ID == 1
    assert config.SEASON == 2026
    assert config.DAILY_QUOTA == 100
    assert config.PER_MIN == 10

def test_ttl_table_has_expected_keys():
    for k in ["teams", "squad", "fixtures", "standings", "injuries"]:
        assert k in config.TTL and config.TTL[k] > 0

def test_news_domains_english_only():
    assert "bbc.com/sport" in config.NEWS_DOMAINS
    assert len(config.NEWS_DOMAINS) >= 4
```

- [ ] **Step 7: 跑測試確認失敗**

Run: `pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: config` 或屬性缺失）。

- [ ] **Step 8: 寫 `config.py`**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LEAGUE_ID = 1
SEASON = 2026

DAILY_QUOTA = 100
PER_MIN = 10

# TTL（秒）
TTL = {
    "teams": 30 * 86400,
    "squad": 86400,
    "fixtures": 6 * 3600,
    "standings": 3600,
    "injuries": 3 * 3600,
}

NEWS_DOMAINS = [
    "bbc.com/sport",
    "espn.com",
    "theathletic.com",
    "goal.com",
    "fifa.com",
]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cache.db"
STAR_JSON_PATH = DATA_DIR / "star_players.json"

API_BASE = "https://v3.football.api-sports.io"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_KEY", "")

DATA_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 9: 跑測試確認通過**

Run: `pytest tests/test_config.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 10: Commit**

```bash
git add .gitignore requirements.txt .env.example config.py tests/test_config.py
git commit -m "chore: project skeleton and config"
```

---

## Phase 1：資料層

### Task 1: SQLite schema 與連線

**Files:**
- Create: `db/__init__.py`（空）, `db/schema.py`, `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_schema.py`**

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL（`ModuleNotFoundError: db.schema`）。

> 設計取捨（對 spec §2.2 的簡化）：不建正規化的 teams/players/fixtures 表，改把各端點原始 JSON 直接存進 `cache_meta`（key=端點識別）。agent 消費的是 JSON，正規化表非必要（YAGNI）。

- [ ] **Step 3: 寫 `db/schema.py`**

```python
import sqlite3
import config

_conn = None

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_meta (
            cache_key   TEXT PRIMARY KEY,
            fetched_at  REAL NOT NULL,
            payload_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kv (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()

def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        init_db(_conn)
    return _conn
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_schema.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```bash
git add db/__init__.py db/schema.py tests/test_schema.py
git commit -m "feat: sqlite schema with WAL"
```

### Task 2: 快取核心 `get_or_fetch`（含 stale fallback）

**Files:**
- Create: `db/cache.py`, `tests/test_cache.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_cache.py`**

```python
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
        calls.append(1); return {"v": 1}
    out = cache.get_or_fetch(conn, "k", ttl=100, fetch_fn=fetch, now=0)
    assert out == {"v": 1} and len(calls) == 1

def test_hit_within_ttl_skips_fetch(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)
    def boom(): raise AssertionError("should not fetch")
    out = cache.get_or_fetch(conn, "k", 100, boom, now=50)
    assert out == {"v": 1}

def test_refetch_after_ttl(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)
    out = cache.get_or_fetch(conn, "k", 100, lambda: {"v": 2}, now=200)
    assert out == {"v": 2}

def test_stale_fallback_on_fetch_error(conn):
    cache.get_or_fetch(conn, "k", 100, lambda: {"v": 1}, now=0)
    def boom(): raise RuntimeError("api down")
    out = cache.get_or_fetch(conn, "k", 100, boom, now=999)
    assert out == {"v": 1}  # 過期但抓取失敗 → 回舊資料

def test_raises_when_no_cache_and_fetch_fails(conn):
    def boom(): raise RuntimeError("api down")
    with pytest.raises(RuntimeError):
        cache.get_or_fetch(conn, "k", 100, boom, now=0)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL（`ModuleNotFoundError: db.cache`）。

- [ ] **Step 3: 寫 `db/cache.py`**

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_cache.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: Commit**

```bash
git add db/cache.py tests/test_cache.py
git commit -m "feat: ttl cache with stale fallback"
```

### Task 3: 配額與每分鐘 RateLimiter

**Files:**
- Create: `db/quota.py`, `tests/test_quota.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_quota.py`**

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_quota.py -v`
Expected: FAIL（`ModuleNotFoundError: db.quota`）。

- [ ] **Step 3: 寫 `db/quota.py`**

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_quota.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: Commit**

```bash
git add db/quota.py tests/test_quota.py
git commit -m "feat: daily quota tracking + per-minute rate limiter"
```

---

## Phase 2：API-Football 工具

### Task 4: 請求底層 + 自適應 live TTL

**Files:**
- Create: `tools/__init__.py`（空）, `tools/apifootball.py`, `tests/test_apifootball.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_apifootball.py`**

```python
import sqlite3
import pytest
from db import schema
import tools.apifootball as af

@pytest.fixture
def conn(tmp_path, monkeypatch):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    schema.init_db(c)
    return c

def test_request_returns_response_and_records_quota(conn, monkeypatch):
    def fake_get(url, params):
        return 200, {"response": [{"id": 1}]}, {"x-ratelimit-requests-remaining": "42"}
    monkeypatch.setattr(af, "_http_get", fake_get)
    from db import quota
    out = af._request(conn, "2026-06-17", "/teams", {"league": 1})
    assert out == [{"id": 1}]
    assert quota.remaining(conn, "2026-06-17") == 42

def test_request_blocked_when_quota_zero(conn, monkeypatch):
    from db import quota
    quota.record_response(conn, "2026-06-17", {"x-ratelimit-requests-remaining": "0"})
    monkeypatch.setattr(af, "_http_get",
                        lambda u, p: (_ for _ in ()).throw(AssertionError("no call")))
    with pytest.raises(af.QuotaExhausted):
        af._request(conn, "2026-06-17", "/teams", {"league": 1})

def test_live_ttl_divides_remaining_window(conn):
    # 還剩 7200s 到午夜、保留 80 配額 → 90s
    ttl = af.live_ttl(seconds_to_reset=7200, reserved_quota=80)
    assert 89 <= ttl <= 91

def test_live_ttl_floor(conn):
    # 配額 0 不可除 → 回安全大值
    assert af.live_ttl(seconds_to_reset=3600, reserved_quota=0) >= 600
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_apifootball.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.apifootball`）。

- [ ] **Step 3: 寫 `tools/apifootball.py`（底層部分）**

```python
import httpx
from agents import function_tool
import config
from db import quota
from db.schema import get_conn
from db.cache import get_or_fetch

class QuotaExhausted(Exception):
    pass

_rl = quota.RateLimiter()

def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _http_get(url: str, params: dict):
    headers = {"x-apisports-key": config.APIFOOTBALL_KEY}
    r = httpx.get(url, params=params, headers=headers, timeout=20)
    return r.status_code, r.json(), dict(r.headers)

def _request(conn, today: str, path: str, params: dict):
    if quota.remaining(conn, today) <= 0:
        raise QuotaExhausted(path)
    if not _rl.allow():
        raise QuotaExhausted("rate-limit/min")
    status, body, hdrs = _http_get(config.API_BASE + path, params)
    quota.record_response(conn, today, hdrs)
    if status != 200:
        raise RuntimeError(f"API {status}: {body}")
    return body.get("response", [])

def _cached(key: str, ttl: int, path: str, params: dict):
    conn, today = get_conn(), _today()
    def fetch():
        return {"response": _request(conn, today, path, params)}
    return get_or_fetch(conn, key, ttl, fetch)["response"]

def live_ttl(seconds_to_reset: int, reserved_quota: int) -> int:
    if reserved_quota <= 0:
        return 600
    return max(60, int(seconds_to_reset / reserved_quota))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_apifootball.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add tools/__init__.py tools/apifootball.py tests/test_apifootball.py
git commit -m "feat: api-football request layer + adaptive live ttl"
```

### Task 5: 6 個 API-Football function tools

**Files:**
- Modify: `tools/apifootball.py`（附加 tools）
- Test: `tests/test_apifootball_tools.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_apifootball_tools.py`**

```python
import tools.apifootball as af

def test_get_squad_uses_cache(monkeypatch):
    captured = {}
    def fake_cached(key, ttl, path, params):
        captured.update(key=key, path=path, params=params); return [{"player": "x"}]
    monkeypatch.setattr(af, "_cached", fake_cached)
    out = af.get_squad(26)   # function_tool 包裝後仍可直呼底層；見下
    assert out == [{"player": "x"}]
    assert captured["path"] == "/players/squads"
    assert captured["params"]["team"] == 26
    assert "squad:26" in captured["key"]

def test_find_team_id_matches_name(monkeypatch):
    monkeypatch.setattr(af, "_teams",
        lambda: [{"team": {"id": 26, "name": "Argentina"}}])
    assert af._find_team_id("Argentina") == 26
    assert af._find_team_id("argentina") == 26   # 大小寫不敏感
    assert af._find_team_id("Narnia") is None
```

> 註：`@function_tool` 包裝的函式，測試時呼叫其 `.__wrapped__` 或保留純函式版本。實作採「純函式 + 各自 function_tool 包裝」雙層，純函式名稱加底線後綴供測試。

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_apifootball_tools.py -v`
Expected: FAIL（`AttributeError: get_squad`）。

- [ ] **Step 3: 在 `tools/apifootball.py` 附加純函式 + function_tool 包裝**

```python
# --- 純函式（可測） ---
def _teams():
    return _cached("teams", config.TTL["teams"], "/teams",
                   {"league": config.LEAGUE_ID, "season": config.SEASON})

def _squad(team_id: int):
    return _cached(f"squad:{team_id}", config.TTL["squad"],
                   "/players/squads", {"team": team_id})

def _find_team_id(name: str):
    """從已快取的 teams 清單，用名稱找 team_id（resolve_entity 之後的橋）。"""
    for t in _teams():
        if name.lower() == t["team"]["name"].lower():
            return t["team"]["id"]
    # 退一步：包含匹配
    for t in _teams():
        if name.lower() in t["team"]["name"].lower():
            return t["team"]["id"]
    return None

def _player_stats(team_id: int):
    return _cached(f"players:{team_id}", config.TTL["squad"], "/players",
                   {"team": team_id, "season": config.SEASON})

def _fixtures(team_id: int | None = None):
    params = {"league": config.LEAGUE_ID, "season": config.SEASON}
    if team_id:
        params["team"] = team_id
    return _cached(f"fixtures:{team_id or 'all'}", config.TTL["fixtures"],
                   "/fixtures", params)

def _standings(group: str | None = None):
    return _cached("standings", config.TTL["standings"], "/standings",
                   {"league": config.LEAGUE_ID, "season": config.SEASON})

def _injuries(team_id: int):
    return _cached(f"injuries:{team_id}", config.TTL["injuries"], "/injuries",
                   {"team": team_id, "season": config.SEASON})

def _live():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    secs = (86400 - (now.hour*3600 + now.minute*60 + now.second))
    conn = get_conn()
    ttl = live_ttl(secs, max(1, quota.remaining(conn, _today()) - 20))
    return _cached("live", ttl, "/fixtures", {"live": "all"})

# 測試別名（純函式直呼）
get_squad = _squad  # 供 test_apifootball_tools.py 直呼

# --- function_tool 包裝（agent 用） ---
@function_tool
def tool_find_team(name: str) -> int:
    """把球隊的拉丁名稱（resolve_entity 的 canonical_name）轉成 team_id；查無回 0。"""
    return _find_team_id(name) or 0

@function_tool
def tool_get_squad(team_id: int) -> list:
    """取得某隊（team_id）的世界盃陣容名單。"""
    return _squad(team_id)

@function_tool
def tool_get_player_stats(team_id: int) -> list:
    """取得某隊球員的賽季數據（含年齡、進球、出場）。"""
    return _player_stats(team_id)

@function_tool
def tool_get_fixtures(team_id: int = 0) -> list:
    """取得賽程；team_id=0 表示全部賽程。"""
    return _fixtures(team_id or None)

@function_tool
def tool_get_standings() -> list:
    """取得世界盃分組排名。"""
    return _standings()

@function_tool
def tool_get_injuries(team_id: int) -> list:
    """取得某隊傷兵名單（事實型困難點）。"""
    return _injuries(team_id)

@function_tool
def tool_get_live() -> list:
    """取得目前所有進行中比賽的即時比分（自適應更新間隔）。"""
    return _live()
```

> 修正測試對齊：將 Step 1 測試中的 `af.get_squad` 對應到 `_squad`（已 `get_squad = _squad` 別名）。

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_apifootball_tools.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: Commit**

```bash
git add tools/apifootball.py tests/test_apifootball_tools.py
git commit -m "feat: api-football function tools (squad/stats/fixtures/standings/injuries/live)"
```

---

## Phase 3：實體解析 + Web 搜尋

### Task 6: `resolve_entity`

**Files:**
- Create: `tools/resolve.py`, `data/aliases.json`, `tests/test_resolve.py`

- [ ] **Step 1: 寫種子別名表 `data/aliases.json`**

```json
{
  "teams": {"阿根廷": "Argentina", "巴西": "Brazil", "法國": "France",
            "德國": "Germany", "西班牙": "Spain", "英格蘭": "England"},
  "players": {"梅西": {"name": "Messi", "team": "Argentina"},
              "姆巴佩": {"name": "Mbappe", "team": "France"}}
}
```

- [ ] **Step 2: 寫失敗測試 `tests/test_resolve.py`**

```python
import tools.resolve as r

def test_resolve_known_team():
    out = r.resolve("阿根廷")
    assert out["type"] == "team" and out["canonical_name"] == "Argentina"

def test_resolve_known_player():
    out = r.resolve("梅西")
    assert out["type"] == "player"
    assert out["canonical_name"] == "Messi" and out["team"] == "Argentina"

def test_unknown_passes_through_as_query():
    out = r.resolve("某冷門球員")
    assert out["type"] == "unknown" and out["canonical_name"] == "某冷門球員"
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `pytest tests/test_resolve.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.resolve`）。

- [ ] **Step 4: 寫 `tools/resolve.py`**

```python
import json
from agents import function_tool
import config

def _load():
    import os
    path = config.DATA_DIR / "aliases.json"
    if not os.path.exists(path):
        return {"teams": {}, "players": {}}
    return json.loads(open(path, encoding="utf-8").read())

def resolve(text: str) -> dict:
    data = _load()
    t = text.strip()
    if t in data["teams"]:
        return {"type": "team", "canonical_name": data["teams"][t]}
    if t in data["players"]:
        p = data["players"][t]
        return {"type": "player", "canonical_name": p["name"], "team": p["team"]}
    return {"type": "unknown", "canonical_name": t}

@function_tool
def resolve_entity(text: str) -> dict:
    """把中文隊名/球員名解析成 API-Football 認得的拉丁名稱。
    回 {type: team|player|unknown, canonical_name, [team]}。
    type=unknown 時，後續用 canonical_name 當 ?search= 字串。"""
    return resolve(text)
```

- [ ] **Step 5: 跑測試確認通過**

Run: `pytest tests/test_resolve.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: Commit**

```bash
git add tools/resolve.py data/aliases.json tests/test_resolve.py
git commit -m "feat: resolve_entity (zh name -> latin)"
```

### Task 7: Tavily `web_search`

**Files:**
- Create: `tools/web.py`, `tests/test_web.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_web.py`**

```python
import tools.web as w

def test_web_search_passes_domains(monkeypatch):
    captured = {}
    def fake_post(url, json, headers):
        captured.update(json); 
        class R:
            def json(self): return {"results": [{"title": "t", "url": "u", "content": "c"}]}
            status_code = 200
        return R()
    monkeypatch.setattr(w.httpx, "post", fake_post)
    out = w.search("Messi 2026", domains=["espn.com"])
    assert out[0]["title"] == "t"
    assert captured["include_domains"] == ["espn.com"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_web.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.web`）。

- [ ] **Step 3: 寫 `tools/web.py`**

```python
import httpx
from agents import function_tool
import config

def search(query: str, domains: list[str] | None = None) -> list[dict]:
    payload = {
        "api_key": config.TAVILY_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_domains": domains or config.NEWS_DOMAINS,
    }
    r = httpx.post("https://api.tavily.com/search", json=payload,
                   headers={"Content-Type": "application/json"})
    data = r.json()
    return [{"title": x["title"], "url": x["url"], "content": x["content"]}
            for x in data.get("results", [])]

@function_tool
def web_search(query: str) -> list:
    """搜尋英文足球新聞（限 BBC/ESPN/The Athletic/Goal/FIFA），回標題+連結+摘要。"""
    return search(query)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_web.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: Commit**

```bash
git add tools/web.py tests/test_web.py
git commit -m "feat: tavily web_search anchored to english news"
```

---

## Phase 4：球星離線建檔

### Task 8: 建檔指示 + 載入器

**Files:**
- Create: `build_stars.md`, `tools/stars.py`, `data/star_players.sample.json`, `tests/test_stars.py`

- [ ] **Step 1: 寫 `build_stars.md`（給 Claude Code agent 的指示）**

```markdown
# 球星建檔任務（在 Claude Code 內以 agent 執行）

目標：產出 `data/star_players.json`，涵蓋 2026 世界盃主要球隊的代表性球星。

來源（僅此兩類）：
- Wikipedia：各隊世界盃名單頁、球員個人頁（取年齡、國家隊 caps、參賽屆數）
- 新聞 web search：BBC Sport / ESPN / The Athletic（取本屆看點敘事）
- 不爬 Transfermarkt。

每位球星輸出物件：
{
  "name_en": "Lionel Messi",
  "name_zh_aliases": ["梅西", "美斯"],
  "team": "Argentina",
  "age": 38,
  "caps": 190,
  "tournaments_played": 5,
  "classification": "老將",          // 老將 | 當打 | 新秀（年齡為硬依據，資歷佐證）
  "one_line_insight": "可能的最後一屆，傳奇收官看點",
  "sources": ["https://en.wikipedia.org/wiki/Lionel_Messi"]
}

分類規則：age>=32 且多屆=老將；age<=21 或首屆=新秀；其餘=當打。
輸出為合法 JSON 陣列，寫入 data/star_players.json。完成後人工抽查 5 筆。
```

- [ ] **Step 2: 寫測試樣本 `data/star_players.sample.json`**

```json
[
  {"name_en": "Lionel Messi", "name_zh_aliases": ["梅西"], "team": "Argentina",
   "age": 38, "caps": 190, "tournaments_played": 5, "classification": "老將",
   "one_line_insight": "傳奇收官看點", "sources": ["https://en.wikipedia.org/wiki/Lionel_Messi"]}
]
```

- [ ] **Step 3: 寫失敗測試 `tests/test_stars.py`**

```python
import tools.stars as s

def test_load_and_find_by_alias(tmp_path, monkeypatch):
    import config, shutil
    shutil.copy("data/star_players.sample.json", tmp_path / "star_players.json")
    monkeypatch.setattr(config, "STAR_JSON_PATH", tmp_path / "star_players.json")
    s._cache = None
    prof = s.find("梅西")
    assert prof and prof["classification"] == "老將"

def test_find_unknown_returns_none(tmp_path, monkeypatch):
    import config, shutil
    shutil.copy("data/star_players.sample.json", tmp_path / "star_players.json")
    monkeypatch.setattr(config, "STAR_JSON_PATH", tmp_path / "star_players.json")
    s._cache = None
    assert s.find("無此人") is None
```

- [ ] **Step 4: 跑測試確認失敗**

Run: `pytest tests/test_stars.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.stars`）。

- [ ] **Step 5: 寫 `tools/stars.py`**

```python
import json
import os
from agents import function_tool
import config

_cache = None

def _all():
    global _cache
    if _cache is None:
        if os.path.exists(config.STAR_JSON_PATH):
            _cache = json.loads(open(config.STAR_JSON_PATH, encoding="utf-8").read())
        else:
            _cache = []
    return _cache

def find(name: str):
    for p in _all():
        if name == p["name_en"] or name in p.get("name_zh_aliases", []):
            return p
    return None

@function_tool
def get_star_profile(name: str) -> dict:
    """查球星的離線建檔（老將/新秀分類、年齡、屆數、一句話看點）。查無回 {}。"""
    return find(name) or {}
```

- [ ] **Step 6: 跑測試確認通過**

Run: `pytest tests/test_stars.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 7: Commit**

```bash
git add build_stars.md tools/stars.py data/star_players.sample.json tests/test_stars.py
git commit -m "feat: star profile loader + build instructions"
```

- [ ] **Step 8: 執行建檔（手動里程碑）**

在 Claude Code 內依 `build_stars.md` 開一個 agent 產出 `data/star_players.json`，人工抽查後手動加入版本控制（此檔不在 .gitignore）。

---

## Phase 5：Agents

### Task 9: XML system prompts

**Files:**
- Create: `wc_agents/__init__.py`（空）, `wc_agents/prompts.py`, `tests/test_prompts.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_prompts.py`**

```python
from wc_agents import prompts

def test_all_prompts_xml_structured():
    for p in [prompts.TRIAGE, prompts.SQUAD, prompts.FIXTURE,
              prompts.STAR, prompts.INSIGHT]:
        assert "<role>" in p and "<rules>" in p and "<output_format>" in p
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL（`ModuleNotFoundError: wc_agents`）。

- [ ] **Step 3: 寫 `wc_agents/prompts.py`**

```python
TRIAGE = """<role>你是 2026 世界盃問答系統的分流員。</role>
<rules>
  <rule>判斷使用者問題屬於哪一類，handoff 給對應專家，不要自己回答。</rule>
  <rule>名單/陣容/誰入選 → Squad；賽程/比分/排名/下一場 → Fixture；
        球星/老將/新星/某球員看點 → Star；看點/隱憂/困難/戰術分析 → Insight。</rule>
  <rule>問題含多領域時，挑最主要的一個 handoff，並提示使用者可分開再問其餘。</rule>
  <rule>問題模糊時，先反問澄清。</rule>
</rules>
<output_format>只做 handoff 或一句澄清提問。</output_format>"""

SQUAD = """<role>你是世界盃陣容專家。</role>
<rules>
  <rule>查資料前先呼叫 resolve_entity 取得 canonical 名稱，再用 tool_find_team 換成 team_id。</rule>
  <rule>用 tool_get_squad / tool_get_player_stats（皆吃 team_id）取名單與數據。</rule>
</rules>
<output_format>依位置分組（門將/後衛/中場/前鋒），標出隊長與核心，附背號。</output_format>"""

FIXTURE = """<role>你是世界盃賽程專家。</role>
<rules>
  <rule>查隊伍賽程前先 resolve_entity，再用 tool_find_team 取得 team_id。</rule>
  <rule>即時比分用 tool_get_live；賽程用 tool_get_fixtures；排名用 tool_get_standings。</rule>
</rules>
<output_format>分「已賽/未賽」；未賽給對手+時間，已賽給比分；排名附積分與淨勝球。</output_format>"""

STAR = """<role>你是世界盃球星分析專家，專長辨識老將與新秀。</role>
<rules>
  <rule>先 resolve_entity；再優先用 get_star_profile 讀離線建檔分類。</rule>
  <rule>建檔沒有時：用 tool_find_team 取 team_id → tool_get_player_stats（年齡/數據）+ web_search 補。</rule>
  <rule>web_search 僅限英文新聞站，不得引用未列來源。</rule>
</rules>
<output_format>每位球星：定位（老將/當打/新秀+年齡/屆數）｜一句話看點｜數據或新聞佐證。</output_format>"""

INSIGHT = """<role>你是世界盃看點與困難點分析專家。</role>
<rules>
  <rule>先 resolve_entity → tool_find_team 取 team_id；事實型困難點用 tool_get_injuries。</rule>
  <rule>分析型看點用 web_search（英文站），需具體可期待，不講空話。</rule>
</rules>
<output_format>困難點分「事實型（傷兵/禁賽/賽程密集）」與「分析型（戰術/狀態）」；看點條列。</output_format>"""
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: Commit**

```bash
git add wc_agents/__init__.py wc_agents/prompts.py tests/test_prompts.py
git commit -m "feat: xml-structured agent prompts"
```

### Task 10: 四個專責 Agent

**Files:**
- Create: `wc_agents/specialists.py`, `tests/test_specialists.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_specialists.py`**

```python
from wc_agents import specialists

def test_specialists_have_expected_tools():
    names = lambda a: {t.name for t in a.tools}
    assert "resolve_entity" in names(specialists.squad_agent)
    assert "tool_get_live" in names(specialists.fixture_agent)
    assert "get_star_profile" in names(specialists.star_agent)
    assert "tool_get_injuries" in names(specialists.insight_agent)

def test_specialists_named():
    assert specialists.squad_agent.name == "Squad"
    assert specialists.star_agent.name == "Star"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_specialists.py -v`
Expected: FAIL（`ModuleNotFoundError: wc_agents.specialists`）。

- [ ] **Step 3: 寫 `wc_agents/specialists.py`**

```python
from agents import Agent          # OpenAI Agents SDK
from wc_agents import prompts     # 本地 prompt 模組
from tools.resolve import resolve_entity
from tools.web import web_search
from tools.stars import get_star_profile
from tools.apifootball import (
    tool_find_team, tool_get_squad, tool_get_player_stats, tool_get_fixtures,
    tool_get_standings, tool_get_injuries, tool_get_live,
)

squad_agent = Agent(
    name="Squad", instructions=prompts.SQUAD,
    tools=[resolve_entity, tool_find_team, tool_get_squad, tool_get_player_stats])

fixture_agent = Agent(
    name="Fixture", instructions=prompts.FIXTURE,
    tools=[resolve_entity, tool_find_team, tool_get_fixtures,
           tool_get_standings, tool_get_live])

star_agent = Agent(
    name="Star", instructions=prompts.STAR,
    tools=[resolve_entity, tool_find_team, get_star_profile,
           tool_get_player_stats, web_search])

insight_agent = Agent(
    name="Insight", instructions=prompts.INSIGHT,
    tools=[resolve_entity, tool_find_team, tool_get_injuries, web_search])
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_specialists.py -v`
Expected: PASS（2 passed）。若 `t.name` 屬性名不符，改用 SDK 實際屬性（`tool.name`）。

- [ ] **Step 5: Commit**

```bash
git add wc_agents/specialists.py tests/test_specialists.py
git commit -m "feat: four specialist agents with tools"
```

### Task 11: Triage Agent

**Files:**
- Create: `wc_agents/triage.py`, `tests/test_triage.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_triage.py`**

```python
from wc_agents.triage import triage_agent

def test_triage_has_four_handoffs():
    names = {h.name for h in triage_agent.handoffs}
    assert {"Squad", "Fixture", "Star", "Insight"} <= names
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_triage.py -v`
Expected: FAIL（`ModuleNotFoundError: wc_agents.triage`）。

- [ ] **Step 3: 寫 `wc_agents/triage.py`**

```python
from agents import Agent          # OpenAI Agents SDK
from wc_agents import prompts
from wc_agents.specialists import (
    squad_agent, fixture_agent, star_agent, insight_agent)

triage_agent = Agent(
    name="Triage",
    instructions=prompts.TRIAGE,
    handoffs=[squad_agent, fixture_agent, star_agent, insight_agent],
)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_triage.py -v`
Expected: PASS（1 passed）。若 handoff 物件屬性不是 `.name`，改用 SDK 對應屬性。

- [ ] **Step 5: Commit**

```bash
git add wc_agents/triage.py tests/test_triage.py
git commit -m "feat: triage agent with handoffs"
```

---

## Phase 6：進入點與初始化

### Task 12: `main.py`

**Files:**
- Create: `main.py`

- [ ] **Step 1: 寫 `main.py`**

```python
import sys
from agents import Runner              # OpenAI Agents SDK
from wc_agents.triage import triage_agent

def ask(question: str) -> str:
    result = Runner.run_sync(triage_agent, question)
    return result.final_output

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("問世界盃什麼？ ")
    print(ask(q))
```

- [ ] **Step 2: 手動冒煙測試（需 .env 已填 key 且已跑過 init_db）**

Run: `python main.py "阿根廷這次帶哪些人？"`
Expected: 透過 Triage → Squad，輸出依位置分組的名單（或在無資料時誠實說明）。

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: cli entrypoint"
```

### Task 13: `init_db.py`（節流 + 續跑）

**Files:**
- Create: `init_db.py`

- [ ] **Step 1: 寫 `init_db.py`**

```python
import time
from db.schema import get_conn
from db.cache import cache_get
import tools.apifootball as af

THROTTLE_SEC = 6  # 守住 10 次/分

def main():
    conn = get_conn()
    teams = af._teams()
    print(f"teams: {len(teams)}")
    for t in teams:
        tid = t["team"]["id"]
        if cache_get(conn, f"squad:{tid}"):
            continue                      # 續跑：已抓過跳過
        af._squad(tid)
        print(f"squad {tid} ok")
        time.sleep(THROTTLE_SEC)
    af._fixtures(None)
    af._standings(None)
    print("init done")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 手動執行（建議獨立一天跑）**

Run: `python init_db.py`
Expected: 印出各隊 squad 進度；中斷後重跑會跳過已抓的隊伍。

- [ ] **Step 3: Commit**

```bash
git add init_db.py
git commit -m "feat: throttled resumable db initialization"
```

---

## Phase 7：端到端驗證

### Task 14: 全測試 + 端到端

- [ ] **Step 1: 跑全部單元測試**

Run: `pytest -v`
Expected: 全綠。

- [ ] **Step 2: 端到端（需 keys + init_db + star_players.json）**

逐一手動驗證並記錄輸出：
```bash
python main.py "巴西下一場打誰？"          # Fixture
python main.py "梅西這屆值得看的點？"        # Star（讀離線建檔）
python main.py "德國這屆最大隱憂？"          # Insight
python main.py "法國前鋒線有誰？"           # Squad
```
Expected: 各自正確 handoff、輸出符合該 agent 的 `<output_format>`，資料缺漏時誠實標註。

- [ ] **Step 3: Commit（若有微調）**

```bash
git add -A
git commit -m "test: end-to-end verification pass"
```

---

## 未來擴充（不在本計畫範圍）
複合問答：用 SDK `agent.as_tool()` 把四專家包成工具，新增 Orchestrator fan-out + 統整，Triage 對複合問題改 handoff 給 Orchestrator。工具/快取/解析/prompt 全沿用。詳見 spec §6。
```
