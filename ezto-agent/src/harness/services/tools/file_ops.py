"""File read/write operations."""

from __future__ import annotations

from pathlib import Path

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


def read_file(
    state: VideoWorkflowState,
    path: str,
    *,
    max_bytes: int = 1_000_000,
) -> str:
    _record_tool_call(
        state, "read_file", {"path": path, "max_bytes": max_bytes},
        allowed=True, reason="File read for content inspection",
    )
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_file(
    state: VideoWorkflowState,
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
) -> str:
    _record_tool_call(
        state, "write_file", {"path": path},
        allowed=True, reason="File write for artifact generation",
    )
    full = Path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding=encoding)
    logger.info("Written %d chars to %s", len(content), path)
    return f"Written {len(content)} chars to {path}"
