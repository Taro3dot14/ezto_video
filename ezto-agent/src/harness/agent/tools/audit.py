"""Push structured tool execution records to workflow execution trace."""

from __future__ import annotations

import json
from typing import Any

from harness.core.execution import push_event
from harness.core.state import VideoWorkflowState

from .result import ToolExecutionRecord


def push_tool_audit(
    state: VideoWorkflowState | dict[str, Any] | None,
    record: ToolExecutionRecord,
    *,
    agent: str | None = None,
) -> None:
    """Append a structured tool audit event to the active execution step."""
    if state is None or not isinstance(state, dict):
        return
    payload = {
        "tool": record.tool_name,
        "code": record.code.value,
        "blocked": record.blocked,
        "done": record.done,
        "ms": record.duration_ms,
        "chars": record.output_chars,
    }
    push_event(state, "tool", json.dumps(payload, ensure_ascii=False), agent=agent)
