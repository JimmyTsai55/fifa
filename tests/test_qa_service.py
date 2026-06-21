import anyio
from services.qa_service import QAService


class FakeEngine:
    def answer(self, q): return f"echo:{q}"


def test_answer_runs_engine_in_threadpool():
    async def go():
        return await QAService(FakeEngine()).answer("hi")
    assert anyio.run(go) == "echo:hi"
