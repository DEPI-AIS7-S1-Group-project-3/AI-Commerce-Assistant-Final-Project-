from ai_commerce_marketplace.agents.shopping.tools import ToolContext, call_tool


def _ctx() -> ToolContext:
    return ToolContext(session=None)  # type: ignore[arg-type]


def test_unknown_tool_is_rejected():
    result = call_tool(_ctx(), "does_not_exist", {})
    assert result["ok"] is False
    assert result["error"] == "unknown_tool"