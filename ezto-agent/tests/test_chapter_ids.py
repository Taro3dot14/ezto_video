"""Tests for chapter folder id resolution."""

from pathlib import Path

from harness.services.tools.chapter.chapter_bundle import review_chapter_bundle
from harness.services.tools.craft.craft_review import (
    _check_no_header_footer,
    run_craft_auto_checks,
)
from harness.workflow.chapter_ids import resolve_chapter_id


def _write_hook_chapter(ws: Path) -> None:
    ch = ws / "presentation" / "src" / "chapters" / "hook"
    reg = ws / "presentation" / "src" / "registry"
    styles = ws / "presentation" / "src" / "styles"
    ch.mkdir(parents=True)
    reg.mkdir(parents=True)
    styles.mkdir(parents=True)
    (styles / "base.css").write_text(
        ":root { --t-projection-hero: clamp(96px, 8vw, 140px); "
        "--t-projection-body: clamp(36px, 3vw, 48px); }\n",
        encoding="utf-8",
    )
    (ch / "narrations.ts").write_text(
        'export const narrations = ["a", "b"];\n', encoding="utf-8",
    )
    (ch / "index.tsx").write_text(
        "import { SceneChrome } from '../../components/SceneChrome';\n"
        "export default function Ch({ step }) {\n"
        '  if (step === 0) return <SceneChrome><div className="hk-hero">X</div></SceneChrome>;\n'
        '  if (step === 1) return <SceneChrome><div className="hk-body">Y</div></SceneChrome>;\n'
        "}\n",
        encoding="utf-8",
    )
    (ch / "index.css").write_text(
        ".hk-hero { font-size: var(--t-projection-hero); font-weight: 800; }\n"
        ".hk-body { font-size: var(--t-projection-body); font-weight: 500; "
        "animation: hk-in 0.5s; }\n"
        "@keyframes hk-in { from { opacity: 0; } to { opacity: 1; } }\n",
        encoding="utf-8",
    )
    (reg / "chapters.ts").write_text(
        "import hook from '../chapters/hook';\n"
        "export const CHAPTERS = [{ id: 'hook', title: 'Hook' }];\n",
        encoding="utf-8",
    )
    (reg / "chapter-meta.ts").write_text("export const NEW_CHAPTER_IDS = ['hook'];\n", encoding="utf-8")
    (ws / "outline.md").write_text(
        "## 1. hook — 钩子（2 steps）\n\n**开发计划**:\n- step 1\n",
        encoding="utf-8",
    )


def test_resolve_chapter_id_maps_chapter_1_to_hook(tmp_path):
    ws = tmp_path
    _write_hook_chapter(ws)
    state = {
        "workspace_root": str(ws),
        "artifact_paths": {"outline.md": str(ws / "outline.md")},
    }
    cid, warn = resolve_chapter_id(state, "chapter_1", default="hook")
    assert cid == "hook"
    assert warn is not None


def test_masthead_header_forbidden():
    tsx = '<header className="hk-masthead"><span className="brand">X</span></header>'
    ok, msg = _check_no_header_footer(tsx)
    assert not ok
    assert "header" in msg.lower()


def test_scene_chrome_brand_prop_forbidden():
    tsx = '<SceneChrome brand="X" issue="Y"><div className="lx-hero">Hi</div></SceneChrome>'
    ok, msg = _check_no_header_footer(tsx)
    assert not ok
    assert "brand" in msg.lower()


def test_scene_chrome_content_only_passes():
    tsx = '<SceneChrome><div className="lx-cover-body"><h1 className="lx-hero">Hi</h1></div></SceneChrome>'
    ok, msg = _check_no_header_footer(tsx)
    assert ok, msg


def test_review_bundle_resolves_chapter_1(tmp_path):
    ws = tmp_path
    _write_hook_chapter(ws)
    state = {"workspace_root": str(ws)}
    ctx: dict = {"chapter_id": "hook"}
    content, _ = review_chapter_bundle(
        state, workspace_root=ws, chapter_id="chapter_1", ctx=ctx,
    )
    assert "hook" in content or "自动改用" in content
    run_craft_auto_checks(ctx, workspace_root=ws, chapter_id="hook")
    assert ctx["craft_review"]["items"]["PROJECTION_TYPE"]["state"] == "pending"
    assert ctx["craft_review"]["auto_hints"]["NO_HEADER_FOOTER"]["pass"] is True
