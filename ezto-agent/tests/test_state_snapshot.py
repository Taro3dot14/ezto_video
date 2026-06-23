"""Tests for workflow state snapshot sanitization."""

from __future__ import annotations

import json

from langgraph.types import Interrupt

from harness.core.state_snapshot import state_for_snapshot


def test_state_for_snapshot_strips_langgraph_interrupt():
    state = {
        "thread_id": "t1",
        "current_node": "wv_checkpoint_chapter_1",
        "__interrupt__": (Interrupt(value={"type": "checkpoint_chapter_1"}, id="abc"),),
        "execution_trace": [],
    }
    snap = state_for_snapshot(state)
    assert "__interrupt__" not in snap
    assert snap["thread_id"] == "t1"
    json.dumps(snap, ensure_ascii=False)


def test_state_for_snapshot_omits_ephemeral_fields():
    state = {
        "thread_id": "t1",
        "tool_calls": [{"node": "x"}],
        "thinking_log": [{"type": "step"}],
    }
    snap = state_for_snapshot(state)
    assert "tool_calls" not in snap
    assert "thinking_log" not in snap
