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
