"""Tests for checkpoint approval routing."""

from __future__ import annotations

import pytest

from harness.workflow.builder import (
    route_batch_checkpoint,
    route_chapter_1_checkpoint,
    route_mode_a_checkpoint,
)
from harness.workflow.guards import PolicyViolation, guard_not_skip_checkpoint


def _state(**overrides) -> dict:
    base = {
        "user_confirmations": {},
        "current_chapter_index": 1,
        "total_chapters": 3,
        "artifact_paths": {"outline.md": "workspace/x/outline.md"},
        "workspace_root": "workspace/x",
    }
    base.update(overrides)
    return base


def test_chapter_1_reject_returns_build_chapter_1(monkeypatch):
    monkeypatch.setattr(
        "harness.workflow.builder.parse_outline_chapters",
        lambda _s: [{"id": "a"}, {"id": "b"}],
    )
    state = _state(
        user_confirmations={"checkpoint_chapter_1": {"approved": False, "feedback": "too dark"}},
    )
    assert route_chapter_1_checkpoint(state) == "wv_build_chapter_1"


def test_chapter_1_approve_routes_to_next_chapter(monkeypatch):
    monkeypatch.setattr(
        "harness.workflow.builder.parse_outline_chapters",
        lambda _s: [{"id": "a"}, {"id": "b"}],
    )
    state = _state(user_confirmations={"checkpoint_chapter_1": {"approved": True}})
    assert route_chapter_1_checkpoint(state) == "wv_build_chapter_n"


def test_chapter_1_approve_single_chapter_goes_phase3(monkeypatch):
    monkeypatch.setattr(
        "harness.workflow.builder.parse_outline_chapters",
        lambda _s: [{"id": "a"}],
    )
    state = _state(user_confirmations={"checkpoint_chapter_1": {"approved": True}})
    assert route_chapter_1_checkpoint(state) == "wv_transition_to_phase3"


def test_mode_a_reject_rebuilds_same_chapter():
    state = _state(
        current_chapter_index=2,
        user_confirmations={"checkpoint_chapter_n": {"approved": False, "feedback": "fix"}},
    )
    assert route_mode_a_checkpoint(state) == "wv_build_chapter_n"


def test_mode_a_approve_continues_when_more_chapters():
    state = _state(
        current_chapter_index=2,
        total_chapters=5,
        user_confirmations={"checkpoint_chapter_n": {"approved": True}},
    )
    assert route_mode_a_checkpoint(state) == "wv_build_chapter_n"


def test_mode_a_approve_finishes_at_last_chapter():
    state = _state(
        current_chapter_index=5,
        total_chapters=5,
        user_confirmations={"checkpoint_chapter_n": {"approved": True}},
    )
    assert route_mode_a_checkpoint(state) == "wv_transition_to_phase3"


def test_batch_reject_rebuilds():
    state = _state(
        user_confirmations={"checkpoint_remaining_batch": {"approved": False}},
    )
    assert route_batch_checkpoint(state) == "wv_build_chapter_n"


def test_guard_blocks_unapproved_chapter_1():
    state = _state(user_confirmations={"checkpoint_chapter_1": {"approved": False}})
    with pytest.raises(PolicyViolation, match="not approved"):
        guard_not_skip_checkpoint(state, "checkpoint_chapter_1")
