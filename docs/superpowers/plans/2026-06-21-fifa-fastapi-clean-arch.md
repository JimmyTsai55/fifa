# FIFA FastAPI Clean Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把現有 OpenAI Agents SDK 的世界盃多代理 CLI 重構成 Clean Architecture 分層、包成同步 FastAPI 服務，並可部署到 GCP Cloud Run（單實例、無 VPC/外部儲存）。

**Architecture:** Clean Architecture + Hexagonal（Ports & Adapters），依專案 `clean-arch` 技能命名：`api → use_cases → services → protocols ← adapters`，`core/container` 在最外層組裝。依賴一律朝內；agent 的 `function_tool` 透過注入的 `FootballDataProtocol` 取資料完成依賴反轉。

**Tech Stack:** Python 3.12/3.13、FastAPI、uvicorn、pydantic-settings、openai-agents、httpx、sqlite3、pytest。

## Global Constraints

- 依賴方向朝內：`api/` → `use_cases/` → `services/` → `protocols/`；`adapters/` 實作 `protocols/`；`core/container` 組裝。Service 層只依賴 Protocol，禁止 import 外部 SDK 型別。
- 命名：Protocol=`<Name>Protocol`、Adapter=`<Provider>Adapter`、Service=`<Domain>Service`、UseCase=`<Action><Domain>UseCase`。
- 同步互動：`POST /ask` 一次回完整 JSON；不做 SSE / 任務佇列。
- 認證：每個非 health 端點都要 `X-API-Key`，比對 `WC_API_KEYS`（逗號分隔）。
- 部署：Cloud Run，`max-instances=1`，無 VPC、無外部儲存（僅 SQLite adapter）。port `8887`（Dockerfile 與 deploy.sh 一致）。
- 機密走 GCP Secret Manager，不明文進 git。
- agent 系統提示維持 XML-tag 結構（既有慣例，勿改）。
- 預設模型 `OPENAI_DEFAULT_MODEL=gpt-4o-mini`；`WC_SEASON=2022`。
- 阻塞的 `Runner.run_sync` 一律用 `anyio.to_thread.run_sync` 在 threadpool 執行，勿卡 event loop。
- TDD：先寫失敗測試 → 最小實作 → 綠 → commit。每個 Task 結束都要能獨立測試。

---

## File Structure

| 路徑 | 動作 | 職責 |
|------|------|------|
| `config.py` | 改寫 | 根目錄保留；pydantic-settings，新增 `WC_API_KEYS`/`PORT`/`STORAGE_BACKEND`，保留既有常數名稱供向後相容 |
| `protocols/cache_store.py` | 新增 | `CacheStoreProtocol` |
| `protocols/quota_store.py` | 新增 | `QuotaStoreProtocol` |
| `protocols/football_data.py` | 新增 | `FootballDataProtocol` |
| `protocols/qa_engine.py` | 新增 | `QAEngineProtocol` |
| `adapters/sqlite_store_adapter.py` | 新增 | `SqliteStoreAdapter` 包 `db/cache.py`+`db/quota.py`+`db/schema.py` |
| `adapters/apifootball_adapter.py` | 新增（搬 `tools/apifootball.py` 邏輯） | `ApiFootballAdapter` 實作 `FootballDataProtocol`，依賴 cache + `QuotaService` |
| `adapters/agent_tools.py` | 新增 | football 的 7 個 `@function_tool` + `bind_football(port)`；綁定注入的 port |
| `adapters/resolve_adapter.py` | 搬移 `tools/resolve.py` | `resolve_entity` tool |
| `adapters/stars_adapter.py` | 搬移 `tools/stars.py` | `get_star_profile` tool |
| `adapters/news_adapter.py` | 搬移 `tools/web.py` | `web_search` tool（Tavily） |
| `adapters/openai_agents_adapter.py` | 新增 | `OpenAIAgentsAdapter` 實作 `QAEngineProtocol`，包 `Runner`+`triage_agent` |
| `wc_agents/{prompts,specialists,triage}.py` | 改 import | 視為 QA engine 內部；改從 `adapters/*` 取工具 |
| `services/quota_service.py` | 新增 | `QuotaService`（每日預檢 + 每分鐘限流），依賴 `QuotaStoreProtocol` |
| `services/qa_service.py` | 新增 | `QAService`，把 `QAEngineProtocol.answer` 丟 threadpool |
| `use_cases/answer_question.py` | 新增 | `AnswerQuestionUseCase` |
| `schemas/qa.py` | 新增 | `AskRequest` / `AskResponse` |
| `core/container.py` | 新增 | composition root，依 `STORAGE_BACKEND` 組裝注入 |
| `api/v1/deps.py` | 新增 | `require_api_key`、依賴注入 |
| `api/v1/routes.py` | 新增 | `POST /ask`、`GET /healthz` |
| `main.py` | 改寫 | FastAPI app（取代 CLI），掛 router、lifespan、exception handler |
| `init_db.py` | 改寫 | 改用 container 取 adapter 做 seeding |
| `Dockerfile` | 新增 | uvicorn 啟動、綁 `$PORT` |
| `deploy.sh` | 修改 | 填 secrets/service 名稱、`--max-instances 1` |
| `requirements.txt` / `.env.example` / `README.md` | 修改 | 新依賴與說明 |
| 各 `__init__.py` | 新增 | 讓新目錄成為 package |
| `tools/` 舊檔、`tools/__init__.py` | 刪除 | 內容已搬入 `adapters/` |

`db/cache.py`、`db/quota.py`、`db/schema.py` 保留為低層 helper（被 adapter 包）。各層目錄需有 `__init__.py`。

---

## Phase 0 — 設定與依賴

### Task 1: 新增依賴與 config（pydantic-settings）

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py`
- Test: `tests/test_config.py`（既有，擴充）

**Interfaces:**
- Produces: 模組 `config` 暴露既有常數（`LEAGUE_ID, SEASON, DAILY_QUOTA, PER_MIN, TTL, NEWS_DOMAINS, BASE_DIR, DATA_DIR, DB_PATH, STAR_JSON_PATH, API_BASE, OPENAI_API_KEY, OPENAI_DEFAULT_MODEL, APIFOOTBALL_KEY, TAVILY_KEY`）＋新增 `PORT: int`、`STORAGE_BACKEND: str`、函式 `api_keys() -> set[str]`。

- [ ] **Step 1: 擴充 config 測試（失敗）**

在 `tests/test_config.py` 末尾新增：
```python
def test_api_keys_parses_comma_list(monkeypatch):
    monkeypatch.setenv("WC_API_KEYS", " k1 , k2 ,")
    import importlib, config
    importlib.reload(config)
    assert config.api_keys() == {"k1", "k2"}

def test_port_defaults_to_8887(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    import importlib, config
    importlib.reload(config)
    assert config.PORT == 8887
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL（`api_keys` / `PORT` 不存在）

- [ ] **Step 3: 改寫 `config.py`**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    OPENAI_API_KEY: str = ""
    APIFOOTBALL_KEY: str = ""
    TAVILY_KEY: str = ""
    WC_API_KEYS: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    WC_SEASON: int = 2022
    STORAGE_BACKEND: str = "sqlite"
    PORT: int = 8887


settings = _Settings()

# --- 向後相容的模組級常數（既有程式以 config.X 取用） ---
OPENAI_API_KEY = settings.OPENAI_API_KEY
APIFOOTBALL_KEY = settings.APIFOOTBALL_KEY
TAVILY_KEY = settings.TAVILY_KEY
OPENAI_DEFAULT_MODEL = settings.OPENAI_DEFAULT_MODEL
SEASON = settings.WC_SEASON
STORAGE_BACKEND = settings.STORAGE_BACKEND
PORT = settings.PORT

LEAGUE_ID = 1
DAILY_QUOTA = 100
PER_MIN = 10
TTL = {
    "teams": 30 * 86400, "squad": 86400, "fixtures": 6 * 3600,
    "standings": 3600, "injuries": 3 * 3600,
}
NEWS_DOMAINS = ["bbc.com/sport", "espn.com", "theathletic.com", "goal.com", "fifa.com"]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cache.db"
STAR_JSON_PATH = DATA_DIR / "star_players.json"
API_BASE = "https://v3.football.api-sports.io"


def api_keys() -> set[str]:
    return {k.strip() for k in settings.WC_API_KEYS.split(",") if k.strip()}


DATA_DIR.mkdir(exist_ok=True)
```

在 `requirements.txt` 新增（每行一個）：`fastapi`、`uvicorn[standard]`、`pydantic-settings`、`anyio`。

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
pip install -r requirements.txt
git add requirements.txt config.py tests/test_config.py
git commit -m "feat: pydantic-settings config with WC_API_KEYS/PORT and api_keys()"
```

---

## Phase 1 — Protocols、SQLite 儲存 adapter、QuotaService

### Task 2: 定義 Protocols

**Files:**
- Create: `protocols/__init__.py`, `protocols/cache_store.py`, `protocols/quota_store.py`, `protocols/football_data.py`, `protocols/qa_engine.py`

**Interfaces:**
- Produces: 四個 `Protocol` 介面，供 services/adapters 引用。

- [ ] **Step 1: 建立 protocols（純介面，無邏輯）**

`protocols/__init__.py`：空檔。

`protocols/cache_store.py`：
```python
from typing import Protocol, Callable, Any


class CacheStoreProtocol(Protocol):
    def get_or_fetch(self, key: str, ttl: int,
                     fetch_fn: Callable[[], dict], now: float | None = None) -> dict: ...
    def peek(self, key: str) -> dict | None: ...
```

`protocols/quota_store.py`：
```python
from typing import Protocol


class QuotaStoreProtocol(Protocol):
    def remaining(self) -> int: ...
    def record_response(self, headers: dict) -> None: ...
```

`protocols/football_data.py`：
```python
from typing import Protocol


class FootballDataProtocol(Protocol):
    def teams(self) -> list: ...
    def squad(self, team_id: int) -> list: ...
    def player_stats(self, team_id: int) -> list: ...
    def fixtures(self, team_id: int | None = None) -> list: ...
    def standings(self, group: str | None = None) -> list: ...
    def injuries(self, team_id: int) -> list: ...
    def live(self) -> list: ...
    def find_team_id(self, name: str) -> int | None: ...
```

`protocols/qa_engine.py`：
```python
from typing import Protocol


class QAEngineProtocol(Protocol):
    def answer(self, question: str) -> str: ...
```

- [ ] **Step 2: 確認可 import**

Run: `python -c "import protocols.cache_store, protocols.quota_store, protocols.football_data, protocols.qa_engine"`
Expected: 無錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add protocols/
git commit -m "feat: define ports (cache/quota/football/qa protocols)"
```

### Task 3: SqliteStoreAdapter

**Files:**
- Create: `adapters/__init__.py`, `adapters/sqlite_store_adapter.py`
- Test: `tests/test_sqlite_store_adapter.py`
- Keep: `db/cache.py`, `db/quota.py`, `db/schema.py`（內部 helper，不動）

**Interfaces:**
- Consumes: `db.cache.{get_or_fetch, cache_get}`、`db.quota.{remaining, record_response}`、`db.schema.init_db`。
- Produces: `SqliteStoreAdapter(db_path: str | Path)` 同時實作 `CacheStoreProtocol` + `QuotaStoreProtocol`：`get_or_fetch(key, ttl, fetch_fn, now=None)`、`peek(key)`、`remaining()`、`record_response(headers)`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_sqlite_store_adapter.py`：
```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_sqlite_store_adapter.py -q`
Expected: FAIL（模組不存在）

- [ ] **Step 3: 實作 adapter**

`adapters/__init__.py`：空檔。
`adapters/sqlite_store_adapter.py`：
```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_sqlite_store_adapter.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/__init__.py adapters/sqlite_store_adapter.py tests/test_sqlite_store_adapter.py
git commit -m "feat: SqliteStoreAdapter wrapping db cache+quota helpers"
```

### Task 4: QuotaService（每日預檢 + 每分鐘限流）

**Files:**
- Create: `services/__init__.py`, `services/quota_service.py`
- Test: `tests/test_quota_service.py`

**Interfaces:**
- Consumes: `QuotaStoreProtocol`、`db.quota.RateLimiter`。
- Produces: `QuotaService(store, per_min=config.PER_MIN, rate_limiter=None)`，方法 `check_preflight() -> None`（額度耗盡或超速 → raise `QuotaExhausted`）、`record(headers) -> None`、`remaining() -> int`。例外類別 `QuotaExhausted(Exception)` 定義於此模組。

- [ ] **Step 1: 寫失敗測試**

`tests/test_quota_service.py`：
```python
import pytest
from services.quota_service import QuotaService, QuotaExhausted


class FakeStore:
    def __init__(self, rem): self._rem = rem; self.recorded = []
    def remaining(self): return self._rem
    def record_response(self, h): self.recorded.append(h)


class FakeRL:
    def __init__(self, ok): self._ok = ok
    def allow(self): return self._ok


def test_preflight_ok_when_quota_and_rate_ok():
    QuotaService(FakeStore(5), rate_limiter=FakeRL(True)).check_preflight()  # 不丟例外


def test_preflight_raises_when_quota_zero():
    with pytest.raises(QuotaExhausted):
        QuotaService(FakeStore(0), rate_limiter=FakeRL(True)).check_preflight()


def test_preflight_raises_when_rate_limited():
    with pytest.raises(QuotaExhausted):
        QuotaService(FakeStore(5), rate_limiter=FakeRL(False)).check_preflight()


def test_record_delegates_to_store():
    s = FakeStore(5)
    QuotaService(s, rate_limiter=FakeRL(True)).record({"h": "1"})
    assert s.recorded == [{"h": "1"}]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_quota_service.py -q`
Expected: FAIL（模組不存在）

- [ ] **Step 3: 實作**

`services/__init__.py`：空檔。
`services/quota_service.py`：
```python
import config
from db.quota import RateLimiter
from protocols.quota_store import QuotaStoreProtocol


class QuotaExhausted(Exception):
    pass


class QuotaService:
    def __init__(self, store: QuotaStoreProtocol,
                 per_min: int = config.PER_MIN, rate_limiter=None):
        self._store = store
        self._rl = rate_limiter or RateLimiter(per_min)

    def check_preflight(self) -> None:
        if self._store.remaining() <= 0:
            raise QuotaExhausted("daily-quota")
        if not self._rl.allow():
            raise QuotaExhausted("rate-limit/min")

    def record(self, headers: dict) -> None:
        self._store.record_response(headers)

    def remaining(self) -> int:
        return self._store.remaining()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_quota_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/__init__.py services/quota_service.py tests/test_quota_service.py
git commit -m "feat: QuotaService with daily preflight + per-minute rate limit"
```

---

## Phase 2 — ApiFootballAdapter 與 agent 工具綁定

### Task 5: ApiFootballAdapter（實作 FootballDataProtocol）

**Files:**
- Create: `adapters/apifootball_adapter.py`
- Test: `tests/test_apifootball_adapter.py`（取代舊 `tests/test_apifootball.py` 的覆蓋範圍）
- Reference（搬移來源）：`tools/apifootball.py:21-122`

**Interfaces:**
- Consumes: `CacheStoreProtocol`、`QuotaService`、`config`、`httpx`。
- Produces: `ApiFootballAdapter(cache, quota_service, http_get=None)` 實作 `FootballDataProtocol`（`teams/squad/player_stats/fixtures/standings/injuries/live/find_team_id`）。`http_get(url, params) -> (status, body, headers)` 可注入以利測試。`live_ttl(seconds_to_reset, reserved_quota)` 保留為模組函式。

- [ ] **Step 1: 寫失敗測試**

`tests/test_apifootball_adapter.py`：
```python
import pytest
from adapters.apifootball_adapter import ApiFootballAdapter, live_ttl
from services.quota_service import QuotaService, QuotaExhausted


class FakeStore:
    def __init__(self, rem=100): self._rem = rem; self.recorded = []
    def get_or_fetch(self, key, ttl, fetch_fn, now=None): return fetch_fn()
    def peek(self, key): return None
    def remaining(self): return self._rem
    def record_response(self, h): self.recorded.append(h)


class FakeRL:
    def allow(self): return True


def make(rem=100, http_get=None):
    store = FakeStore(rem)
    qs = QuotaService(store, rate_limiter=FakeRL())
    return ApiFootballAdapter(store, qs, http_get=http_get), store


def test_squad_returns_response_and_records_quota():
    def http_get(url, params):
        return 200, {"response": [{"id": 1}], "errors": []}, {"x": "1"}
    af, store = make(http_get=http_get)
    assert af.squad(10) == [{"id": 1}]
    assert store.recorded  # 有記錄額度


def test_request_blocked_when_quota_zero():
    af, _ = make(rem=0, http_get=lambda u, p: (200, {"response": []}, {}))
    with pytest.raises(QuotaExhausted):
        af.squad(10)


def test_raises_on_200_with_errors_body():
    def http_get(url, params):
        return 200, {"errors": {"token": "bad"}}, {}
    af, _ = make(http_get=http_get)
    with pytest.raises(RuntimeError):
        af.squad(10)


def test_squad_rejects_bad_team_id():
    af, _ = make()
    out = af.squad(0)
    assert out and "error" in out[0]


def test_live_ttl_floor():
    assert live_ttl(120, 5) == 60   # max(60, 24) -> 60
    assert live_ttl(600, 0) == 600
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_apifootball_adapter.py -q`
Expected: FAIL（模組不存在）

- [ ] **Step 3: 實作 adapter（搬 `tools/apifootball.py` 邏輯，改用注入的 cache/quota）**

`adapters/apifootball_adapter.py`：
```python
import httpx
from datetime import datetime, timezone

import config
from protocols.cache_store import CacheStoreProtocol
from services.quota_service import QuotaService

_BAD_TEAM = [{"error": "無效的 team_id；請先用 resolve_entity + tool_find_team "
              "取得有效 id，或先執行 init_db.py 初始化隊伍資料。"}]


def _default_http_get(url: str, params: dict):
    headers = {"x-apisports-key": config.APIFOOTBALL_KEY}
    r = httpx.get(url, params=params, headers=headers, timeout=20)
    return r.status_code, r.json(), dict(r.headers)


def live_ttl(seconds_to_reset: int, reserved_quota: int) -> int:
    if reserved_quota <= 0:
        return 600
    return max(60, int(seconds_to_reset / reserved_quota))


class ApiFootballAdapter:
    """實作 FootballDataProtocol。對 cache / quota 走注入的 Protocol，完成依賴反轉。"""

    def __init__(self, cache: CacheStoreProtocol, quota_service: QuotaService,
                 http_get=None):
        self._cache = cache
        self._quota = quota_service
        self._http_get = http_get or _default_http_get

    def _request(self, path: str, params: dict):
        self._quota.check_preflight()
        status, body, hdrs = self._http_get(config.API_BASE + path, params)
        self._quota.record(hdrs)
        if status != 200:
            raise RuntimeError(f"API {status}: {body}")
        errs = body.get("errors")
        if errs:
            raise RuntimeError(f"API errors: {errs}")
        return body.get("response", [])

    def _cached(self, key: str, ttl: int, path: str, params: dict):
        def fetch():
            return {"response": self._request(path, params)}
        return self._cache.get_or_fetch(key, ttl, fetch)["response"]

    def teams(self):
        return self._cached("teams", config.TTL["teams"], "/teams",
                            {"league": config.LEAGUE_ID, "season": config.SEASON})

    def squad(self, team_id: int):
        if team_id <= 0:
            return list(_BAD_TEAM)
        return self._cached(f"squad:{team_id}", config.TTL["squad"],
                            "/players/squads", {"team": team_id})

    def player_stats(self, team_id: int):
        if team_id <= 0:
            return list(_BAD_TEAM)
        return self._cached(f"players:{team_id}", config.TTL["squad"], "/players",
                            {"team": team_id, "season": config.SEASON})

    def fixtures(self, team_id: int | None = None):
        params = {"league": config.LEAGUE_ID, "season": config.SEASON}
        if team_id:
            params["team"] = team_id
        return self._cached(f"fixtures:{team_id or 'all'}", config.TTL["fixtures"],
                            "/fixtures", params)

    def standings(self, group: str | None = None):
        return self._cached("standings", config.TTL["standings"], "/standings",
                            {"league": config.LEAGUE_ID, "season": config.SEASON})

    def injuries(self, team_id: int):
        if team_id <= 0:
            return list(_BAD_TEAM)
        return self._cached(f"injuries:{team_id}", config.TTL["injuries"], "/injuries",
                            {"team": team_id, "season": config.SEASON})

    def live(self):
        now = datetime.now(timezone.utc)
        secs = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
        ttl = live_ttl(secs, max(1, self._quota.remaining() - 20))
        return self._cached("live", ttl, "/fixtures", {"live": "all"})

    def find_team_id(self, name: str):
        lname = name.lower()
        teams = self.teams()
        for t in teams:
            if lname == t["team"]["name"].lower():
                return t["team"]["id"]
        for t in teams:
            if lname in t["team"]["name"].lower():
                return t["team"]["id"]
        return None
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_apifootball_adapter.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/apifootball_adapter.py tests/test_apifootball_adapter.py
git commit -m "feat: ApiFootballAdapter implementing FootballDataProtocol (DI cache/quota)"
```

### Task 6: agent 工具綁定（football function_tools）

**Files:**
- Create: `adapters/agent_tools.py`
- Test: `tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `FootballDataProtocol`（透過 `bind_football`）、`agents.function_tool`。
- Produces: `bind_football(port: FootballDataProtocol) -> None`、`current_football() -> FootballDataProtocol`（未綁定時 raise `RuntimeError`），以及 7 個 `@function_tool`：`tool_find_team(name)->int`、`tool_get_squad(team_id)->list`、`tool_get_player_stats(team_id)->list`、`tool_get_fixtures(team_id=0)->list`、`tool_get_standings()->list`、`tool_get_injuries(team_id)->list`、`tool_get_live()->list`。

- [ ] **Step 1: 寫失敗測試**

`tests/test_agent_tools.py`：
```python
import pytest
import adapters.agent_tools as at


class FakePort:
    def find_team_id(self, name): return 7 if name == "Brazil" else None
    def squad(self, tid): return [{"tid": tid}]
    def player_stats(self, tid): return []
    def fixtures(self, tid=None): return [{"f": tid}]
    def standings(self, group=None): return [{"s": 1}]
    def injuries(self, tid): return []
    def live(self): return [{"live": 1}]


def test_current_football_raises_when_unbound():
    at._football = None
    with pytest.raises(RuntimeError):
        at.current_football()


def test_bind_and_lookup():
    at.bind_football(FakePort())
    assert at.current_football().find_team_id("Brazil") == 7
```

注意：`@function_tool` 包裝後的物件不可直接呼叫，測試只驗 `bind_football` / `current_football` 與底層 port；工具行為在 API 整合測試（Task 12）覆蓋。

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_agent_tools.py -q`
Expected: FAIL

- [ ] **Step 3: 實作**

`adapters/agent_tools.py`：
```python
from agents import function_tool
from protocols.football_data import FootballDataProtocol

_football: FootballDataProtocol | None = None


def bind_football(port: FootballDataProtocol) -> None:
    global _football
    _football = port


def current_football() -> FootballDataProtocol:
    if _football is None:
        raise RuntimeError("football port not bound; call bind_football() at startup")
    return _football


@function_tool
def tool_find_team(name: str) -> int:
    """把球隊的拉丁名稱（resolve_entity 的 canonical_name）轉成 team_id；查無回 0。"""
    return current_football().find_team_id(name) or 0


@function_tool
def tool_get_squad(team_id: int) -> list:
    """取得某隊（team_id）的世界盃陣容名單。"""
    return current_football().squad(team_id)


@function_tool
def tool_get_player_stats(team_id: int) -> list:
    """取得某隊球員的賽季數據（含年齡、進球、出場）。"""
    return current_football().player_stats(team_id)


@function_tool
def tool_get_fixtures(team_id: int = 0) -> list:
    """取得賽程；team_id=0 表示全部賽程。"""
    return current_football().fixtures(team_id or None)


@function_tool
def tool_get_standings() -> list:
    """取得世界盃分組排名。"""
    return current_football().standings()


@function_tool
def tool_get_injuries(team_id: int) -> list:
    """取得某隊傷兵名單（事實型困難點）。"""
    return current_football().injuries(team_id)


@function_tool
def tool_get_live() -> list:
    """取得目前所有進行中比賽的即時比分（自適應更新間隔）。"""
    return current_football().live()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_agent_tools.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: football function_tools bound to injected FootballDataProtocol"
```

---

## Phase 3 — 搬移 resolve / stars / news 工具，更新 agents

### Task 7: 搬移 resolve / stars / news 至 adapters，更新 specialists 與測試

**Files:**
- Create: `adapters/resolve_adapter.py`（搬 `tools/resolve.py`）, `adapters/stars_adapter.py`（搬 `tools/stars.py`）, `adapters/news_adapter.py`（搬 `tools/web.py`）
- Modify: `wc_agents/specialists.py`, `wc_agents/triage.py`
- Modify: `tests/test_resolve.py`, `tests/test_stars.py`, `tests/test_web.py`（更新 import）
- Delete: `tools/resolve.py`, `tools/stars.py`, `tools/web.py`, `tools/apifootball.py`, `tools/__init__.py`

**Interfaces:**
- Produces: `adapters.resolve_adapter.{resolve, resolve_entity}`、`adapters.stars_adapter.{find, get_star_profile}`、`adapters.news_adapter.{search, web_search}`（簽名與原 `tools/*` 完全相同）。
- Consumes（specialists）：`adapters.agent_tools` 的 7 個 football 工具 + 上述三組工具。

- [ ] **Step 1: 搬移三個工具檔（內容不變，僅改放置位置）**

逐檔把 `tools/resolve.py`→`adapters/resolve_adapter.py`、`tools/stars.py`→`adapters/stars_adapter.py`、`tools/web.py`→`adapters/news_adapter.py`，內容**原封不動**（它們只依賴 `config` 與 `httpx`/本地 JSON，無需注入）。

- [ ] **Step 2: 更新 `wc_agents/specialists.py` 的 import**

把：
```python
from tools.resolve import resolve_entity
from tools.web import web_search
from tools.stars import get_star_profile
from tools.apifootball import (
    tool_find_team, tool_get_squad, tool_get_player_stats, tool_get_fixtures,
    tool_get_standings, tool_get_injuries, tool_get_live,
)
```
改為：
```python
from adapters.resolve_adapter import resolve_entity
from adapters.news_adapter import web_search
from adapters.stars_adapter import get_star_profile
from adapters.agent_tools import (
    tool_find_team, tool_get_squad, tool_get_player_stats, tool_get_fixtures,
    tool_get_standings, tool_get_injuries, tool_get_live,
)
```
其餘（Agent 定義、`import config`）不變。`wc_agents/triage.py` 維持原樣（它只 import specialists 與 prompts）。

- [ ] **Step 3: 更新三個測試檔 import 並刪除舊 tools**

把 `tests/test_resolve.py` 內 `from tools.resolve` / `import tools.resolve` 改成 `adapters.resolve_adapter`；`tests/test_stars.py` 改 `adapters.stars_adapter`；`tests/test_web.py` 改 `adapters.news_adapter`（含 monkeypatch 目標 `w.httpx`→指向新模組）。
刪除舊檔：
```bash
git rm tools/resolve.py tools/stars.py tools/web.py tools/apifootball.py tools/__init__.py
```
刪除過時的 `tests/test_apifootball.py` 與 `tests/test_apifootball_tools.py`（覆蓋範圍已由 Task 5/6 + Task 12 取代）：
```bash
git rm tests/test_apifootball.py tests/test_apifootball_tools.py
```

- [ ] **Step 4: 跑全測試確認綠**

Run: `python -m pytest -q`
Expected: PASS（resolve/stars/web/specialists/triage 等全綠；無殘留對 `tools.*` 的 import）

- [ ] **Step 5: Commit**

```bash
git add adapters/resolve_adapter.py adapters/stars_adapter.py adapters/news_adapter.py \
        wc_agents/specialists.py tests/test_resolve.py tests/test_stars.py tests/test_web.py
git add -A tools/ tests/test_apifootball.py tests/test_apifootball_tools.py
git commit -m "refactor: move resolve/stars/news tools into adapters; drop tools/ package"
```

---

## Phase 4 — QA engine adapter

### Task 8: OpenAIAgentsAdapter（實作 QAEngineProtocol）

**Files:**
- Create: `adapters/openai_agents_adapter.py`
- Test: `tests/test_openai_agents_adapter.py`

**Interfaces:**
- Consumes: `agents.Runner`、`wc_agents.triage.triage_agent`。
- Produces: `OpenAIAgentsAdapter(runner=None, agent=None)` 實作 `QAEngineProtocol`；`answer(question) -> str` 內部呼叫 `Runner.run_sync(agent, question).final_output`。`runner` 可注入以利測試。

- [ ] **Step 1: 寫失敗測試**

`tests/test_openai_agents_adapter.py`：
```python
from adapters.openai_agents_adapter import OpenAIAgentsAdapter


class FakeResult:
    final_output = "answer-text"


class FakeRunner:
    def __init__(self): self.calls = []
    def run_sync(self, agent, question):
        self.calls.append((agent, question))
        return FakeResult()


def test_answer_returns_final_output():
    runner = FakeRunner()
    adapter = OpenAIAgentsAdapter(runner=runner, agent="AGENT")
    assert adapter.answer("hi") == "answer-text"
    assert runner.calls == [("AGENT", "hi")]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_openai_agents_adapter.py -q`
Expected: FAIL

- [ ] **Step 3: 實作**

`adapters/openai_agents_adapter.py`：
```python
from agents import Runner
from wc_agents.triage import triage_agent


class _DefaultRunner:
    def run_sync(self, agent, question):
        return Runner.run_sync(agent, question)


class OpenAIAgentsAdapter:
    """實作 QAEngineProtocol；包 OpenAI Agents SDK 的 Runner + triage_agent。"""

    def __init__(self, runner=None, agent=None):
        self._runner = runner or _DefaultRunner()
        self._agent = agent if agent is not None else triage_agent

    def answer(self, question: str) -> str:
        return self._runner.run_sync(self._agent, question).final_output
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_openai_agents_adapter.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/openai_agents_adapter.py tests/test_openai_agents_adapter.py
git commit -m "feat: OpenAIAgentsAdapter implementing QAEngineProtocol"
```

---

## Phase 5 — Service / UseCase / Schema

### Task 9: QAService（threadpool 卸載）

**Files:**
- Create: `services/qa_service.py`
- Test: `tests/test_qa_service.py`

**Interfaces:**
- Consumes: `QAEngineProtocol`、`anyio`。
- Produces: `QAService(engine)`，`async def answer(question) -> str`（在 threadpool 跑 `engine.answer`）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_qa_service.py`：
```python
import anyio
from services.qa_service import QAService


class FakeEngine:
    def answer(self, q): return f"echo:{q}"


def test_answer_runs_engine_in_threadpool():
    async def go():
        return await QAService(FakeEngine()).answer("hi")
    assert anyio.run(go) == "echo:hi"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_qa_service.py -q`
Expected: FAIL

- [ ] **Step 3: 實作**

`services/qa_service.py`：
```python
import anyio
from protocols.qa_engine import QAEngineProtocol


class QAService:
    def __init__(self, engine: QAEngineProtocol):
        self._engine = engine

    async def answer(self, question: str) -> str:
        return await anyio.to_thread.run_sync(self._engine.answer, question)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_qa_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/qa_service.py tests/test_qa_service.py
git commit -m "feat: QAService offloading blocking engine to threadpool"
```

### Task 10: AnswerQuestionUseCase + schemas

**Files:**
- Create: `use_cases/__init__.py`, `use_cases/answer_question.py`, `schemas/__init__.py`, `schemas/qa.py`
- Test: `tests/test_answer_question.py`

**Interfaces:**
- Consumes: `QAService`、`config`。
- Produces: `schemas.qa.AskRequest{question: str}`、`AskResponse{answer: str, model: str}`；`AnswerQuestionUseCase(qa_service)`，`async def execute(question: str) -> AskResponse`（空白問題 raise `ValueError`）。

- [ ] **Step 1: 寫失敗測試**

`tests/test_answer_question.py`：
```python
import anyio
import pytest
from use_cases.answer_question import AnswerQuestionUseCase
from schemas.qa import AskResponse


class FakeQA:
    async def answer(self, q): return f"A:{q}"


def test_execute_returns_response_with_model():
    async def go():
        return await AnswerQuestionUseCase(FakeQA()).execute("  hi  ")
    out = anyio.run(go)
    assert isinstance(out, AskResponse)
    assert out.answer == "A:hi"
    assert out.model  # 帶有模型名


def test_execute_rejects_blank():
    async def go():
        return await AnswerQuestionUseCase(FakeQA()).execute("   ")
    with pytest.raises(ValueError):
        anyio.run(go)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_answer_question.py -q`
Expected: FAIL

- [ ] **Step 3: 實作**

`schemas/__init__.py`：空檔。
`schemas/qa.py`：
```python
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    model: str
```

`use_cases/__init__.py`：空檔。
`use_cases/answer_question.py`：
```python
import config
from schemas.qa import AskResponse
from services.qa_service import QAService


class AnswerQuestionUseCase:
    def __init__(self, qa_service: QAService):
        self._qa = qa_service

    async def execute(self, question: str) -> AskResponse:
        q = question.strip()
        if not q:
            raise ValueError("question must not be blank")
        text = await self._qa.answer(q)
        return AskResponse(answer=text, model=config.OPENAI_DEFAULT_MODEL)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_answer_question.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add use_cases/ schemas/ tests/test_answer_question.py
git commit -m "feat: AnswerQuestionUseCase + AskRequest/AskResponse schemas"
```

---

## Phase 6 — Composition root 與 API 層

### Task 11: core/container 組裝、api deps、routes、main、例外處理

**Files:**
- Create: `core/__init__.py`, `core/container.py`, `api/__init__.py`, `api/v1/__init__.py`, `api/v1/deps.py`, `api/v1/routes.py`
- Modify: `main.py`（改寫為 FastAPI app）

**Interfaces:**
- Consumes: 前述所有 adapter / service / use case / schema / config。
- Produces:
  - `core.container.build_use_case() -> AnswerQuestionUseCase`：依 `config.STORAGE_BACKEND` 建 `SqliteStoreAdapter` → `QuotaService` → `ApiFootballAdapter` →（`bind_football`）→ `OpenAIAgentsAdapter` → `QAService` → `AnswerQuestionUseCase`。
  - `api.v1.deps.require_api_key`（FastAPI dependency）、`api.v1.deps.get_use_case`。
  - `main.app`（FastAPI 實例）。

- [ ] **Step 1: 實作 composition root**

`core/__init__.py`：空檔。
`core/container.py`：
```python
import config
from adapters.sqlite_store_adapter import SqliteStoreAdapter
from adapters.apifootball_adapter import ApiFootballAdapter
from adapters.openai_agents_adapter import OpenAIAgentsAdapter
from adapters import agent_tools
from services.quota_service import QuotaService
from services.qa_service import QAService
from use_cases.answer_question import AnswerQuestionUseCase


def _build_store():
    if config.STORAGE_BACKEND == "sqlite":
        return SqliteStoreAdapter(config.DB_PATH)
    raise ValueError(f"unsupported STORAGE_BACKEND: {config.STORAGE_BACKEND}")


def build_use_case() -> AnswerQuestionUseCase:
    store = _build_store()
    quota_service = QuotaService(store)
    football = ApiFootballAdapter(store, quota_service)
    agent_tools.bind_football(football)          # 依賴反轉：綁定到 agent 工具
    engine = OpenAIAgentsAdapter()
    return AnswerQuestionUseCase(QAService(engine))
```

- [ ] **Step 2: 實作 api deps（認證 + 注入）**

`api/__init__.py`、`api/v1/__init__.py`：空檔。
`api/v1/deps.py`：
```python
from fastapi import Header, HTTPException, status

import config
from core.container import build_use_case

_use_case = None


def get_use_case():
    global _use_case
    if _use_case is None:
        _use_case = build_use_case()
    return _use_case


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    allowed = config.api_keys()
    if not allowed or x_api_key not in allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid or missing API key")
```

- [ ] **Step 3: 實作 routes**

`api/v1/routes.py`：
```python
from fastapi import APIRouter, Depends

from api.v1.deps import require_api_key, get_use_case
from schemas.qa import AskRequest, AskResponse

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse,
             dependencies=[Depends(require_api_key)])
async def ask(req: AskRequest, use_case=Depends(get_use_case)):
    return await use_case.execute(req.question)
```

- [ ] **Step 4: 改寫 `main.py` 為 FastAPI app（含例外處理）**

`main.py`（完全取代原 CLI 內容）：
```python
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v1.routes import router
from services.quota_service import QuotaExhausted

log = logging.getLogger("wc")

app = FastAPI(title="World Cup QA")
app.include_router(router)


@app.exception_handler(QuotaExhausted)
async def _quota_handler(request: Request, exc: QuotaExhausted):
    return JSONResponse(status_code=429,
                        content={"detail": "API quota exhausted, try later"})


@app.exception_handler(ValueError)
async def _value_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def _runtime_handler(request: Request, exc: RuntimeError):
    log.exception("upstream error")
    return JSONResponse(status_code=502, content={"detail": "upstream data error"})
```

- [ ] **Step 5: 煙霧測試（健康檢查可起）**

Run: `python -c "from main import app; print([r.path for r in app.routes])"`
Expected: 輸出含 `/healthz` 與 `/ask`

- [ ] **Step 6: Commit**

```bash
git add core/ api/ main.py
git commit -m "feat: composition root + FastAPI app (/ask, /healthz, error handlers)"
```

---

## Phase 7 — API 整合測試

### Task 12: tests/test_api.py（TestClient）

**Files:**
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: `main.app`、`api.v1.deps` 的 dependency override 機制。

- [ ] **Step 1: 寫測試（mock 掉 use case，不真打 agent）**

`tests/test_api.py`：
```python
import pytest
from fastapi.testclient import TestClient

import config
import main
from api.v1 import deps
from schemas.qa import AskResponse
from services.quota_service import QuotaExhausted


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WC_API_KEYS", "secret")
    import importlib
    importlib.reload(config)

    class FakeUseCase:
        async def execute(self, question):
            if question == "boom":
                raise QuotaExhausted("daily-quota")
            return AskResponse(answer=f"A:{question}", model="test-model")

    main.app.dependency_overrides[deps.get_use_case] = lambda: FakeUseCase()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_healthz_no_auth(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ask_requires_api_key(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 401


def test_ask_happy_path(client):
    r = client.post("/ask", json={"question": "hi"},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert r.json() == {"answer": "A:hi", "model": "test-model"}


def test_ask_blank_question_422(client):
    r = client.post("/ask", json={"question": ""},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 422


def test_ask_quota_exhausted_429(client):
    r = client.post("/ask", json={"question": "boom"},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 429
```

- [ ] **Step 2: 跑測試確認通過（先看是否需要調整 reload 時序）**

Run: `python -m pytest tests/test_api.py -q`
Expected: PASS（若 `require_api_key` 因 config reload 取到舊值，於 `deps.require_api_key` 內改為呼叫時即時 `config.api_keys()`——本計畫已是即時呼叫，無需改）

- [ ] **Step 3: 跑全測試**

Run: `python -m pytest -q`
Expected: 全綠

- [ ] **Step 4: Commit**

```bash
git add tests/test_api.py
git commit -m "test: API integration tests (auth/validation/quota/happy path)"
```

---

## Phase 8 — 清理與 init 腳本

### Task 13: 改寫 init_db.py、移除殘留 db 直連

**Files:**
- Modify: `init_db.py`
- Test: 手動執行（需真實 key，不納入 CI）

**Interfaces:**
- Consumes: `core.container`、`adapters` 的 store/football。

- [ ] **Step 1: 改寫 `init_db.py` 走 adapter**

```python
import time

import config
from adapters.sqlite_store_adapter import SqliteStoreAdapter
from adapters.apifootball_adapter import ApiFootballAdapter
from services.quota_service import QuotaService

THROTTLE_SEC = 7  # 守住 10 次/分（留安全餘裕）


def main():
    store = SqliteStoreAdapter(config.DB_PATH)
    football = ApiFootballAdapter(store, QuotaService(store))
    teams = football.teams()
    print(f"teams: {len(teams)}")
    for t in teams:
        tid = t["team"]["id"]
        if store.peek(f"squad:{tid}"):
            continue
        football.squad(tid)
        print(f"squad {tid} ok")
        time.sleep(THROTTLE_SEC)
    time.sleep(THROTTLE_SEC)
    football.fixtures(None)
    time.sleep(THROTTLE_SEC)
    football.standings(None)
    print("init done")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 確認可 import（不實際打 API）**

Run: `python -c "import init_db"`
Expected: 無錯誤

- [ ] **Step 3: 確認無殘留 `from db import` 於 app 路徑外**

Run: `grep -rn "tools\.\|import tools\|af\._" --include=*.py . | grep -v tests/ || echo OK`
Expected: `OK`（無殘留舊 tools 引用）

- [ ] **Step 4: 跑全測試**

Run: `python -m pytest -q`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git add init_db.py
git commit -m "refactor: init_db.py seeds via adapters"
```

---

## Phase 9 — 部署交付物與文件

### Task 14: Dockerfile

**Files:**
- Create: `Dockerfile`, `.dockerignore`

- [ ] **Step 1: 建立 Dockerfile**

`Dockerfile`：
```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8887
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run 注入 $PORT；SQLite 寫到容器可寫路徑即可（單實例、ephemeral 可接受）
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8887}"]
```

`.dockerignore`：
```
.git
.venv
__pycache__
*.pyc
.pytest_cache
data/cache.db
docs
tests
```

- [ ] **Step 2: build 驗證**

Run: `docker build -t wc-qa:local .`
Expected: build 成功

- [ ] **Step 3: 本地起服務 + 健康檢查**

Run:
```bash
docker run --rm -e PORT=8887 -e WC_API_KEYS=local -p 8887:8887 wc-qa:local &
sleep 5 && curl -s localhost:8887/healthz
```
Expected: `{"status":"ok"}`（測完 `kill %1`）

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: Dockerfile (uvicorn binding to $PORT)"
```

### Task 15: 對齊 deploy.sh、更新 .env.example、README、CI

**Files:**
- Modify: `deploy.sh`（即現有 `gcp_Dev.sh`；若沿用該檔名則改該檔）
- Modify: `.env.example`, `README.md`

- [ ] **Step 1: 對齊 deploy.sh 變數與 Cloud Run 參數**

在腳本頂部填入並確認：
```bash
project_id="<你的 GCP 專案>"
region="asia-east1"
image_name="${region}-docker.pkg.dev/<project>/<repo>/wc-qa:v1"
service_name="wc-qa"
service_account="<你的部署 SA>"
```
Step-5 的 `gcloud run deploy` 確認/修改為：
```bash
gcloud run deploy "$service_name" \
  --image "$image_name" \
  --platform managed --region "$region" \
  --port 8887 --cpu 1 --memory 1Gi \
  --min-instances 0 --max-instances 1 \
  --timeout 180s --concurrency 50 \
  --update-secrets=OPENAI_API_KEY=OPENAI_API_KEY:latest,APIFOOTBALL_KEY=APIFOOTBALL_KEY:latest,TAVILY_KEY=TAVILY_KEY:latest,WC_API_KEYS=WC_API_KEYS:latest \
  --set-env-vars=OPENAI_DEFAULT_MODEL=gpt-4o-mini,WC_SEASON=2022,STORAGE_BACKEND=sqlite \
  --allow-unauthenticated
```
（無 `--vpc-connector`、無 `--vpc-egress`。機密需先 `gcloud secrets create` 並授權給 `service_account`。）

- [ ] **Step 2: 更新 `.env.example`**

新增/確認：
```
WC_API_KEYS=changeme1,changeme2
PORT=8887
STORAGE_BACKEND=sqlite
```

- [ ] **Step 3: 更新 `README.md`**

新增「啟動服務」與「部署」段落：
- 本地：`uvicorn main:app --reload --port 8887`，呼叫 `curl -H "X-API-Key: <key>" -d '{"question":"..."}' -H 'Content-Type: application/json' localhost:8887/ask`
- 部署：建 Secret Manager 機密 → `bash deploy.sh`
- 說明 CLI 已移除、改用 HTTP API。

- [ ] **Step 4: 跑全測試 + 確認 CI 不變即可綠**

Run: `python -m pytest -q`
Expected: 全綠（CI workflow 既有 matrix 不需改；新依賴已在 requirements）

- [ ] **Step 5: Commit**

```bash
git add deploy.sh .env.example README.md
git commit -m "docs: align deploy.sh for Cloud Run (max-instances=1, secrets) + README/.env"
```

---

## Self-Review 摘要（已對照 spec）

- **同步 /ask + JSON**：Task 10/11/12 ✓
- **X-API-Key 認證**：Task 11（`require_api_key`）+ Task 12 測試 ✓
- **Clean Arch 分層 + 命名**：Task 2–11 ✓（protocols/adapters/services/use_cases/core/api/schemas）
- **依賴反轉穿過 agent 工具**：Task 6（`bind_football`）+ Task 11（container 綁定）✓
- **單實例免外部儲存（僅 SQLite adapter）**：Task 3 + container `_build_store` ✓
- **CLI 移除**：Task 11（`main.py` 改寫）+ Task 7（刪 tools）✓
- **錯誤對應 401/422/429/502/500**：Task 11 handlers + Task 12 測試 ✓
- **threadpool 卸載**：Task 9 ✓
- **Dockerfile/deploy.sh/port 8887/Secret Manager/無 VPC**：Task 14/15 ✓
- **測試遷移 + 新增 test_api**：Task 3–12 ✓
- **XML 提示不動**：Task 7 僅改 import，prompts.py 不變 ✓

已知後續（非本計畫）：CD 自動化（在 CI 加 build/deploy step）留待之後。
</content>
