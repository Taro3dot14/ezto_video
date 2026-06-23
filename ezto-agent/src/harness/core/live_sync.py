"""Push in-flight LangGraph state mutations to the thread store for SSE."""

from __future__ import annotations

from typing import Callable

from .state import VideoWorkflowState

_patch_handler: Callable[[str, dict], None] | None = None


def set_live_sync_handler(handler: Callable[[str, dict], None]) -> None:
    global _patch_handler
    _patch_handler = handler


def live_sync(state: VideoWorkflowState) -> None:
    """Mirror execution fields to WorkflowManager thread store."""
    if _patch_handler is None:
        return
    thread_id = state.get("thread_id")
    if not thread_id:
        return
    from .execution import derive_runtime

    runtime = derive_runtime(state)
    _patch_handler(
        thread_id,
        {
            "execution_trace": list(state.get("execution_trace", [])),
            "execution_revision": state.get("execution_revision", 0),
            **runtime,
        },
    )
