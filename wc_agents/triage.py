from agents import Agent          # OpenAI Agents SDK
from wc_agents import prompts
import config
from wc_agents.specialists import (
    squad_agent, fixture_agent, star_agent, insight_agent)

triage_agent = Agent(
    name="Triage",
    instructions=prompts.TRIAGE,
    model=config.OPENAI_DEFAULT_MODEL,
    handoffs=[squad_agent, fixture_agent, star_agent, insight_agent],
)
