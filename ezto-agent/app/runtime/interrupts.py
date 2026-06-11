"""Checkpoint interrupt helpers.

Maps the original SKILL.md "must stop" / "hard checkpoint" points to
LangGraph interrupt() calls. Each checkpoint has a typed payload that
preserves the original skill's semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt

# Module-level storage for the last interrupt payload.
# Set before interrupt() raises GraphInterrupt; consumed after astream loop.
_LAST_INTERRUPT_PAYLOAD: dict | None = None


def set_interrupt_node(node_name: str) -> None:
    """Attach the running node name to the stored interrupt payload."""
    global _LAST_INTERRUPT_PAYLOAD
    if _LAST_INTERRUPT_PAYLOAD is not None:
        _LAST_INTERRUPT_PAYLOAD["node"] = node_name


def pop_last_interrupt_payload() -> dict | None:
    """Return and clear the stored interrupt payload."""
    global _LAST_INTERRUPT_PAYLOAD
    data = _LAST_INTERRUPT_PAYLOAD
    _LAST_INTERRUPT_PAYLOAD = None
    return data


def _store_and_interrupt(payload: dict) -> Any:
    """Store payload, then call interrupt().

    On first call (new interrupt), interrupt() raises GraphInterrupt and
    the payload remains stored for pop_last_interrupt_payload() to read
    after the astream loop.

    On resume, interrupt() returns the resume value and we clear the
    stale payload so pop_last_interrupt_payload() correctly returns None.
    """
    global _LAST_INTERRUPT_PAYLOAD
    _LAST_INTERRUPT_PAYLOAD = payload
    try:
        result = interrupt(payload)
        # Resume path: interrupt() returned normally
        _LAST_INTERRUPT_PAYLOAD = None
        return result
    except GraphInterrupt:
        # First-call path: payload stays stored for detection
        raise

from .state import VideoWorkflowState

# ── Payload type discriminators ──

CheckpointType = Literal[
    "checkpoint_plan",
    "checkpoint_chapter_1",
    "checkpoint_chapter_n",
    "checkpoint_remaining_batch",
    "checkpoint_audio",
    "checkpoint_audio_segments",
]


def checkpoint_plan(
    state: VideoWorkflowState,
    theme_recommendations: list[dict],
    material_list: list[str],
) -> dict:
    """Checkpoint Plan — one-shot align 5 things with the user.

    Original SKILL.md semantics (must not be split into multiple questions):
      1. script.md — any changes?
      2. outline.md — any changes?
      3. Theme selection (with recommendations)
      4. Material / asset preparation plan
      5. Development mode A/B/C

    Returns user_confirmations dict to merge into state.
    """
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_plan",
            "description": "一次对齐 5 件事：稿子 / outline / 主题 / 素材 / 开发模式",
            "files": {
                "script": _rel_path(state, "script.md"),
                "outline": _rel_path(state, "outline.md"),
            },
            "must_confirm": [
                "script",
                "outline",
                "theme",
                "materials",
                "development_mode",
            ],
            "theme_recommendations": theme_recommendations,
            "material_list": material_list,
            "development_modes": {
                "A": "逐章确认（默认，推荐）",
                "B": "第 1 章后顺序开发，统一验收",
                "C": "第 1 章后并行开发（subagent）",
            },
        }
    )
    return _ensure_confirmations(response, "checkpoint_plan")


def _preview_url(state: VideoWorkflowState, chapter_index: int) -> str | None:
    """Build a preview URL pointing to a specific chapter (0-indexed)."""
    base = state.get("presentation_url")
    if not base:
        return None
    return f"{base}?chapter={chapter_index}"


def checkpoint_chapter_1(state: VideoWorkflowState) -> dict:
    """Chapter 1 mandatory acceptance checkpoint.

    Original semantics: chapter 1 is the style anchor and must be reviewed
    by the user before remaining chapters are built.
    """
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_chapter_1",
            "description": "第 1 章强制验收 — 风格锚点，不可跳过",
            "chapter_id": _chapter_1_id(state),
            "preview_url": _preview_url(state, 0),
            "checklist": [
                "视觉气质是否符合选定主题？",
                "节奏是否合适？信息密度是否恰当？",
                "内容驱动动画是否到位？",
                "双源原则：画面是否回了原文章抽细节？",
                "反 AI 味：有无紫粉渐变 / 圆角彩色边框 / emoji / 假数据？",
            ],
        }
    )
    return _ensure_confirmations(response, "checkpoint_chapter_1")


def checkpoint_chapter_n(state: VideoWorkflowState, chapter_index: int) -> dict:
    """Per-chapter acceptance (Mode A)."""
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_chapter_n",
            "description": f"第 {chapter_index} 章验收",
            "chapter_index": chapter_index,
            "preview_url": _preview_url(state, chapter_index - 1),
        }
    )
    return _ensure_confirmations(response, "checkpoint_chapter_n")


def checkpoint_remaining_batch(
    state: VideoWorkflowState, chapter_indices: list[int]
) -> dict:
    """Batch acceptance for remaining chapters (Modes B & C)."""
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_remaining_batch",
            "description": f"第 {chapter_indices[0]}~{chapter_indices[-1]} 章批量验收",
            "chapter_indices": chapter_indices,
            "preview_url": _preview_url(state, chapter_indices[0] - 1),
        }
    )
    return _ensure_confirmations(response, "checkpoint_remaining_batch")


def checkpoint_audio(state: VideoWorkflowState) -> dict:
    """Checkpoint Audio — ask if the user wants narration synthesis."""
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_audio",
            "description": "网页已完成，是否合成口播音频？",
            "context": {
                "total_chapters": _count_chapters(state),
                "total_steps": _count_steps(state),
            },
            "options": {
                "yes": "合成音频 → 扫 narrations.ts → audio-segments.json → TTS",
                "no": "跳过 Phase 3，直接到录屏指引",
            },
        }
    )
    return _ensure_confirmations(response, "checkpoint_audio")


def checkpoint_audio_segments(state: VideoWorkflowState) -> dict:
    """Review generated audio-segments.json before synthesis."""
    response: dict[str, Any] = _store_and_interrupt(
        {
            "type": "checkpoint_audio_segments",
            "description": "请检查 audio-segments.json 中的文本是否正确",
            "path": state["artifact_paths"].get("audio-segments.json"),
        }
    )
    return _ensure_confirmations(response, "checkpoint_audio_segments")


# ── Internal helpers ──


def _ensure_confirmations(response: dict, key: str) -> dict:
    """Wrap interrupt response into user_confirmations update."""
    return {"user_confirmations": {key: response}}


def _chapter_1_id(state: VideoWorkflowState) -> str | None:
    """Extract chapter-1 id from outline if available."""
    path = state["artifact_paths"].get("outline.md")
    if not path:
        return None
    return "chapter_1"  # placeholder; real impl reads from outline


def _rel_path(state: VideoWorkflowState, logical: str) -> str | None:
    """Convert an artifact absolute path to relative (for the readArtifact API)."""
    abspath = state.get("artifact_paths", {}).get(logical)
    if not abspath:
        return None
    ws = state.get("workspace_root", "workspace")
    prefix = ws + "/"
    if abspath.startswith(prefix):
        return abspath[len(prefix):]
    return abspath


def _count_chapters(state: VideoWorkflowState) -> int:
    path = state["artifact_paths"].get("outline.md")
    if not path:
        return 0
    return 0  # placeholder


def _count_steps(state: VideoWorkflowState) -> int:
    return 0  # placeholder
