"""SSE event streaming service."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Protocol


class WorkflowStateProvider(Protocol):
    def get_state(self, thread_id: str) -> dict | None: ...


async def event_generator(
    thread_id: str,
    service: WorkflowStateProvider,
    *,
    revision_from: int = 0,
    last_event_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for workflow state changes."""
    last_node_count = -1
    last_revision = max(0, revision_from)
    if last_event_id:
        try:
            last_revision = max(last_revision, int(last_event_id))
        except ValueError:
            pass
    last_pending_interrupt: dict | None = None
    last_current_node = ""
    last_token_revision = -1

    while True:
        state = service.get_state(thread_id)
        if state is None:
            yield f"event: error\ndata: {json.dumps({'message': 'workflow deleted'})}\n\n"
            break

        nodes = state.get("completed_nodes", [])
        revision = state.get("execution_revision", 0)
        trace = state.get("execution_trace", [])
        current_pi = state.get("pending_interrupt")

        if revision > last_revision:
            last_revision = revision
            yield (
                f"id: {revision}\n"
                f"event: trace\n"
                f"data: {json.dumps({'trace': trace, 'revision': revision}, ensure_ascii=False)}\n\n"
            )

        cn = state.get("current_node", "")
        cn_changed = cn != last_current_node
        pi_changed = current_pi and current_pi != last_pending_interrupt
        token_usage = state.get("token_usage") or {}
        token_rev = int(token_usage.get("revision", 0))
        token_changed = token_rev != last_token_revision
        if cn_changed or len(nodes) != last_node_count or pi_changed or token_changed:
            if cn_changed:
                last_current_node = cn
            last_node_count = len(nodes)
            if pi_changed:
                last_pending_interrupt = current_pi
            if token_changed:
                last_token_revision = token_rev
            event = {
                "type": "state_change",
                "current_phase": state.get("current_phase"),
                "current_node": cn,
                "completed_nodes": nodes,
                "pending_interrupt": state.get("pending_interrupt"),
                "final_summary": state.get("final_summary"),
                "token_usage": token_usage,
                "presentation_url": state.get("presentation_url"),
                "user_confirmations": state.get("user_confirmations"),
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if state.get("final_summary") is not None:
            yield (
                f"event: completed\n"
                f"data: {json.dumps({'summary': state['final_summary']})}\n\n"
            )
            break

        await asyncio.sleep(1)
