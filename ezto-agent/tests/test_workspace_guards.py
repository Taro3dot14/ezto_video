"""Tests for workspace readiness helpers."""

from __future__ import annotations

from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.workflow.guards import ensure_artifact_parent, ensure_workspace_ready, init_workspace


def test_ensure_workspace_ready_recreates_missing_dir(tmp_path: Path):
    state: VideoWorkflowState = {
        "thread_id": "abc-123",
        "workspace_root": str(tmp_path / "workspace"),
        "artifact_paths": {
            "script.md": str(tmp_path / "workspace" / "abc-123" / "script.md"),
        },
    }
    update = ensure_workspace_ready(state)
    assert Path(update["workspace_root"]).is_dir()
    assert update["artifact_paths"]["script.md"].endswith("script.md")


def test_ensure_artifact_parent_creates_nested_dir(tmp_path: Path):
    path = tmp_path / "nested" / "dir" / "script.md"
    ensure_artifact_parent(path).write_text("hello", encoding="utf-8")
    assert path.read_text(encoding="utf-8") == "hello"


def test_init_workspace_sets_artifact_paths(tmp_path: Path):
    state: VideoWorkflowState = {
        "thread_id": "tid-1",
        "workspace_root": str(tmp_path / "workspace"),
    }
    update = init_workspace(state)
    ws = Path(update["workspace_root"])
    assert ws.is_dir()
    assert Path(update["artifact_paths"]["script.md"]) == ws / "script.md"
