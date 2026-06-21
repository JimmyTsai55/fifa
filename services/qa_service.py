import anyio
from protocols.qa_engine import QAEngineProtocol


class QAService:
    def __init__(self, engine: QAEngineProtocol):
        self._engine = engine

    async def answer(self, question: str) -> str:
        return await anyio.to_thread.run_sync(self._engine.answer, question)
