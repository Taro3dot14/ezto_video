"""Tests for report_missing_assets tool and MISSING_ASSETS_NOTE gate."""

from harness.services.tools.craft_review import (
    init_craft_checklist,
    mark_craft_review_check,
    run_craft_auto_checks,
    try_check_craft_todo_item,
)
from harness.services.tools.missing_assets import (
    format_missing_assets_for_user,
    get_missing_assets,
    report_missing_assets,
)


def test_report_missing_assets_writes_state():
    state: dict = {"tool_calls": []}
    msg = report_missing_assets(
        state,
        chapter_id="chapter_1",
        items=["产品 logo PNG", "团队合影"],
        note="用户后续补充",
    )
    assert "已写入" in msg
    entry = get_missing_assets(state, "chapter_1")
    assert entry is not None
    assert entry["items"] == ["产品 logo PNG", "团队合影"]
    assert entry["note"] == "用户后续补充"
    assert any(c["tool"] == "report_missing_assets" for c in state.get("tool_calls", []))


def test_report_empty_items_means_none_missing():
    state: dict = {}
    report_missing_assets(state, chapter_id="chapter_2", items=[])
    entry = get_missing_assets(state, "chapter_2")
    assert entry is not None
    assert entry["items"] == []
    text = format_missing_assets_for_user(state, "chapter_2")
    assert text is not None
    assert "已齐全" in text or "无缺失" in text


def test_missing_assets_note_blocked_without_report(tmp_path):
    ws = tmp_path
    ctx: dict = {"chapter_id": "chapter_1", "workflow_state": {"workspace_root": str(ws)}}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    err = try_check_craft_todo_item(ctx, "MISSING_ASSETS_NOTE")
    assert "report_missing_assets" in err


def test_missing_assets_note_passes_after_report(tmp_path):
    ws = tmp_path
    state: dict = {"workspace_root": str(ws)}
    report_missing_assets(state, chapter_id="chapter_1", items=["图表截图"])
    ctx: dict = {"chapter_id": "chapter_1", "workflow_state": state}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    err = try_check_craft_todo_item(ctx, "MISSING_ASSETS_NOTE")
    assert err == ""


def test_craft_review_check_requires_report(tmp_path):
    ws = tmp_path
    ctx: dict = {"chapter_id": "chapter_1", "workflow_state": {}}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    msg = mark_craft_review_check(ctx, "MISSING_ASSETS_NOTE")
    assert "report_missing_assets" in msg
