"""Tests for batch-read tools."""

from pathlib import Path

from harness.services.tools.chapter_bundle import review_chapter_bundle, validate_chapter_bundle
from harness.services.tools.craft_review import CRAFT_REVIEW_ITEMS, mark_craft_review_checks
from harness.services.tools.missing_assets import report_missing_assets
from harness.services.tools.source_docs import read_source_docs
from harness.workflow.chapter_policies import check_tool_guard


def _manual_ids() -> list[str]:
    return [i.id for i in CRAFT_REVIEW_ITEMS if i.mode == "manual"]


def _write_reviewable_chapter(ws: Path) -> None:
    ppt = ws / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    reg = ppt / "src" / "registry"
    ch.mkdir(parents=True)
    reg.mkdir(parents=True)
    (ch / "narrations.ts").write_text(
        'export const narrations = [\n  "a",\n  "b",\n];\n', encoding="utf-8",
    )
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
    (reg / "chapter-meta.ts").write_text(
        "export const NEW_CHAPTER_IDS = ['chapter_1'];\n", encoding="utf-8",
    )


def test_read_source_docs(tmp_path):
    ws = tmp_path
    (ws / "script.md").write_text("# Script\nHello", encoding="utf-8")
    (ws / "outline.md").write_text("# Outline\nCh1", encoding="utf-8")
    state: dict = {"workspace_root": str(ws)}
    out = read_source_docs(state, workspace_root=ws)
    assert "script.md" in out
    assert "Hello" in out
    assert "outline.md" in out
    assert "Ch1" in out


def test_review_chapter_bundle_with_review(tmp_path):
    ws = tmp_path
    _write_reviewable_chapter(ws)
    state: dict = {"workspace_root": str(ws)}
    ctx: dict = {}
    content, ok = review_chapter_bundle(state, workspace_root=ws, chapter_id="chapter_1", ctx=ctx)
    assert "narrations.ts" in content
    assert "chapters.ts" in content
    assert "完工自检" in content
    report_missing_assets(state, chapter_id="chapter_1", items=[], note="")
    ctx.setdefault("workflow_state", state)
    ctx.setdefault("chapter_id", "chapter_1")
    mark_craft_review_checks(ctx, _manual_ids())
    assert ctx["review_ok"] is True


def test_validate_chapter_bundle_registry_missing(tmp_path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    (ch / "narrations.ts").write_text('export const narrations = ["a"];\n', encoding="utf-8")
    (ch / "index.tsx").write_text("export default function X() { return null; }\n", encoding="utf-8")
    (ch / "index.css").write_text(".x { }\n", encoding="utf-8")
    ok, errors, _ = validate_chapter_bundle(ppt, "chapter_1", chapters_ts="export const CHAPTERS = [];")
    assert ok is False
    assert any("not in chapters.ts" in e for e in errors)


def test_tool_guard_typecheck_requires_review(tmp_path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    (ch / "narrations.ts").write_text('export const narrations = ["a"];\n', encoding="utf-8")
    (ch / "index.tsx").write_text("export default function X() { return null; }\n", encoding="utf-8")
    ctx = {"review_ok": False, "typecheck_ok": False}
    msg = check_tool_guard("typecheck", {}, ppt=ppt, chapter_id="chapter_1", ctx=ctx)
    assert msg and "完工自检" in msg
