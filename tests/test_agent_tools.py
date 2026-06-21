import asyncio
import pytest
from unittest.mock import MagicMock

import adapters.agent_tools as at
from agents.tool import FunctionTool, resolve_function_tool_failure_error_function
from services.quota_service import QuotaExhausted


class FakePort:
    def find_team_id(self, name): return 7 if name == "Brazil" else None
    def squad(self, tid): return [{"tid": tid}]
    def player_stats(self, tid): return []
    def fixtures(self, tid=None): return [{"f": tid}]
    def standings(self, group=None): return [{"s": 1}]
    def injuries(self, tid): return []
    def live(self): return [{"live": 1}]


class ErrorPort:
    """Port that raises QuotaExhausted or RuntimeError to simulate quota/API failures."""
    def find_team_id(self, name): raise QuotaExhausted("quota gone")
    def squad(self, tid): raise RuntimeError("API errors: 429")
    def player_stats(self, tid): raise QuotaExhausted("quota gone")
    def fixtures(self, tid=None): raise QuotaExhausted("quota gone")
    def standings(self, group=None): raise QuotaExhausted("quota gone")
    def injuries(self, tid): raise QuotaExhausted("quota gone")
    def live(self): raise QuotaExhausted("quota gone")


def test_current_football_raises_when_unbound():
    at._football = None
    with pytest.raises(RuntimeError):
        at.current_football()


def test_bind_and_lookup():
    at.bind_football(FakePort())
    assert at.current_football().find_team_id("Brazil") == 7


# ---------------------------------------------------------------------------
# FIX 1: Verify all football tools are configured to re-raise on exception
# ---------------------------------------------------------------------------

_FOOTBALL_TOOLS = [
    at.tool_find_team,
    at.tool_get_squad,
    at.tool_get_player_stats,
    at.tool_get_fixtures,
    at.tool_get_standings,
    at.tool_get_injuries,
    at.tool_get_live,
]


@pytest.mark.parametrize("tool", _FOOTBALL_TOOLS, ids=lambda t: t.name)
def test_football_tool_configured_to_reraise(tool):
    """Each football tool must have failure_error_function=None so the SDK re-raises
    exceptions (QuotaExhausted→429, RuntimeError→502) instead of swallowing them.

    This checks _use_default_failure_error_function=False and that
    resolve_function_tool_failure_error_function returns None — the SDK path that
    causes _FailureHandlingFunctionToolInvoker to `raise` rather than return a string.

    LIMITATION: This test cannot cover the LLM-driven end-to-end path (Runner.run_sync
    deciding to call a tool) because that requires a live OpenAI API key. It verifies
    the configuration attribute that controls the SDK re-raise behaviour.
    """
    assert isinstance(tool, FunctionTool)
    assert not tool._use_default_failure_error_function, (
        f"{tool.name}: _use_default_failure_error_function should be False"
    )
    resolved = resolve_function_tool_failure_error_function(tool)
    assert resolved is None, (
        f"{tool.name}: failure_error_function must resolve to None to enable re-raise; got {resolved}"
    )


def _make_tool_context(tool_name: str):
    """Build a minimal mock ToolContext sufficient for on_invoke_tool invocation."""
    ctx = MagicMock()
    ctx.tool_name = tool_name
    ctx.run_config = None
    return ctx


@pytest.mark.parametrize("tool,args_json,exc_type", [
    (at.tool_find_team, '{"name": "Brazil"}', QuotaExhausted),
    (at.tool_get_squad, '{"team_id": 1}', RuntimeError),
    (at.tool_get_standings, '{}', QuotaExhausted),
], ids=["tool_find_team", "tool_get_squad", "tool_get_standings"])
def test_football_tool_reraises_on_exception(tool, args_json, exc_type):
    """Directly invoke on_invoke_tool (the SDK's async callable) with an error-raising port
    and assert the exception propagates — i.e. is NOT swallowed and returned as a string.

    This exercises the _FailureHandlingFunctionToolInvoker.__call__ path:
      exception raised → maybe_invoke_function_tool_failure_error_function returns None
      → `raise` re-raises the original exception.

    LIMITATION: The full path (LLM picks tool → Runner.run_sync → handler → HTTP status)
    requires a live API key and is not feasible in CI.
    """
    at.bind_football(ErrorPort())
    ctx = _make_tool_context(tool.name)
    with pytest.raises(exc_type):
        asyncio.run(tool.on_invoke_tool(ctx, args_json))
