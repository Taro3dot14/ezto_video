"""Tests for structured tool results and chapter session state."""

from harness.agent.tools import ChapterSessionState, ToolErrorCode, ToolResult, make_build_agent_tools


def test_tool_result_blocked_for_llm():
    r = ToolResult.blocked("call read_chapter_context() first")
    text = r.for_llm()
    assert "POLICY BLOCKED" in text
    assert "read_chapter_context" in text
    assert r.code == ToolErrorCode.BLOCKED
    assert not r.ok


def test_tool_result_from_handler_done():
    r = ToolResult.from_handler_output("[DONE] built chapter", tool_name="done")
    assert r.done
    assert r.message == "built chapter"


def test_tool_result_from_handler_blocked_string():
    r = ToolResult.from_handler_output(
        "❌ BLOCKED: builder cannot typecheck",
        tool_name="typecheck",
    )
    assert r.code == ToolErrorCode.BLOCKED


def test_chapter_session_record_tool_success():
    session = ChapterSessionState.for_chapter(
        chapter_id="hook",
        chapter_index=1,
        tool_profile="builder",
        workflow_state={},
    )
    assert not session.chapter_context_read
    session.record_tool_success("read_chapter_context", {})
    assert session.chapter_context_read

    session.record_tool_success(
        "write_file",
        {"path": "presentation/src/chapters/hook/index.tsx"},
    )
    assert session.index_tsx_written
    assert not session.narrations_written

    session.record_tool_success("write_narrations", {"chapter_id": "hook"})
    assert session.narrations_written


def test_write_narrations_blocked_without_context(tmp_path):
    """Regression: write_narrations must enforce read_chapter_context guard."""
    state = {"workspace_root": str(tmp_path)}
    ch = tmp_path / "presentation" / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    tools, _session = make_build_agent_tools(state, chapter_id="hook", tool_profile="builder")
    write_tool = next(t for t in tools if t.name == "write_narrations")
    result = write_tool.fn(chapter_id="hook", lines=["line one"])
    assert result.code == ToolErrorCode.BLOCKED
    assert "read_chapter_context" in result.message


def test_chapter_session_apply_tool_outcome_skips_failed():
    session = ChapterSessionState.for_chapter(
        chapter_id="hook",
        chapter_index=1,
        tool_profile="builder",
        workflow_state={},
    )
    failed = ToolResult.success("❌ lines must be a non-empty array")
    session.apply_tool_outcome(failed, "write_narrations", {})
    assert not session.narrations_written

    ok = ToolResult.success("Written narrations.ts")
    session.apply_tool_outcome(ok, "write_narrations", {"chapter_id": "hook"})
    assert session.narrations_written


def test_chapter_session_dict_compat():
    session = ChapterSessionState({"review_ok": True, "craft_review": {"items": {}}})
    assert session["review_ok"] is True
    assert session.get("craft_review") == {"items": {}}
    session["typecheck_ok"] = True
    assert session.typecheck_ok


def test_push_tool_audit_appends_event():
    from harness.agent.tools.audit import push_tool_audit
    from harness.agent.tools.result import ToolErrorCode, ToolExecutionRecord

    state: dict = {"execution_trace": [{"id": "x:0", "status": "running", "events": []}]}
    rec = ToolExecutionRecord(
        tool_name="write_file",
        code=ToolErrorCode.BLOCKED,
        duration_ms=1.2,
        output_chars=40,
        blocked=True,
        done=False,
        args_summary={"path": "a.tsx"},
    )
    push_tool_audit(state, rec, agent="builder")
    events = state["execution_trace"][0]["events"]
    assert len(events) == 1
    assert events[0]["type"] == "tool"
    assert '"blocked": true' in events[0]["content"]
    assert events[0]["agent"] == "builder"
