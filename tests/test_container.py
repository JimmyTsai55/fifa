import config
import core.container as container


def test_build_use_case_wires_openai_key_into_sdk(tmp_path, monkeypatch):
    """config 透過 pydantic-settings 讀 .env 但不 export 到 os.environ；
    OpenAI Agents SDK 只讀 os.environ，故 build_use_case 必須把金鑰明確餵給 SDK。
    回歸測試：移除這段 wiring 會讓 .env-only 的本機啟動在第一次 /ask 時 500。"""
    calls = []
    monkeypatch.setattr(container, "set_default_openai_key", lambda k: calls.append(k))
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")

    container.build_use_case()

    assert calls == ["sk-test-123"]


def test_build_use_case_skips_key_when_unset(tmp_path, monkeypatch):
    """金鑰為空時不呼叫 set_default_openai_key（避免用空字串覆蓋真環境變數設定）。"""
    calls = []
    monkeypatch.setattr(container, "set_default_openai_key", lambda k: calls.append(k))
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")

    container.build_use_case()

    assert calls == []
