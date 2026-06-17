import httpx
from agents import function_tool          # OpenAI Agents SDK
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
    secs = (86400 - (now.hour * 3600 + now.minute * 60 + now.second))
    conn = get_conn()
    ttl = live_ttl(secs, max(1, quota.remaining(conn, _today()) - 20))
    return _cached("live", ttl, "/fixtures", {"live": "all"})


# 測試別名（純函式直呼）
get_squad = _squad


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
