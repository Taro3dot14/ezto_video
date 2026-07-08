"""Batch-read chapter build context: article excerpts + 01-example pattern."""

from __future__ import annotations

from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.services.tools.core.telemetry import _record_tool_call
from harness.workflow.chapter_brief import (
    LAYOUT_SYSTEM_BLOCK,
    NO_AI_SLOP_BLOCK,
    PROJECTION_READABILITY_BLOCK,
    get_chapter_brief,
    load_example_chapter_excerpt,
    load_motion_system_bundle,
    load_motion_system_summary,
    parse_article_refs_from_outline,
)
from harness.workflow.step_indexing import agent_rule_block


def _article_script_sections(
    state: VideoWorkflowState,
    *,
    chapter_id: str,
    chapter_index: int,
) -> tuple[list[str], str | None]:
    brief = get_chapter_brief(state, chapter_id, chapter_index)
    parts: list[str] = []

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
    return parts, script_excerpt or None


def read_chapter_context(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
    chapter_id: str,
    chapter_index: int = 1,
    chapter_title: str = "",
) -> str:
    """Tier-A context: article + script + excerpted 01-example + motion summary."""
    _record_tool_call(
        state,
        "read_chapter_context",
        {"chapter_id": chapter_id, "chapter_index": chapter_index},
        allowed=True,
        reason="Batch read article + 01-example excerpt + layout + motion summary",
    )

    title = chapter_title or chapter_id
    parts = [
        f"# Chapter context: {title} (`{chapter_id}`)",
        "",
    ]

    article_parts, _script = _article_script_sections(
        state, chapter_id=chapter_id, chapter_index=chapter_index,
    )
    parts.extend(article_parts)

    parts.append(load_example_chapter_excerpt(workspace_root))
    parts += ["", load_motion_system_summary(workspace_root)]

    mask = workspace_root / "presentation" / "src" / "components" / "MaskReveal.tsx"
    if mask.exists():
        parts += [
            "",
            "## MaskReveal (import from ../../components/MaskReveal)",
            "```",
            mask.read_text(encoding="utf-8", errors="replace")[:900],
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
        "## Global template classes (layouts.css / motion/ / animations.css — do NOT duplicate in index.css)",
        "lx-* typography & shells · mot-* motion presets · mask-reveal · in · rule-grow · "
        "scene-pad, masthead, kicker, hero-num, label-mono, rule, card, pull-quote, "
        "serif-cn, display-en, display-en-soft, dot-accent — use theme tokens `--t-*`, `--text`, `--accent`.",
        "",
        "## Optional detail tools (only if needed)",
        "- read_motion_detail() — full MOTION-SYSTEM.md + presets.css + animations.css",
        "- read_layout_catalog() — full LAYOUT-SYSTEM.md shell catalog",
        "",
        "## Do NOT read_file presentation/src/styles/* — use tools above instead.",
    ]
    return "\n".join(parts)


def read_motion_detail(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
) -> str:
    """Tier-B: full motion system reference."""
    _record_tool_call(
        state,
        "read_motion_detail",
        {},
        allowed=True,
        reason="On-demand full motion bundle",
    )
    return load_motion_system_bundle(workspace_root)


def read_layout_catalog(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
) -> str:
    """Tier-B: full layout shell catalog."""
    _record_tool_call(
        state,
        "read_layout_catalog",
        {},
        allowed=True,
        reason="On-demand LAYOUT-SYSTEM.md",
    )
    spec = workspace_root / "presentation" / "src" / "layouts" / "LAYOUT-SYSTEM.md"
    if not spec.is_file():
        return "MISSING: presentation/src/layouts/LAYOUT-SYSTEM.md — run scaffold."
    return (
        "## Layout Shell System (full catalog)\n\n"
        + spec.read_text(encoding="utf-8", errors="replace")[:12000]
    )
