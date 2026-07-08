"""Tests for chapter build mode orchestration."""

from unittest.mock import MagicMock, patch

from harness.agent.chapter_build import chapter_build_mode_label, run_chapter_pipeline
from harness.agent.loop import AgentResult
from harness.agent.tools import make_build_agent_tools


def test_tool_profile_builder_blocks_craft_review_check(tmp_path):
    state = {"workspace_root": str(tmp_path)}
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    (ch / "narrations.ts").write_text('export const narrations = ["a"];\n')
    (ch / "index.tsx").write_text("export default function X() { return null; }\n")

    tools, ctx = make_build_agent_tools(state, chapter_id="chapter_1", tool_profile="builder")
    names = {t.name for t in tools}
    assert "craft_review_check" not in names
    assert "read_file" not in names
    assert "read_chapter_context" in names
    assert "craft_auto_check" in names

    from harness.workflow.chapter_policies import check_tool_guard

    msg = check_tool_guard("craft_review_check", {"item": "X"}, ppt=ppt, chapter_id="chapter_1", ctx=ctx)
    assert msg and "BLOCKED" in msg


def test_tool_profile_reviewer_blocks_write(tmp_path):
    state = {"workspace_root": str(tmp_path)}
    ppt = tmp_path / "presentation"
    ppt.mkdir(parents=True)
    _, ctx = make_build_agent_tools(state, chapter_id="chapter_1", tool_profile="reviewer")
    from harness.workflow.chapter_policies import check_tool_guard

    msg = check_tool_guard(
        "write_file", {"path": "presentation/src/chapters/chapter_1/index.tsx"},
        ppt=ppt, chapter_id="chapter_1", ctx=ctx,
    )
    assert msg and "read-only" in msg


def test_builder_cannot_todolist_check_craft_items(tmp_path):
    state = {"workspace_root": str(tmp_path)}
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    (ch / "narrations.ts").write_text('export const narrations = ["a"];\n')
    (ch / "index.tsx").write_text("export default function X() { return null; }\n")

    _, ctx = make_build_agent_tools(state, chapter_id="chapter_1", tool_profile="builder")
    from harness.workflow.chapter_policies import check_tool_guard

    msg = check_tool_guard(
        "todolist_check", {"item": "VISUAL_DEMOS"},
        ppt=ppt, chapter_id="chapter_1", ctx=ctx,
    )
    assert msg and "Reviewer" in msg


def test_reviewer_todolist_craft_items(tmp_path):
    from harness.services.tools.craft.craft_review import (
        init_craft_checklist,
        run_craft_auto_checks,
        try_check_craft_todo_item,
    )

    ws = tmp_path
    ppt = ws / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    reg = ppt / "src" / "registry"
    ch.mkdir(parents=True)
    reg.mkdir(parents=True)
    (ch / "narrations.ts").write_text('export const narrations = [\n  "a",\n  "b",\n];\n', encoding="utf-8")
    (ch / "index.tsx").write_text(
        "import MaskReveal from '../../components/MaskReveal';\n"
        'export default function X({ step }) {\n'
        '  if (step === 0) return <div className="hk-title"/>;\n'
        '  if (step === 1) return <div className="hk-body"><MaskReveal/></div>;\n'
        '}\n',
        encoding="utf-8",
    )
    (ch / "index.css").write_text(
        ".hk-title { font-size: 100px; font-weight: 800; width: 60%; animation: hk-in 1s; }\n"
        ".hk-body { font-size: 40px; font-weight: 500; }\n"
        "@keyframes hk-in { from { opacity: 0; } }\n",
        encoding="utf-8",
    )
    (reg / "chapters.ts").write_text(
        "import chapter_1 from '../chapters/chapter_1';\n"
        "export const CHAPTERS = [{ id: 'chapter_1', title: 'T' }];\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert try_check_craft_todo_item(ctx, "REVIEW_BUNDLE") == ""
    assert try_check_craft_todo_item(ctx, "VISUAL_DEMOS", result="pass") == ""


def test_chapter_build_mode_labels():
    assert chapter_build_mode_label("sub_agent") == "Sub Agent 模式"
    assert chapter_build_mode_label("agent_team") == "Agent Team 模式"


@patch("harness.agent.chapter_build._run_sub_agent_pipeline")
def test_sub_agent_mode(mock_sub):
    mock_sub.return_value = AgentResult(content="ok", success=True)
    with patch("harness.agent.chapter_build.settings") as st:
        st.chapter_build_mode = "sub_agent"
        run_chapter_pipeline(
            {"workspace_root": "/tmp"},
            chapter_id="chapter_1",
            title="T",
        )
    mock_sub.assert_called_once()


@patch("harness.agent.chapter_build._run_agent_team_pipeline")
def test_agent_team_mode(mock_team):
    mock_team.return_value = AgentResult(content="ok", success=True)
    with patch("harness.agent.chapter_build.settings") as st:
        st.chapter_build_mode = "agent_team"
        run_chapter_pipeline(
            {"workspace_root": "/tmp"},
            chapter_id="chapter_1",
            title="T",
        )
    mock_team.assert_called_once()
