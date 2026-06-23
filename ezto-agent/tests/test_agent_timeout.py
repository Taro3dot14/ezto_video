"""Agent timeout and verify messaging."""

from harness.agent.loop import format_agent_timeout_message


def test_timeout_filters_thinking_snippet():
    msg = format_agent_timeout_message(
        "verify",
        50,
        "Now let me run both checks:",
    )
    assert "Now let me" not in msg
    assert "验收检查" in msg
    assert "50" in msg


def test_timeout_keeps_real_error_snippet():
    msg = format_agent_timeout_message(
        "builder",
        25,
        "TypeScript error TS2322 in index.tsx line 42",
    )
    assert "TS2322" in msg
    assert "构建" in msg
