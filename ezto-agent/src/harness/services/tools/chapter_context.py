"""Batch-read chapter build context: article excerpts + 01-example pattern."""

from __future__ import annotations

from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call
from harness.workflow.chapter_brief import (
    LAYOUT_SYSTEM_BLOCK,
    NO_AI_SLOP_BLOCK,
    PROJECTION_READABILITY_BLOCK,
    get_chapter_brief,
    load_example_chapter_pattern,
    parse_article_refs_from_outline,
)
from harness.workflow.step_indexing import agent_rule_block


def read_chapter_context(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
    chapter_id: str,
    chapter_index: int = 1,
    chapter_title: str = "",
) -> str:
    """Return article excerpts (per outline refs) + script beats + 01-example files."""
    _record_tool_call(
        state,
        "read_chapter_context",
        {"chapter_id": chapter_id, "chapter_index": chapter_index},
        allowed=True,
        reason="Batch read article + 01-example for chapter build",
    )

    brief = get_chapter_brief(state, chapter_id, chapter_index)
    title = chapter_title or chapter_id
    parts = [
        f"# Chapter context: {title} (`{chapter_id}`)",
        "",
    ]

    outline_section = brief.get("outline_section", "")
    refs = brief.get("article_refs") or parse_article_refs_from_outline(outline_section)
    article_excerpt = brief.get("article_excerpt", "")

    parts.append("## Article excerpts (visual detail — from outline 信息池 sources)")
    if refs:
        parts.append(f"Refs parsed: {', '.join(refs)}")
    if article_excerpt:
        parts.append(article_excerpt)
    else:
        paths = state.get("artifact_paths", {})
        article_path = paths.get("article.md")
        if article_path and Path(article_path).exists():
            parts.append("(No 信息池 refs — nothing extracted.)")
        else:
            parts.append("(No article.md — script-only project; design visuals from outline.)")
    parts.append("")

    script_excerpt = brief.get("script_excerpt", "")
    if script_excerpt:
        parts += [
            "## Script beats (narration source for this chapter)",
            script_excerpt,
            "",
        ]

    parts.append(load_example_chapter_pattern(workspace_root))

    layout_spec = workspace_root / "presentation" / "src" / "layouts" / "LAYOUT-SYSTEM.md"
    if layout_spec.is_file():
        parts += [
            "",
            "## Layout Shell System (presentation/src/layouts/LAYOUT-SYSTEM.md)",
            layout_spec.read_text(encoding="utf-8", errors="replace")[:8000],
        ]

    mask = workspace_root / "presentation" / "src" / "components" / "MaskReveal.tsx"
    if mask.exists():
        parts += [
            "",
            "## MaskReveal (import from ../../components/MaskReveal)",
            "```",
            mask.read_text(encoding="utf-8", errors="replace")[:1200],
            "```",
        ]

    parts += [
        "",
        agent_rule_block(),
        "",
        NO_AI_SLOP_BLOCK,
        "",
        LAYOUT_SYSTEM_BLOCK,
        "",
        PROJECTION_READABILITY_BLOCK,
        "",
        "## Global primitive classes (in base.css — do NOT re-read)",
        "scene-pad, masthead, kicker, hero-num, label-mono, rule, card, pull-quote, "
        "serif-cn, display-en, display-en-soft, dot-accent — use theme tokens `--t-*`, `--text`, `--accent`.",
        "",
        "## Do NOT read_file presentation/src/styles/* — sizes are in tokens above.",
    ]
    return "\n".join(parts)
