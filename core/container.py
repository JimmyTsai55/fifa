import config
from adapters.sqlite_store_adapter import SqliteStoreAdapter
from adapters.apifootball_adapter import ApiFootballAdapter
from adapters.openai_agents_adapter import OpenAIAgentsAdapter
from adapters import agent_tools
from services.quota_service import QuotaService
from services.qa_service import QAService
from use_cases.answer_question import AnswerQuestionUseCase


def _build_store():
    if config.STORAGE_BACKEND == "sqlite":
        return SqliteStoreAdapter(config.DB_PATH)
    raise ValueError(f"unsupported STORAGE_BACKEND: {config.STORAGE_BACKEND}")


def build_use_case() -> AnswerQuestionUseCase:
    store = _build_store()
    quota_service = QuotaService(store)
    football = ApiFootballAdapter(store, quota_service)
    agent_tools.bind_football(football)          # 依賴反轉：綁定到 agent 工具
    engine = OpenAIAgentsAdapter()
    return AnswerQuestionUseCase(QAService(engine))
