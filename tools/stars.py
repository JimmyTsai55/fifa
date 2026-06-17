import json
import os
from agents import function_tool          # OpenAI Agents SDK
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
