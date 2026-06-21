import json
from agents import function_tool          # OpenAI Agents SDK
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
