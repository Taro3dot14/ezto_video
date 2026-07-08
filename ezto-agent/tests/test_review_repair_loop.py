"""Tests for review-repair loop, todo aliases, and theme token validation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from harness.agent.loop import AgentResult
from harness.agent.review_repair_loop import run_review_repair_loop
from harness.services.tools.craft.craft_review import (
    REVIEW_BUNDLE_TODO,
    resolve_todo_item_id,
    reviewer_todo_items,
)


def test_resolve_todo_item_id_aliases():
    items = reviewer_todo_items()
    assert resolve_todo_item_id("review_chapter_bundle", items) == REVIEW_BUNDLE_TODO
    assert resolve_todo_item_id("REVIEW_BUNDLE", items) == REVIEW_BUNDLE_TODO
    assert resolve_todo_item_id(
        "review_chapter_bundle — 读修复后章节文件", items,
    ) == REVIEW_BUNDLE_TODO
    assert resolve_todo_item_id("VISUAL_DEMOS", items) == "VISUAL_DEMOS"


def test_resolve_repair_todo_alias():
    items = {"REPAIR": "Fix all reviewer-reported failures"}
    assert resolve_todo_item_id("Fix all reviewer-reported failures", items) == "REPAIR"
    assert resolve_todo_item_id("REPAIR", items) == "REPAIR"


def test_theme_tokens_flags_unknown_var(tmp_path):
    from harness.services.tools.craft.craft_review import run_craft_auto_checks

    ws = tmp_path
    ppt = ws / "presentation"
    styles = ppt / "src" / "styles"
    ch = ppt / "src" / "chapters" / "co"
    reg = ppt / "src" / "registry"
    styles.mkdir(parents=True)
    ch.mkdir(parents=True)
    reg.mkdir(parents=True)
    (styles / "tokens.css").write_text(":root { --shell: #dcc8a5; --text: #1a1a1a; }\n", encoding="utf-8")
    (styles / "base.css").write_text("/* base */\n", encoding="utf-8")
    (ch / "narrations.ts").write_text('export const narrations = ["a", "b"];\n', encoding="utf-8")
    (ch / "index.tsx").write_text(
        'export default function X({ step }) {\n'
        '  if (step === 0) return <div className="co-a"/>;\n'
        '  return <div className="co-b"/>;\n'
        '}\n',
        encoding="utf-8",
    )
    (ch / "index.css").write_text(
        ".co-badge { color: var(--bg); font-size: 96px; font-weight: 800; width: 60%; }\n"
        ".co-body { font-size: 40px; }\n",
        encoding="utf-8",
    )
    (reg / "chapters.ts").write_text("export const CHAPTERS = [];\n", encoding="utf-8")

    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="co")
    assert hints["THEME_TOKENS"]["pass"] is False
    assert "--bg" in hints["THEME_TOKENS"]["evidence"]


@patch("harness.agent.review_repair_loop.WebBuildAgent")
@patch("harness.agent.review_repair_loop.ChapterReviewAgent")
def test_last_review_round_still_triggers_repair(mock_reviewer_cls, mock_builder_cls):
    """Round 2 review failure must still run Repair (coldopen regression)."""
    fail_ctx = {"craft_review": {"items": {"THEME_TOKENS": {"state": "fail"}}, "review_ok": False}}
    ok_ctx = {"craft_review": {"items": {}, "review_ok": True}}

    review_fail = MagicMock()
    review_fail.run.return_value = AgentResult(content="fail", success=True, iterations=3, tool_calls=2)
    review_fail._ctx = fail_ctx
    review_fail._todo_done = set()
    review_fail.TODO_ITEMS = {"REVIEW_BUNDLE": "x", "THEME_TOKENS": "y"}
    review_fail.review_ok = False

    review_ok = MagicMock()
    review_ok.run.return_value = AgentResult(content="ok", success=True, iterations=2, tool_calls=1)
    review_ok._ctx = ok_ctx
    review_ok._todo_done = set()
    review_ok.TODO_ITEMS = {"REVIEW_BUNDLE": "x"}
    review_ok.review_ok = True

    mock_reviewer_cls.side_effect = [review_fail, review_ok]

    repair_agent = MagicMock()
    repair_agent.run.return_value = AgentResult(content="fixed", success=True, iterations=4, tool_calls=3)
    mock_builder_cls.return_value = repair_agent

    with patch("harness.agent.review_repair_loop.settings") as st:
        st.chapter_review_max_rounds = 2
        st.chapter_repair_max_rounds = 3
        with patch("harness.agent.review_repair_loop.failed_item_ids", side_effect=[["THEME_TOKENS"], []]):
            with patch("harness.agent.review_repair_loop.reconcile_auto_failures", return_value=[]):
                with patch("harness.agent.review_repair_loop.persist_craft_review"):
                    with patch("harness.agent.review_repair_loop.run_craft_auto_checks"):
                        with patch(
                            "harness.agent.review_repair_loop.format_review_failure_report",
                            return_value="report",
                        ):
                            ok, iters, tools, msg = run_review_repair_loop(
                                {"workspace_root": "/tmp"},
                                chapter_id="coldopen",
                                title="T",
                                chapter_index=1,
                            )

    assert ok is True
    assert msg is None
    repair_agent.run.assert_called_once()
    assert mock_reviewer_cls.call_count == 2
