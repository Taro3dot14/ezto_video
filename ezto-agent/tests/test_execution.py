"""Tests for execution trace — single source of truth."""

from harness.core.execution import ExecutionTracker, derive_runtime, push_event


def _state() -> dict:
    return {
        "thread_id": "test-thread",
        "current_phase": "phase1",
        "execution_trace": [],
        "execution_revision": 0,
    }


def test_begin_end_step():
    state = _state()
    tracker = ExecutionTracker(state)
    step_id = tracker.begin("wv_identify_input")
    assert len(state["execution_trace"]) == 1
    assert state["execution_trace"][0]["status"] == "running"

    tracker.end(step_id)
    runtime = derive_runtime(state)
    assert runtime["current_node"] == ""
    assert runtime["completed_nodes"] == ["wv_identify_input"]


def test_running_node_derived():
    state = _state()
    tracker = ExecutionTracker(state)
    tracker.begin("wv_prepare_source_files")
    runtime = derive_runtime(state)
    assert runtime["current_node"] == "wv_prepare_source_files"
    assert runtime["completed_nodes"] == []


def test_push_event_to_running_step():
    state = _state()
    tracker = ExecutionTracker(state)
    tracker.begin("wv_build_chapter_1")
    push_event(state, "step", "Agent thinking")
    assert state["execution_trace"][0]["events"][-1]["content"] == "Agent thinking"


def test_push_event_with_agent():
    state = _state()
    tracker = ExecutionTracker(state)
    tracker.begin("wv_build_chapter_1")
    push_event(state, "step", "⚡ read_chapter_context → 1200 chars", agent="builder")
    ev = state["execution_trace"][0]["events"][-1]
    assert ev["agent"] == "builder"


def test_validation_group_metadata():
    state = _state()
    tracker = ExecutionTracker(state)
    tracker.begin("wv_validate_script")
    step = state["execution_trace"][0]
    assert step["group"] == "script"
    assert step["events"][0]["type"] == "phase"
