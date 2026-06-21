import anyio
import pytest
from use_cases.answer_question import AnswerQuestionUseCase
from schemas.qa import AskResponse


class FakeQA:
    async def answer(self, q): return f"A:{q}"


def test_execute_returns_response_with_model():
    async def go():
        return await AnswerQuestionUseCase(FakeQA()).execute("  hi  ")
    out = anyio.run(go)
    assert isinstance(out, AskResponse)
    assert out.answer == "A:hi"
    assert out.model  # 帶有模型名


def test_execute_rejects_blank():
    async def go():
        return await AnswerQuestionUseCase(FakeQA()).execute("   ")
    with pytest.raises(ValueError):
        anyio.run(go)
