"""Tests for chapter brief extraction and chapter context tool."""

from pathlib import Path

from harness.services.tools.chapter_context import read_chapter_context
from harness.workflow.chapter_brief import (
    extract_article_excerpts_for_chapter,
    format_brief_for_prompt,
    parse_article_refs_from_outline,
    parse_outline_text,
)


OUTLINE_SAMPLE = """# Video Outline

> **主题**：midnight-press

---

## 1. coldopen — 痛点与钩子（3 steps · ~45s）

**信息池**：
- 数字：3.8s —— article §1

**开发计划**：
- step 1 (~15s) — hero number 3.8s
- step 2 (~15s) — strike-through to 1.2s
- step 3 (~15s) — proof cards

口播节选：
> 你有没有想过，为什么...

---

## 2. why-good — 原理解释（4 steps · ~60s）

**开发计划**：
- step 1 (~15s) — intro
"""


def test_parse_outline_spec_format():
    chapters = parse_outline_text(OUTLINE_SAMPLE)
    assert len(chapters) == 2
    assert chapters[0]["id"] == "coldopen"
    assert chapters[0]["title"] == "痛点与钩子"
    assert chapters[0]["steps"] == 3
    assert "hero number" in chapters[0]["section"]
    assert chapters[1]["id"] == "why_good"


def test_parse_outline_legacy_format():
    text = "## Chapter 1 — Introduction\n\nSome content"
    chapters = parse_outline_text(text)
    assert chapters[0]["id"] == "chapter_1"
    assert "Introduction" in chapters[0]["title"]


def test_format_brief():
    brief = {
        "chapter_id": "coldopen",
        "expected_steps": 3,
        "outline_section": (
            "## 1. coldopen\n"
            "**开发计划**：\n"
            "- step 1 (~15s) — hero number\n"
            "- step 2 (~15s) — strike-through\n"
            "- step 3 (~15s) — proof cards"
        ),
        "script_excerpt": "beat one",
        "article_excerpt": "",
    }
    prompt = format_brief_for_prompt(brief, "痛点与钩子")
    assert "write_narrations" in prompt
    assert "step === 0" in prompt
    assert "[code step 0]" in prompt
    assert "[code step 2]" in prompt
    assert "3 screens" in prompt
    assert "beat one" in prompt
    assert "read_chapter_context" in prompt
    assert "Projection readability" in prompt
    assert "96px" in prompt
    assert "hook-chapter" in prompt
    assert "Steps: outline labels vs code" in prompt
    assert "ZERO emoji" in prompt or "never emoji" in prompt.lower()
    assert "craft_auto_check" in prompt
    assert "NO_AI_SLOP" in prompt


def test_parse_article_refs_from_outline():
    section = OUTLINE_SAMPLE + "\n- 引用：foo —— 来源 article §Why dynamic workflows"
    refs = parse_article_refs_from_outline(section)
    assert "article §1" in refs


def test_extract_article_excerpts_by_section_name():
    article = """# Title

Intro paragraph about hooks.

## Example prompts

Prompt list here.

## Why dynamic workflows

Failure modes paragraph.
"""
    outline = "## 1. why — test\n- foo —— 来源 article §Why dynamic workflows\n"
    excerpt, used = extract_article_excerpts_for_chapter(article, outline)
    assert "Failure modes" in excerpt
    assert any("Why dynamic" in r for r in used)


def test_read_chapter_context_tool(tmp_path):
    ws = tmp_path
    (ws / "outline.md").write_text(OUTLINE_SAMPLE, encoding="utf-8")
    (ws / "script.md").write_text("beat one\n---\nbeat two", encoding="utf-8")
    (ws / "article.md").write_text("# Art\n\nHook intro.\n\n## Section\n\ndata", encoding="utf-8")
    ex_dir = ws / "presentation" / "src" / "chapters" / "01-example"
    ex_dir.mkdir(parents=True)
    (ex_dir / "Example.tsx").write_text("export default function X() {}", encoding="utf-8")
    state = {
        "workspace_root": str(ws),
        "artifact_paths": {
            "outline.md": str(ws / "outline.md"),
            "script.md": str(ws / "script.md"),
            "article.md": str(ws / "article.md"),
        },
    }
    out = read_chapter_context(
        state,
        workspace_root=ws,
        chapter_id="coldopen",
        chapter_index=1,
        chapter_title="痛点与钩子",
    )
    assert "01-example" in out
    assert "Steps: outline labels vs code" in out
    assert "NO_AI_SLOP" in out or "never emoji" in out.lower()
    assert "Example.tsx" in out
    assert "export default function X" in out
    assert "Hook intro" in out or "article §1" in out
