import httpx
from agents import function_tool          # OpenAI Agents SDK
import config


def search(query: str, domains: list[str] | None = None) -> list[dict]:
    payload = {
        "api_key": config.TAVILY_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_domains": domains or config.NEWS_DOMAINS,
    }
    r = httpx.post(
        "https://api.tavily.com/search", json=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {config.TAVILY_KEY}"})
    data = r.json()
    return [{"title": x["title"], "url": x["url"], "content": x["content"]}
            for x in data.get("results", [])]


@function_tool
def web_search(query: str) -> list:
    """搜尋英文足球新聞（限 BBC/ESPN/The Athletic/Goal/FIFA），回標題+連結+摘要。"""
    return search(query)
