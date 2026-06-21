from agents import Agent          # OpenAI Agents SDK
from wc_agents import prompts     # 本地 prompt 模組
import config
from adapters.resolve_adapter import resolve_entity
from adapters.news_adapter import web_search
from adapters.stars_adapter import get_star_profile
from adapters.agent_tools import (
    tool_find_team, tool_get_squad, tool_get_player_stats, tool_get_fixtures,
    tool_get_standings, tool_get_injuries, tool_get_live,
)

_MODEL = config.OPENAI_DEFAULT_MODEL

squad_agent = Agent(
    name="Squad", instructions=prompts.SQUAD, model=_MODEL,
    tools=[resolve_entity, tool_find_team, tool_get_squad, tool_get_player_stats])

fixture_agent = Agent(
    name="Fixture", instructions=prompts.FIXTURE, model=_MODEL,
    tools=[resolve_entity, tool_find_team, tool_get_fixtures,
           tool_get_standings, tool_get_live])

star_agent = Agent(
    name="Star", instructions=prompts.STAR, model=_MODEL,
    tools=[resolve_entity, tool_find_team, get_star_profile,
           tool_get_player_stats, web_search])

insight_agent = Agent(
    name="Insight", instructions=prompts.INSIGHT, model=_MODEL,
    tools=[resolve_entity, tool_find_team, tool_get_injuries, web_search])
