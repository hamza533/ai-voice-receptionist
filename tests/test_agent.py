"""The agent is thin: its tool list must match the API's tools exactly."""

from __future__ import annotations

import pytest

pytest.importorskip("livekit.agents")


def test_agent_tools_match_api_tools() -> None:
    from livekit.agents.llm import ToolContext as LKToolContext

    from agent.main import CallState, Receptionist
    from app.services.tools import TOOLS

    agent = Receptionist("test", api=None, state=CallState("c"), ctx=None)  # type: ignore[arg-type]
    names = set(LKToolContext(agent.tools).function_tools)
    assert names - {"end_call"} == set(TOOLS)


def test_tool_result_hides_internal_fields() -> None:
    import json

    from agent.main import _result

    out = json.loads(_result({"status": "ok", "message": "Say hi", "data": {"x": 1}}))
    assert out == {"status": "ok", "instruction": "Say hi", "data": {"x": 1}}
