from typing import Protocol


class QAEngineProtocol(Protocol):
    def answer(self, question: str) -> str: ...
