"""Batch-read workspace source documents (script + outline)."""

from __future__ import annotations

from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.services.tools.fs.file_ops import read_file_with_header
from harness.services.tools.core.telemetry import _record_tool_call

_SOURCE_FILES = ("script.md", "outline.md")


def read_source_docs(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
) -> str:
    """Read script.md and outline.md in one call."""
    _record_tool_call(
        state,
        "read_source_docs",
        {},
        allowed=True,
        reason="Batch read script.md and outline.md",
    )
    parts: list[str] = []
    for name in _SOURCE_FILES:
        path = workspace_root / name
        if not path.exists():
            parts.append(f"--- {name} ---\nERROR: file not found at {path}")
            continue
        parts.append(read_file_with_header(state, str(path)))
    return "\n\n".join(parts)
