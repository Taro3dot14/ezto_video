"""Tests for chapter tool guard policies."""

from pathlib import Path

from harness.agent.tools.guards import check_tool_guard
from harness.workflow.chapter_validation import validate_no_header_footer_tsx


def test_write_file_guard_passes_when_content_provided(tmp_path: Path):
    """Regression: runtime must pass content into check_tool_guard."""
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ctx = {"tool_profile": "builder", "chapter_context_read": True}
    tsx = (
        'import { SceneChrome } from "../../components/SceneChrome";\n'
        "import type { ChapterStepProps } from '../../registry/types';\n"
        "export default function Coldopen({ step }: ChapterStepProps) {\n"
        '  if (step === 0) return <SceneChrome><div className="lx-cover-body">'
        '<h1 className="lx-hero">Title</h1></div></SceneChrome>;\n'
        '  if (step === 1) return <SceneChrome><div className="lx-solo">'
        '<div className="lx-solo-panel mot-stamp-drop"><h2 className="lx-title">Solo</h2></div></div></SceneChrome>;\n'
        '  if (step === 2) return <SceneChrome><div className="lx-kicker">K</div></SceneChrome>;\n'
        "  return null;\n"
        "}\n"
    )
    assert len(tsx) >= 180
    msg = check_tool_guard(
        "write_file",
        {"path": "presentation/src/chapters/hook/index.tsx", "content": tsx},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    )
    assert msg is None


def test_write_file_guard_blocks_empty_content(tmp_path: Path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ctx = {"tool_profile": "builder", "chapter_context_read": True}
    msg = check_tool_guard(
        "write_file",
        {"path": "presentation/src/chapters/hook/index.tsx", "content": ""},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    )
    assert msg is not None
    assert "0 chars" in msg or "only" in msg


def test_builder_blocked_header_in_index_tsx(tmp_path: Path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ctx = {"tool_profile": "builder", "chapter_context_read": True}
    tsx = (
        'import { SceneChrome } from "../../components/SceneChrome";\n'
        'export default function X({ step }: { step: number }) {\n'
        '  if (step === 0) return <SceneChrome brand="Bad"><div className="hk-hero">X</div></SceneChrome>;\n'
        "  return null;\n"
        "}\n"
    )
    msg = check_tool_guard(
        "write_file",
        {"path": "presentation/src/chapters/hook/index.tsx", "content": tsx},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    )
    assert msg is not None
    assert "header" in msg.lower() or "brand" in msg.lower()
    assert validate_no_header_footer_tsx(tsx) is not None


def test_builder_blocked_short_index_tsx(tmp_path: Path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ctx = {"tool_profile": "builder", "chapter_context_read": True}
    msg = check_tool_guard(
        "write_file",
        {"path": "presentation/src/chapters/hook/index.tsx", "content": "// stub\n"},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    )
    assert msg is not None
    assert "7 chars" in msg or "only" in msg


def test_builder_blocked_write_until_read_chapter_context(tmp_path: Path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ctx = {"tool_profile": "builder", "chapter_context_read": False}
    msg = check_tool_guard(
        "write_narrations",
        {"lines": ['"hello"']},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    )
    assert msg is not None
    assert "read_chapter_context" in msg

    ctx["chapter_context_read"] = True
    assert check_tool_guard(
        "write_narrations",
        {"lines": ['"hello"']},
        ppt=ppt,
        chapter_id="hook",
        ctx=ctx,
    ) is None
