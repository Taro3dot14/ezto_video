"""Serialize workflow state for disk / API — strip LangGraph runtime fields."""

from __future__ import annotations

from typing import Any

# Large / ephemeral fields omitted from workflow_state.json
_SKIP_KEYS = frozenset({"tool_calls", "thinking_log"})


def state_for_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe subset of workflow state.

    LangGraph injects ``__interrupt__`` (tuple of ``Interrupt``) into streamed
    values at checkpoint nodes; those objects are not JSON-serializable.
    """
    return {
        k: v
        for k, v in state.items()
        if k not in _SKIP_KEYS and not (isinstance(k, str) and k.startswith("__"))
    }
