"""Tests for CHAPTER-CRAFT craft review checklist."""

from pathlib import Path

from harness.services.tools.chapter.chapter_bundle import review_chapter_bundle
from harness.services.tools.craft.craft_review import (
    CRAFT_REVIEW_ITEMS,
    attest_craft_review_item,
    craft_auto_check,
    craft_checklist_snapshot,
    format_craft_checklist,
    init_craft_checklist,
    load_craft_review_into_ctx,
    mark_craft_review_check,
    mark_craft_review_checks,
    passed_item_ids,
    persist_craft_review,
    prepare_recheck_round,
    reconcile_auto_failures,
    reviewer_todo_items,
    run_craft_auto_checks,
    sync_review_ok,
    try_check_craft_todo_item,
)
from harness.services.tools.chapter.missing_assets import report_missing_assets


def _write_minimal_chapter(ws: Path, chapter_id: str = "chapter_1") -> None:
    ppt = ws / "presentation"
    ch = ppt / "src" / "chapters" / chapter_id
    reg = ppt / "src" / "registry"
    ch.mkdir(parents=True)
    reg.mkdir(parents=True)
    (ch / "narrations.ts").write_text(
        'export const narrations = [\n  "hello world",\n  "second step",\n];\n',
        encoding="utf-8",
    )
    (ch / "index.tsx").write_text(
        "import MaskReveal from '../../components/MaskReveal';\n"
        "export default function Ch({ step }) {\n"
        '  if (step === 0) return <div className="hk-hero">Title</div>;\n'
        '  if (step === 1) return <div className="hk-body"><MaskReveal>Body</MaskReveal></div>;\n'
        "}\n",
        encoding="utf-8",
    )
    (ch / "index.css").write_text(
        ".hk-hero { font-size: 120px; font-weight: 800; width: 78%; }\n"
        ".hk-body { font-size: 40px; font-weight: 500; width: 60%; "
        "animation: hk-in 0.8s ease; }\n"
        "@keyframes hk-in { from { opacity: 0; } to { opacity: 1; } }\n",
        encoding="utf-8",
    )
    (reg / "chapters.ts").write_text(
        f"import {chapter_id} from '../chapters/{chapter_id}';\n"
        f"export const CHAPTERS = [{{ id: '{chapter_id}', title: 'T' }}];\n",
        encoding="utf-8",
    )
    (reg / "chapter-meta.ts").write_text(
        f"export const NEW_CHAPTER_IDS = ['{chapter_id}'];\n", encoding="utf-8",
    )


def _manual_item_ids() -> list[str]:
    return [i.id for i in CRAFT_REVIEW_ITEMS if i.mode == "manual"]


def _report_no_missing(state: dict, chapter_id: str = "chapter_1") -> None:
    report_missing_assets(state, chapter_id=chapter_id, items=[], note="")


def _complete_manual_checks(ctx: dict, state: dict, chapter_id: str = "chapter_1") -> None:
    ctx.setdefault("workflow_state", state)
    ctx.setdefault("chapter_id", chapter_id)
    _report_no_missing(state, chapter_id)
    mark_craft_review_checks(ctx, _manual_item_ids())


def test_craft_auto_checks_store_hints_not_block(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["VISUAL_DEMOS"]["pass"] is True
    assert ctx["craft_review"]["items"]["VISUAL_DEMOS"]["state"] == "pass"
    assert ctx["craft_review"]["items"]["VARIED_ANIMATIONS"]["state"] == "pending"
    assert ctx.get("review_ok") is False


def test_craft_review_complete_after_manual_checks(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    state: dict = {"workspace_root": str(ws)}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    for item_id in [i.id for i in CRAFT_REVIEW_ITEMS if i.mode == "auto"]:
        if ctx["craft_review"]["items"][item_id]["state"] != "pass":
            mark_craft_review_check(ctx, item_id)
    ctx.setdefault("workflow_state", state)
    ctx.setdefault("chapter_id", "chapter_1")
    _report_no_missing(state, "chapter_1")
    for item_id in [i.id for i in CRAFT_REVIEW_ITEMS if i.mode == "manual"]:
        if ctx["craft_review"]["items"][item_id]["state"] == "pass":
            continue
        mark_craft_review_check(ctx, item_id)
    sync_review_ok(ctx)
    assert ctx["review_ok"] is True


def test_projection_type_auto_pass_without_font_size(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        ".hk-hero { width: 78%; animation: hk-in 0.8s; }\n"
        ".hk-body { width: 60%; }\n"
        "@keyframes hk-in { from { opacity: 0; } }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert ctx["craft_review"]["items"]["PROJECTION_TYPE"]["state"] == "pass"
    assert "无 font-size" in ctx["craft_review"]["items"]["PROJECTION_TYPE"]["evidence"]


def test_todolist_check_allowed_despite_auto_hint_fail(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(".hk-hero { font-size: 12px; }\n", encoding="utf-8")
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert ctx["craft_review"]["auto_hints"]["NO_TINY_TEXT_WALL"]["pass"] is False
    msg = attest_craft_review_item(ctx, "ZOOM_READABLE", result="pass")
    assert msg is None
    err = try_check_craft_todo_item(
        ctx,
        "NO_TINY_TEXT_WALL",
        result="pass",
        reason="28px only on auxiliary .badge-tagline, hero/body meet floor",
    )
    assert err == ""
    assert ctx["craft_review"]["items"]["NO_TINY_TEXT_WALL"]["state"] == "pass"


def test_reviewer_fail_attestation_requires_reason(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    msg = attest_craft_review_item(ctx, "THEME_TOKENS", result="fail", reason="hex in css")
    assert "fix" in msg
    msg2 = attest_craft_review_item(
        ctx,
        "THEME_TOKENS",
        result="fail",
        reason="index.css L42 hardcoded #ff0000",
        fix="Replace #ff0000 with var(--text) in .terminal-body",
    )
    assert msg2 is None
    assert ctx["craft_review"]["items"]["THEME_TOKENS"]["state"] == "fail"
    assert ctx["craft_review"]["items"]["THEME_TOKENS"]["fix"] == (
        "Replace #ff0000 with var(--text) in .terminal-body"
    )
    assert ctx["review_ok"] is False


def test_prepare_recheck_round_only_failed_items(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    attest_craft_review_item(ctx, "VISUAL_DEMOS", result="pass")
    attest_craft_review_item(
        ctx,
        "THEME_TOKENS",
        result="fail",
        reason="hardcoded hex",
        fix="use var(--shell) for terminal bg",
    )
    attest_craft_review_item(
        ctx,
        "NO_TINY_TEXT_WALL",
        result="fail",
        reason="28px body text",
        fix="bump .badge-tagline to 36px",
    )
    recheck = prepare_recheck_round(ctx)
    assert set(recheck) == {"THEME_TOKENS", "NO_TINY_TEXT_WALL"}
    assert ctx["craft_review"]["items"]["VISUAL_DEMOS"]["state"] == "pass"
    assert ctx["craft_review"]["items"]["THEME_TOKENS"]["state"] == "pending"
    todos = reviewer_todo_items(recheck_ids=recheck)
    assert "VISUAL_DEMOS" not in todos
    assert "THEME_TOKENS" in todos
    assert "[复审]" in todos["THEME_TOKENS"]


def test_persist_and_load_craft_review(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="hook")
    attest_craft_review_item(ctx, "VISUAL_DEMOS", result="pass")
    wf: dict = {"workspace_root": str(ws)}
    persist_craft_review(wf, "hook", ctx)
    ctx2: dict = {}
    assert load_craft_review_into_ctx(ctx2, wf, "hook") is True
    assert ctx2["craft_review"]["items"]["VISUAL_DEMOS"]["state"] == "pass"


def test_review_failure_report_lists_reviewer_fails(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    attest_craft_review_item(ctx, "THEME_TOKENS", result="fail", reason="hardcoded hex in terminal", fix="use tokens")
    from harness.services.tools.craft.craft_review import format_review_failure_report

    report = format_review_failure_report(ctx, chapter_id="chapter_1")
    assert "Reviewer failures" in report
    assert "THEME_TOKENS" in report
    assert "hardcoded hex" in report


def test_try_check_fail_attestation_registers_item(tmp_path):
    """Regression: fail attest must not be treated as validation error (old bug: startswith ❌)."""
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    err = try_check_craft_todo_item(
        ctx,
        "NO_AI_SLOP",
        result="fail",
        reason="emoji in AgentIcon step 1",
        fix="Remove emoji span from index.tsx AgentIcon",
    )
    assert err == ""
    assert ctx["craft_review"]["items"]["NO_AI_SLOP"]["state"] == "fail"
    assert ctx["review_ok"] is False


def test_pass_blocked_when_auto_hint_fails_without_reason(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\nexport const E = "🔬";\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    err = try_check_craft_todo_item(ctx, "NO_AI_SLOP", result="pass")
    assert "auto-check" in err


def test_reconcile_auto_failures_flips_bypass_pass(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\nexport const E = "🔬";\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    # Simulate legacy Reviewer bypass (plain pass while auto-check failed)
    from harness.services.tools.craft.craft_review import _set_item, sync_review_ok
    _set_item(ctx, "NO_AI_SLOP", state="pass", evidence="reviewer pass")
    sync_review_ok(ctx)
    assert ctx["craft_review"]["items"]["NO_AI_SLOP"]["state"] == "pass"
    flipped = reconcile_auto_failures(ctx)
    assert flipped == ["NO_AI_SLOP"]
    assert ctx["craft_review"]["items"]["NO_AI_SLOP"]["state"] == "fail"
    assert ctx["review_ok"] is False


def test_reviewer_done_accepts_fail_items(tmp_path):
    """done() must succeed when all items reviewed including failures → Repair path."""
    from harness.agent.loop import ChapterReviewAgent
    from harness.services.tools.craft.craft_review import reviewer_todo_items

    ws = tmp_path
    _write_minimal_chapter(ws)
    state: dict = {"workspace_root": str(ws)}
    _report_no_missing(state, "chapter_1")
    agent = ChapterReviewAgent(state)
    agent._chapter_id = "chapter_1"
    init_craft_checklist(agent._ctx, workspace_root=ws, chapter_id="chapter_1")
    agent._ctx["workflow_state"] = state
    agent._ctx["chapter_id"] = "chapter_1"

    for item_id in reviewer_todo_items():
        if item_id == "REVIEW_BUNDLE":
            agent._mark("REVIEW_BUNDLE")
            continue
        if item_id == "NO_AI_SLOP":
            agent._mark(
                "NO_AI_SLOP",
                result="fail",
                reason="emoji icons in step 1",
                fix="delete emoji prop from AgentIcon",
            )
        else:
            agent._mark(item_id, result="pass")

    out = agent._verify("review summary")
    assert out.startswith("[DONE] Review complete with failures")
    assert "NO_AI_SLOP" in out
    assert agent.review_ok is False


def test_review_chapter_bundle_includes_craft_checklist(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    state: dict = {"workspace_root": str(ws)}
    content, ok = review_chapter_bundle(state, workspace_root=ws, chapter_id="chapter_1", ctx=ctx)
    assert "CHAPTER-CRAFT 完工自检" in content
    assert "视觉演示" in content
    assert "ITEM_ID checklist" in content
    assert ok is False
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    for item_id in [i.id for i in CRAFT_REVIEW_ITEMS if i.mode == "auto"]:
        mark_craft_review_check(ctx, item_id)
    _complete_manual_checks(ctx, state)
    assert ctx["review_ok"] is True


def test_craft_auto_check_tool(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    text = craft_auto_check(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert "Craft auto-check" in text
    assert "VISUAL_DEMOS" in text
    assert ctx["craft_review"]["auto_hints"]["VISUAL_DEMOS"]["pass"] is True


def test_format_craft_checklist_shows_progress(tmp_path):
    ctx: dict = {"craft_review": {"items": {
        "VISUAL_DEMOS": {"state": "pass", "evidence": "ok", "mode": "auto"},
        "VARIED_ANIMATIONS": {"state": "pending", "evidence": "", "mode": "manual"},
    }}}
    text = format_craft_checklist(ctx)
    assert "进度:" in text
    assert "☐" in text or "核查后" in text


def test_craft_checklist_snapshot_for_frontend(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    init_craft_checklist(ctx, workspace_root=ws, chapter_id="chapter_1")
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    snap = craft_checklist_snapshot(ctx)
    assert snap["total"] == 19
    assert snap["done"] < snap["total"]
    assert len(snap["items"]) == len(CRAFT_REVIEW_ITEMS)
    assert snap["items"][0]["id"] == "VISUAL_DEMOS"
    assert snap["items"][0]["state"] in ("pass", "fail", "pending", "deferred")


def test_no_ai_slop_fails_italic(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\n  if (step === 9) return <span className="serif-it">bad</span>;\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_AI_SLOP"]["pass"] is False
    assert "serif-it" in hints["NO_AI_SLOP"]["evidence"]


def test_no_ai_slop_allows_terminal_symbols(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\n  if (step === 2) return <span className="hk-cursor">▌</span>;\n'
        + '  if (step === 3) return <span className="hk-sep">·</span>;\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_AI_SLOP"]["pass"] is True


def test_no_tiny_text_allows_auxiliary_28px(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        ".hk-hero { font-size: 120px; font-weight: 800; width: 78%; }\n"
        ".hk-body { font-size: 40px; font-weight: 500; width: 60%; }\n"
        ".hk-badge-tagline { font-size: 28px; font-weight: 500; }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_TINY_TEXT_WALL"]["pass"] is True


def test_no_tiny_text_fails_body_below_28px(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        ".hk-hero { font-size: 120px; }\n"
        ".hk-body { font-size: 26px; }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_TINY_TEXT_WALL"]["pass"] is False


def test_theme_tokens_allows_terminal_simulation_hex(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        (ch / "index.css").read_text(encoding="utf-8")
        + "\n.terminal-window { background: #1a1a2e; color: #e0e0e0; }\n"
        + ".terminal-dot { background: #ff5f57; }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["THEME_TOKENS"]["pass"] is True


def test_theme_tokens_allows_macos_window_dots(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        (ch / "index.css").read_text(encoding="utf-8")
        + "\n.intro-win-dot--red { background: #ff5f57; }\n"
        + ".intro-win-dot--yellow { background: #febc2e; }\n"
        + ".intro-win-dot--green { background: #28c840; }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["THEME_TOKENS"]["pass"] is True


def test_no_tiny_text_skips_code_and_svg_labels(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.css").write_text(
        ".hk-hero { font-size: 120px; font-weight: 800; width: 78%; }\n"
        ".hk-body { font-size: 40px; font-weight: 500; width: 60%; }\n"
        ".intro-svg-node { font-size: 15px; }\n"
        ".intro-code-body { font-size: 22px; }\n"
        ".intro-win-line { font-size: 20px; }\n",
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_TINY_TEXT_WALL"]["pass"] is True


def test_no_muted_text_allows_svg_stroke(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\n  if (step === 9) return <svg><path stroke="var(--text-mute)" /></svg>;\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_MUTED_TEXT"]["pass"] is True


def test_no_muted_text_fails_muted_on_copy(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ch = ws / "presentation" / "src" / "chapters" / "chapter_1"
    (ch / "index.tsx").write_text(
        (ch / "index.tsx").read_text(encoding="utf-8")
        + '\n  if (step === 9) return <p style={{ color: "var(--text-mute)" }}>muted</p>;\n',
        encoding="utf-8",
    )
    ctx: dict = {}
    hints = run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="chapter_1")
    assert hints["NO_MUTED_TEXT"]["pass"] is False


def test_review_chapter_bundle_includes_item_id_checklist(tmp_path):
    ws = tmp_path
    _write_minimal_chapter(ws)
    ctx: dict = {}
    state: dict = {"workspace_root": str(ws)}
    content, _ok = review_chapter_bundle(state, workspace_root=ws, chapter_id="chapter_1", ctx=ctx)
    assert "ITEM_ID checklist" in content
    assert "`VISUAL_DEMOS`" in content
