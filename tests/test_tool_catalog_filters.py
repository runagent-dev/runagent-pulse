from server.tools import list_tools_for, list_tools


def test_list_tools_http_contains_schedule():
    names = [t.name for t in list_tools_for("http")]
    assert "schedule_task" in names


def test_list_tools_mcp_contains_schedule():
    names = [t.name for t in list_tools_for("mcp")]
    assert "schedule_task" in names


def test_list_tools_framework_filter():
    names = [t.name for t in list_tools_for("framework", framework="langgraph")]
    assert "schedule_task" in names
    assert "cancel_task" in names


def test_list_tools_matches_meta():
    http_tools = list_tools_for("http")
    assert len(list_tools()) >= len(http_tools)

