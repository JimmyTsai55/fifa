from agents import Agent          # OpenAI Agents SDK
from wc_agents import prompts
from wc_agents.specialists import (
    squad_agent, fixture_agent, star_agent, insight_agent)

triage_agent = Agent(
    name="Triage",
    instructions=prompts.TRIAGE,
    handoffs=[squad_agent, fixture_agent, star_agent, insight_agent],
)
