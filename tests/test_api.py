import pytest
from fastapi.testclient import TestClient

import config
import main
from api.v1 import deps
from schemas.qa import AskResponse
from services.quota_service import QuotaExhausted


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WC_API_KEYS", "secret")
    import importlib
    importlib.reload(config)

    class FakeUseCase:
        async def execute(self, question):
            if question == "boom":
                raise QuotaExhausted("daily-quota")
            return AskResponse(answer=f"A:{question}", model="test-model")

    main.app.dependency_overrides[deps.get_use_case] = lambda: FakeUseCase()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_healthz_no_auth(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ask_requires_api_key(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 401


def test_ask_happy_path(client):
    r = client.post("/ask", json={"question": "hi"},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert r.json() == {"answer": "A:hi", "model": "test-model"}


def test_ask_blank_question_422(client):
    r = client.post("/ask", json={"question": ""},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 422


def test_ask_quota_exhausted_429(client):
    r = client.post("/ask", json={"question": "boom"},
                    headers={"X-API-Key": "secret"})
    assert r.status_code == 429
