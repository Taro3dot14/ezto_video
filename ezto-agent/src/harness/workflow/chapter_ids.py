"""Resolve presentation chapter folder ids (outline slug vs LLM 'chapter_1')."""

from __future__ import annotations

import re
from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.workflow.chapter_brief import parse_outline_chapters_from_state

_CHAPTER_INDEX_RE = re.compile(r"^chapter_(\d+)$", re.I)


def chapter_dir(workspace_root: Path, chapter_id: str) -> Path:
    return workspace_root / "presentation" / "src" / "chapters" / chapter_id


def chapter_exists(workspace_root: Path, chapter_id: str) -> bool:
    ch = chapter_dir(workspace_root, chapter_id)
    return ch.is_dir() and (ch / "index.tsx").exists()


def resolve_chapter_id(
    state: VideoWorkflowState,
    requested: str | None,
    *,
    default: str,
) -> tuple[str, str | None]:
    """Return (resolved_id, warning_message).

    Maps mistaken ``chapter_1`` → outline slug (e.g. ``human-agent-teams``) when that folder exists.
    """
    raw = (requested or default).strip() or default
    ws = Path(state.get("workspace_root", "."))

    if chapter_exists(ws, raw):
        return raw, None

    m = _CHAPTER_INDEX_RE.match(raw)
    if m:
        chapters = parse_outline_chapters_from_state(state)
        idx = int(m.group(1)) - 1
        if chapters and 0 <= idx < len(chapters):
            mapped = chapters[idx]["id"]
            if chapter_exists(ws, mapped):
                return mapped, (
                    f"⚠️ 章节目录是 `{mapped}`，不是 `{raw}`。"
                    f"已自动改用 `{mapped}`。"
                )

    if raw != default and chapter_exists(ws, default):
        return default, (
            f"⚠️ 未找到 `{raw}`，已改用当前章节 `{default}`。"
        )

    return raw, None
