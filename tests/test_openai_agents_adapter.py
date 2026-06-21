from adapters.openai_agents_adapter import OpenAIAgentsAdapter


class FakeResult:
    final_output = "answer-text"


class FakeRunner:
    def __init__(self): self.calls = []
    def run_sync(self, agent, question):
        self.calls.append((agent, question))
        return FakeResult()


def test_answer_returns_final_output():
    runner = FakeRunner()
    adapter = OpenAIAgentsAdapter(runner=runner, agent="AGENT")
    assert adapter.answer("hi") == "answer-text"
    assert runner.calls == [("AGENT", "hi")]
