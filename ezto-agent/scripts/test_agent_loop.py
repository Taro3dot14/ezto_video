"""Direct test for harness/agent/loop.py — mock unit + optional live LLM smoke."""

from __future__ import annotations

import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

# scripts/ → ezto-agent/
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from backend.core.llm import ChatResult, ToolCall  # noqa: E402
from configs import settings  # noqa: E402
from harness.agent.loop import (  # noqa: E402
    AgentResult,
    AgentTool,
    WebBuildAgent,
    _run_loop,
    _trim_messages,
)


def _minimal_state(ws: Path) -> dict:
    return {
        "thread_id": str(uuid.uuid4()),
        "workspace_root": str(ws),
        "thinking_log": [],
        "execution_trace": [],
        "execution_revision": 0,
        "artifact_paths": {
            "script.md": str(ws / "script.md"),
            "outline.md": str(ws / "outline.md"),
            "presentation": str(ws / "presentation"),
        },
        "loaded_refs": ["CHAPTER-CRAFT.md"],
    }


def _seed_workspace(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "outline.md").write_text(
        "## 1. coldopen — 痛点与钩子 (3 steps)\n\n"
        "- Step 0: 大数字 3.8s\n"
        "- Step 1: 对比 1.2s\n"
        "- Step 2: 案例卡片\n",
        encoding="utf-8",
    )
    (ws / "script.md").write_text(
        "开场：3.8 秒这个数字代表什么？\n---\n"
        "对比：Server Components 把它压到 1.2 秒。\n---\n"
        "案例：Shopify、Twill、Uniqlo 的真实迁移数据。\n",
        encoding="utf-8",
    )
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True, exist_ok=True)
    (ch / "index.tsx").write_text("// placeholder\n", encoding="utf-8")
    (ch / "index.css").write_text("/* placeholder */\n", encoding="utf-8")


def test_trim_messages():
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}]
    for i in range(13):
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"tc{i}",
                "type": "function",
                "function": {"name": "read_file", "arguments": "{}"},
            }],
            "reasoning_content": "think",
        })
        msgs.append({"role": "tool", "tool_call_id": f"tc{i}", "content": "ok"})
    trimmed = _trim_messages(msgs)
    assert trimmed[0]["role"] == "system"
    assert any("truncated" in str(m.get("content") or "") for m in trimmed)
    # No orphan tool messages
    for idx, m in enumerate(trimmed):
        if m["role"] == "tool":
            assert trimmed[idx - 1]["role"] == "assistant"
            assert trimmed[idx - 1].get("tool_calls")
    print("  trim_messages: OK")


def test_sanitize_orphan_tool():
    from harness.agent.loop import _sanitize_tool_chains

    bad = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "tool", "tool_call_id": "x", "content": "orphan"},
    ]
    fixed = _sanitize_tool_chains(bad)
    assert all(m["role"] != "tool" for m in fixed)
    print("  sanitize_orphan_tool: OK")


def test_run_loop_mock_native():
    """Mock chat_with_tools → echo then done."""
    tools = [
        AgentTool(
            name="echo",
            description="Echo a message",
            input_schema={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            fn=lambda msg: f"echoed: {msg}",
        ),
        AgentTool(
            name="done",
            description="Finish",
            input_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
            fn=lambda summary: f"[DONE] {summary}",
        ),
    ]
    sequence = [
        ChatResult(
            content="calling echo",
            tool_calls=[ToolCall(id="tc1", name="echo", arguments={"msg": "hello"})],
        ),
        ChatResult(
            content="finishing",
            tool_calls=[ToolCall(id="tc2", name="done", arguments={"summary": "all good"})],
        ),
    ]

    with patch("harness.agent.loop.settings.agent_use_native_tools", True):
        with patch("harness.agent.loop.llm.chat_with_tools", side_effect=sequence):
            result = _run_loop(
                tools=tools,
                system_prompt="test system",
                user_prompt="test user",
                max_iterations=5,
            )

    assert isinstance(result, AgentResult)
    assert result.success, f"expected success, got {result}"
    assert result.tool_calls == 1
    assert result.iterations == 2
    assert "all good" in result.content
    print(f"  run_loop mock native: OK (iterations={result.iterations}, tools={result.tool_calls})")


def test_run_loop_mock_no_tool_retry():
    """Empty tool_calls → loop retries then succeeds."""
    tools = [
        AgentTool(
            name="done",
            description="Finish",
            input_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
            fn=lambda summary: f"[DONE] {summary}",
        ),
    ]
    sequence = [
        ChatResult(content="oops no tools", tool_calls=[]),
        ChatResult(
            content="",
            tool_calls=[ToolCall(id="tc1", name="done", arguments={"summary": "recovered"})],
        ),
    ]

    with patch("harness.agent.loop.settings.agent_use_native_tools", True):
        with patch("harness.agent.loop.llm.chat_with_tools", side_effect=sequence):
            result = _run_loop(
                tools=tools,
                system_prompt="sys",
                user_prompt="user",
                max_iterations=5,
            )

    assert result.success
    assert result.iterations == 2
    print("  run_loop no-tool retry: OK")


def test_web_build_agent_mock():
    """WebBuildAgent with mocked LLM: todolist_status → write_narrations → done blocked."""
    ws = Path(tempfile.mkdtemp(prefix="ezto-loop-"))
    try:
        _seed_workspace(ws)
        state = _minimal_state(ws)

        narrations = ["开场白", "对比", "案例"]
        sequence = [
            ChatResult(
                content="check todos",
                tool_calls=[ToolCall(id="t1", name="todolist_status", arguments={})],
            ),
            ChatResult(
                content="write narrations",
                tool_calls=[ToolCall(
                    id="t2",
                    name="write_narrations",
                    arguments={"chapter_id": "chapter_1", "lines": narrations},
                )],
            ),
            ChatResult(
                content="try done early",
                tool_calls=[ToolCall(id="t3", name="done", arguments={"summary": "partial"})],
            ),
            ChatResult(
                content="",
                tool_calls=[ToolCall(id="t4", name="todolist_status", arguments={})],
            ),
        ]

        with patch("harness.agent.loop.settings.agent_use_native_tools", True):
            with patch("harness.agent.loop.settings.web_build_agent_max_iterations", 4):
                with patch("harness.agent.loop.llm.chat_with_tools", side_effect=sequence):
                    agent = WebBuildAgent(state)
                    result = agent.run(
                        chapter_id="chapter_1",
                        title="痛点与钩子",
                        chapter_index=1,
                        total_chapters=1,
                    )

        narr_path = ws / "presentation" / "src" / "chapters" / "chapter_1" / "narrations.ts"
        assert narr_path.exists(), "write_narrations should create narrations.ts"
        text = narr_path.read_text(encoding="utf-8")
        assert "开场白" in text

        assert result.success is False  # max iterations, done blocked by verify
        assert result.tool_calls >= 2
        print(
            f"  WebBuildAgent mock: OK (tools={result.tool_calls})"
        )
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_web_build_agent_live():
    """Live LLM: first round should call a tool (usually todolist_status or write_narrations)."""
    if not settings.deepseek_api_key:
        print("  WebBuildAgent live: SKIP (no DEEPSEEK_API_KEY)")
        return

    ws = Path(tempfile.mkdtemp(prefix="ezto-loop-live-"))
    try:
        _seed_workspace(ws)
        state = _minimal_state(ws)

        with patch("harness.agent.loop.settings.agent_use_native_tools", True):
            with patch("harness.agent.loop.settings.web_build_agent_max_iterations", 2):
                agent = WebBuildAgent(state)
                result = agent.run(
                    chapter_id="chapter_1",
                    title="痛点与钩子",
                    chapter_index=1,
                    total_chapters=1,
                )

        assert result.tool_calls >= 1, "live run should execute at least one tool"
        print(
            f"  WebBuildAgent live: OK (iterations={result.iterations}, "
            f"tools={result.tool_calls}, success={result.success})"
        )
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def main() -> int:
    print("=== loop.py direct tests ===\n")
    tests = [
        test_trim_messages,
        test_sanitize_orphan_tool,
        test_run_loop_mock_native,
        test_run_loop_mock_no_tool_retry,
        test_web_build_agent_mock,
        test_web_build_agent_live,
    ]
    failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            fn()
        except Exception as e:
            print(f"  {name}: FAIL — {e}")
            failed += 1

    print()
    if failed:
        print(f"FAIL: {failed}/{len(tests)} tests failed")
        return 1
    print(f"PASS: all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
