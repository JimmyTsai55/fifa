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


# failure_error_function=None disables the SDK's default error-swallowing behaviour:
# when a tool raises (e.g. QuotaExhausted or RuntimeError("API errors: ...")), the SDK
# calls resolve_function_tool_failure_error_function → returns None → re-raises the
# exception so it propagates through Runner.run_sync to our FastAPI handlers, which
# map QuotaExhausted→429 and RuntimeError→502.
@function_tool(failure_error_function=None)
def tool_find_team(name: str) -> int:
    """把球隊的拉丁名稱（resolve_entity 的 canonical_name）轉成 team_id；查無回 0。"""
    return current_football().find_team_id(name) or 0


@function_tool(failure_error_function=None)
def tool_get_squad(team_id: int) -> list:
    """取得某隊（team_id）的世界盃陣容名單。"""
    return current_football().squad(team_id)


@function_tool(failure_error_function=None)
def tool_get_player_stats(team_id: int) -> list:
    """取得某隊球員的賽季數據（含年齡、進球、出場）。"""
    return current_football().player_stats(team_id)


@function_tool(failure_error_function=None)
def tool_get_fixtures(team_id: int = 0) -> list:
    """取得賽程；team_id=0 表示全部賽程。"""
    return current_football().fixtures(team_id or None)


@function_tool(failure_error_function=None)
def tool_get_standings() -> list:
    """取得世界盃分組排名。"""
    return current_football().standings()


@function_tool(failure_error_function=None)
def tool_get_injuries(team_id: int) -> list:
    """取得某隊傷兵名單（事實型困難點）。"""
    return current_football().injuries(team_id)


@function_tool(failure_error_function=None)
def tool_get_live() -> list:
    """取得目前所有進行中比賽的即時比分（自適應更新間隔）。"""
    return current_football().live()
