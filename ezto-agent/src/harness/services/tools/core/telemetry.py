"""Workflow-level tool call audit — append to state.tool_calls."""

from __future__ import annotations

import time
from typing import Any

from harness.core.state import ToolCallRecord, VideoWorkflowState


def record_tool_call(
    state: VideoWorkflowState,
    tool_name: str,
    args: dict[str, Any],
    *,
    allowed: bool,
    reason: str,
) -> ToolCallRecord:
    """Record a capability invocation on workflow state (distinct from agent SSE audit)."""
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


# Backward-compatible alias used across service modules.
_record_tool_call = record_tool_call
