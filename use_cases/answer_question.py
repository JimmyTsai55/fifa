import config
from schemas.qa import AskResponse
from services.qa_service import QAService


class AnswerQuestionUseCase:
    def __init__(self, qa_service: QAService):
        self._qa = qa_service

    async def execute(self, question: str) -> AskResponse:
        q = question.strip()
        if not q:
            raise ValueError("question must not be blank")
        text = await self._qa.answer(q)
        return AskResponse(answer=text, model=config.OPENAI_DEFAULT_MODEL)
