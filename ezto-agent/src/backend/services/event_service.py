"""SSE event streaming service."""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator

from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import drain_scaffold_log
from backend.services.workflow_service import WorkflowService


async def event_generator(
    thread_id: str,
    service: WorkflowService,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for workflow state changes."""
    last_node_count = -1
    last_think_count = 0
    last_pending_interrupt: dict | None = None
    last_scaffold_count = 0

    while True:
        state = service.get_state(thread_id)
        if state is None:
            yield f"event: error\ndata: {json.dumps({'message': 'workflow deleted'})}\n\n"
            break

        nodes = state.get("completed_nodes", [])
        thinking = state.get("thinking_log", [])
        current_pi = state.get("pending_interrupt")

        new_think = thinking[last_think_count:]
        if new_think:
            last_think_count = len(thinking)
            yield f"event: think\ndata: {json.dumps(new_think, ensure_ascii=False)}\n\n"

        new_scaffold, last_scaffold_count = drain_scaffold_log(thread_id, last_scaffold_count)
        if new_scaffold:
            scaffold_think = [
                {"type": "step", "content": line, "ts": time.time()}
                for line in new_scaffold
            ]
            yield f"event: think\ndata: {json.dumps(scaffold_think, ensure_ascii=False)}\n\n"

        pi_changed = current_pi and current_pi != last_pending_interrupt
        if len(nodes) != last_node_count or pi_changed:
            last_node_count = len(nodes)
            if pi_changed:
                last_pending_interrupt = current_pi
            event = {
                "type": "state_change",
                "current_phase": state.get("current_phase"),
                "current_node": state.get("current_node"),
                "completed_nodes": nodes,
                "pending_interrupt": state.get("pending_interrupt"),
                "final_summary": state.get("final_summary"),
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if state.get("final_summary") is not None:
            yield f"event: completed\ndata: {json.dumps({'summary': state['final_summary']})}\n\n"
            break

        await asyncio.sleep(1)
