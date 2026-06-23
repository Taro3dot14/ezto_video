"""Execution trace — single source of truth for workflow progress UI."""

from __future__ import annotations

import time
from typing import Any, Literal

from harness.workflow.node_catalog import TOTAL_NODES, display_label, display_label_for_state, meta

from .live_sync import live_sync
from .state import VideoWorkflowState

StepStatus = Literal["running", "completed", "failed"]


def derive_runtime(state: VideoWorkflowState) -> dict[str, Any]:
    """Derive API/UI fields from execution_trace (never store separately)."""
    trace: list[dict] = state.get("execution_trace", [])
    running = next((s for s in reversed(trace) if s.get("status") == "running"), None)

    completed_nodes: list[str] = []
    for step in trace:
        if step.get("status") == "completed":
            node_id = step.get("node_id", "")
            if not completed_nodes or completed_nodes[-1] != node_id:
                completed_nodes.append(node_id)

    phase = running.get("phase") if running else state.get("current_phase", "phase1")
    if not running and trace:
        last = trace[-1]
        if last.get("status") == "completed":
            phase = last.get("phase", phase)

    current_node = ""
    if running:
        current_node = running.get("node_id", "")
    elif state.get("paused_at_node"):
        current_node = state["paused_at_node"]
    else:
        for step in reversed(trace):
            if step.get("status") == "running":
                current_node = step.get("node_id", "")
                break
        if not current_node and trace:
            current_node = trace[-1].get("node_id", "")

    return {
        "current_node": current_node,
        "completed_nodes": completed_nodes,
        "current_phase": phase,
    }


class ExecutionTracker:
    """Mutate execution_trace on state; sync live to thread store."""

    def __init__(self, state: VideoWorkflowState):
        self._state = state
        self._trace: list[dict] = state.setdefault("execution_trace", [])
        self._active_id: str | None = None

    @property
    def active_step_id(self) -> str | None:
        return self._active_id

    def _bump(self) -> None:
        self._state["execution_revision"] = self._state.get("execution_revision", 0) + 1
        live_sync(self._state)

    def begin(self, node_id: str, *, label: str | None = None) -> str:
        m = meta(node_id)
        phase = m.get("phase", "phase1")
        self._state["current_phase"] = phase

        step_id = f"{node_id}:{len(self._trace)}"
        group = m.get("group")
        events: list[dict] = []
        if group:
            events.append({
                "type": "phase",
                "content": f"▸ {m['label']}",
                "ts": time.time(),
            })

        step = {
            "id": step_id,
            "node_id": node_id,
            "label": label or display_label_for_state(node_id, self._state),
            "phase": phase,
            "status": "running",
            "group": group,
            "started_at": time.time(),
            "ended_at": None,
            "events": events,
        }
        self._trace.append(step)
        self._active_id = step_id
        self._bump()
        return step_id

    def end(self, step_id: str, *, status: StepStatus = "completed") -> None:
        for step in self._trace:
            if step.get("id") == step_id:
                step["status"] = status
                step["ended_at"] = time.time()
                break
        if self._active_id == step_id:
            self._active_id = None
        self._bump()

    def add_events(self, events: list[dict]) -> None:
        if not events:
            return
        step = self._running_step()
        if step is None:
            return
        step["events"].extend(events)
        self._bump()

    def push_event(self, type_: str, content: str, *, agent: str | None = None) -> None:
        step = self._running_step()
        if step is None:
            return
        event: dict[str, Any] = {"type": type_, "content": content, "ts": time.time()}
        if agent:
            event["agent"] = agent
        step["events"].append(event)
        self._bump()

    def fail(self, step_id: str, message: str) -> None:
        for step in self._trace:
            if step.get("id") == step_id:
                step["events"].append({"type": "error", "content": message, "ts": time.time()})
                break
        self.end(step_id, status="failed")

    def _running_step(self) -> dict | None:
        if self._active_id:
            for step in self._trace:
                if step.get("id") == self._active_id:
                    return step
        return next((s for s in reversed(self._trace) if s.get("status") == "running"), None)


def push_event(state: VideoWorkflowState, type_: str, content: str, *, agent: str | None = None) -> None:
    """Append a sub-event to the active step (agent loop, scaffold, etc.)."""
    ExecutionTracker(state).push_event(type_, content, agent=agent)


def total_node_count() -> int:
    return TOTAL_NODES
