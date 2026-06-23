"""Tests for chapter policy validation."""

from pathlib import Path

from harness.workflow.chapter_policies import (
    auto_validate_chapter,
    validate_chapter_tsx_contract,
    validate_theme_contrast,
    validate_tsx_css_classes,
)


def test_validate_chapter_tsx_contract_rejects_useChapterStore():
    tsx = (
        "import { useChapterStore } from '../../store/useChapterStore';\n"
        "export default function X() { const step = useChapterStore(s => s.step); return null; }\n"
    )
    msg = validate_chapter_tsx_contract(tsx)
    assert msg is not None
    assert "useChapterStore" in msg
    assert "ChapterStepProps" in msg


def test_validate_chapter_tsx_contract_accepts_chapter_step_props():
    tsx = (
        "import type { ChapterStepProps } from '../../registry/types';\n"
        "export default function X({ step }: ChapterStepProps) { return step === 0 ? null : null; }\n"
    )
    assert validate_chapter_tsx_contract(tsx) is None


def test_validate_tsx_css_classes_detects_missing(tmp_path: Path):
    ch = tmp_path / "presentation" / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ch.joinpath("index.tsx").write_text(
        '<div className="hk-scene scene-pad"><div className="hk-stat-body" /></div>',
        encoding="utf-8",
    )
    ch.joinpath("index.css").write_text(".hk-cover-h { font-size: 96px; }\n", encoding="utf-8")

    msg = validate_tsx_css_classes(tmp_path / "presentation", "hook")
    assert msg is not None
    assert "hk-stat-body" in msg


def test_validate_tsx_css_classes_passes_when_matched(tmp_path: Path):
    ch = tmp_path / "presentation" / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ch.joinpath("index.tsx").write_text(
        '<div className="hk-scene scene-pad"><div className="hk-stat-body" /></div>',
        encoding="utf-8",
    )
    ch.joinpath("index.css").write_text(
        ".hk-scene {}\n.hk-stat-body { font-size: 36px; }\n",
        encoding="utf-8",
    )

    assert validate_tsx_css_classes(tmp_path / "presentation", "hook") is None


def test_auto_validate_warns_on_small_font(tmp_path: Path):
    ch = tmp_path / "presentation" / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ch.joinpath("narrations.ts").write_text('export default [\n  "a",\n  "b",\n];\n', encoding="utf-8")
    ch.joinpath("index.tsx").write_text(
        'export default function X({ step }: { step: number }) {\n'
        '  if (step === 0) return <div className="hk-scene" />;\n'
        '  return <div className="hk-scene" />;\n'
        '}\n',
        encoding="utf-8",
    )
    ch.joinpath("index.css").write_text(".hk-scene { font-size: 20px; }\n", encoding="utf-8")

    hint = auto_validate_chapter(
        tmp_path / "presentation",
        "hook",
        written_path="presentation/src/chapters/hook/index.css",
    )
    assert hint is not None
    assert "20px" in hint


def test_auto_validate_skips_decorative_small_font(tmp_path: Path):
    ch = tmp_path / "presentation" / "src" / "chapters" / "hook"
    ch.mkdir(parents=True)
    ch.joinpath("narrations.ts").write_text('export default [\n  "a",\n];\n', encoding="utf-8")
    ch.joinpath("index.tsx").write_text(
        'export default function X({ step }: { step: number }) {\n'
        '  if (step === 0) return <div className="hk-scene" />;\n'
        '  return null;\n'
        '}\n',
        encoding="utf-8",
    )
    ch.joinpath("index.css").write_text(
        ".hk-scene { font-size: 96px; }\n"
        ".intro-svg-node { font-size: 15px; }\n"
        ".intro-code-body { font-size: 22px; font-family: var(--font-mono); }\n",
        encoding="utf-8",
    )

    hint = auto_validate_chapter(
        tmp_path / "presentation",
        "hook",
        written_path="presentation/src/chapters/hook/index.css",
    )
    assert hint is None


def test_validate_theme_contrast_flags_dark_bg_trap():
    css = """
    .co-scene { background: var(--bg, #0b0b0d); color: var(--text); }
    .co-fail-title { color: var(--text); }
    """
    msg = validate_theme_contrast(css)
    assert msg is not None
    assert "--bg" in msg


def test_validate_theme_contrast_passes_theme_surfaces():
    css = """
    .co-scene { background: var(--shell); color: var(--text); }
    .co-fail-card { background: var(--surface-2); border: 1px solid var(--rule); }
    """
    assert validate_theme_contrast(css) is None
