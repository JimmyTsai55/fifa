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
