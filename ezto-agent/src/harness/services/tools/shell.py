"""Shell execution and scaffold log streaming."""

from __future__ import annotations

import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from backend.core.logger import logger
from harness.core.state import ToolCallRecord, VideoWorkflowState

_scaffold_logs: dict[str, list[str]] = {}
_scaffold_logs_lock = threading.Lock()


def _push_scaffold_log(thread_id: str, line: str) -> None:
    with _scaffold_logs_lock:
        _scaffold_logs.setdefault(thread_id, []).append(line)


def drain_scaffold_log(thread_id: str, seen: int = 0) -> tuple[list[str], int]:
    with _scaffold_logs_lock:
        lines = _scaffold_logs.get(thread_id, [])
    return lines[seen:], len(lines)


def _clear_scaffold_log(thread_id: str) -> None:
    with _scaffold_logs_lock:
        _scaffold_logs.pop(thread_id, None)


def _record_tool_call(
    state: VideoWorkflowState,
    tool_name: str,
    args: dict[str, Any],
    allowed: bool,
    reason: str,
) -> ToolCallRecord:
    record: ToolCallRecord = {
        "node": state.get("current_node", "unknown"),
        "tool": tool_name,
        "args": args,
        "allowed": allowed,
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    calls = state.get("tool_calls", [])
    calls.append(record)
    return record


def normalize_presentation_command(command: str) -> tuple[str, str | None]:
    """Strip presentation/ prefix when cwd is already presentation/."""
    if not re.search(r"(?:^|[\s;&|])presentation/", command):
        return command, None
    normalized = command
    if normalized.startswith("presentation/"):
        normalized = normalized[len("presentation/") :]
    normalized = re.sub(r"([\s;&|])presentation/", r"\1", normalized)
    return normalized, (
        "Note: stripped 'presentation/' prefix — run_shell cwd is already presentation/."
    )


def run_shell(
    state: VideoWorkflowState,
    command: str,
    *,
    cwd: str | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    _record_tool_call(
        state, "shell", {"command": command, "cwd": cwd, "timeout": timeout},
        allowed=True, reason="Shell command for workflow step",
    )
    return subprocess.run(
        command, shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
