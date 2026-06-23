"""Report missing chapter assets into workflow state."""

from __future__ import annotations

from typing import Any

from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


def report_missing_assets(
    state: VideoWorkflowState,
    *,
    chapter_id: str,
    items: list[str] | None = None,
    note: str = "",
) -> str:
    """Record assets still missing for a chapter (empty items = explicitly none)."""
    lines = [str(i).strip() for i in (items or []) if str(i).strip()]
    entry = {
        "items": lines,
        "note": note.strip(),
    }
    bucket = state.setdefault("chapter_missing_assets", {})
    if not isinstance(bucket, dict):
        bucket = {}
        state["chapter_missing_assets"] = bucket
    bucket[chapter_id] = entry

    _record_tool_call(
        state,
        "report_missing_assets",
        {"chapter_id": chapter_id, "items": lines, "note": note},
        allowed=True,
        reason="Chapter delivery missing-assets disclosure",
    )

    if lines:
        preview = "; ".join(lines[:5])
        extra = f" (+{len(lines) - 5} more)" if len(lines) > 5 else ""
        body = f"本章还缺这些素材: {preview}{extra}"
    else:
        body = "本章无缺失素材（已显式确认）"
    if note.strip():
        body += f"\n备注: {note.strip()}"
    return f"✅ 已写入 state.chapter_missing_assets[{chapter_id}]\n{body}"


def get_missing_assets(state: VideoWorkflowState, chapter_id: str) -> dict[str, Any] | None:
    bucket = state.get("chapter_missing_assets")
    if not isinstance(bucket, dict):
        return None
    entry = bucket.get(chapter_id)
    return entry if isinstance(entry, dict) else None


def format_missing_assets_for_user(state: VideoWorkflowState, chapter_id: str) -> str | None:
    entry = get_missing_assets(state, chapter_id)
    if not entry:
        return None
    items = entry.get("items") or []
    note = entry.get("note") or ""
    if not items and not note:
        return "本章素材已齐全（Reviewer 已确认）"
    lines = ["## 本章还缺这些素材"]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- （无具体条目）")
    if note:
        lines.append(f"\n{note}")
    return "\n".join(lines)
