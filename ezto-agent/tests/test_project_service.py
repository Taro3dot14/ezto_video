"""Tests for project management service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.project_service import ProjectService, PROJECT_META_FILE


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspace"


@pytest.fixture
def svc(workspace: Path) -> ProjectService:
    workspace.mkdir()
    return ProjectService(str(workspace))


def test_ensure_meta_creates_project_json(svc: ProjectService, workspace: Path):
    meta = svc.ensure_meta(
        "abc-123",
        user_request="测试文章标题\n第二行",
        input_type="article",
    )
    assert meta["id"] == "abc-123"
    assert meta["name"] == "测试文章标题"
    assert (workspace / "abc-123" / PROJECT_META_FILE).exists()


def test_list_projects_infers_legacy_dirs(svc: ProjectService, workspace: Path):
    (workspace / "legacy-id").mkdir()
    (workspace / "legacy-id" / "script.md").write_text("# script", encoding="utf-8")

    projects = svc.list_projects()
    assert len(projects) == 1
    assert projects[0]["id"] == "legacy-id"
    assert projects[0]["status"] == "in_progress"
    assert projects[0]["artifact_count"] >= 1


def test_rename_project(svc: ProjectService, workspace: Path):
    svc.ensure_meta("p1", user_request="hello")
    updated = svc.rename_project("p1", "我的演示项目")
    assert updated["name"] == "我的演示项目"

    meta = json.loads((workspace / "p1" / PROJECT_META_FILE).read_text(encoding="utf-8"))
    assert meta["name"] == "我的演示项目"


def test_rename_empty_name_raises(svc: ProjectService):
    svc.ensure_meta("p1")
    with pytest.raises(ValueError, match="不能为空"):
        svc.rename_project("p1", "   ")


def test_scan_and_read_artifacts(svc: ProjectService, workspace: Path):
    svc.ensure_meta("p1")
    script = workspace / "p1" / "script.md"
    script.write_text("hello script", encoding="utf-8")

    artifacts = svc.scan_disk_artifacts("p1")
    script_art = next(a for a in artifacts if a["logical_name"] == "script.md")
    assert script_art["exists"] is True

    content, path = svc.read_artifact("p1", "script.md")
    assert content == "hello script"
    assert path == "script.md"


def test_completed_status_with_presentation(svc: ProjectService, workspace: Path):
    svc.ensure_meta("p1")
    pres = workspace / "p1" / "presentation"
    pres.mkdir()
    (pres / "package.json").write_text("{}", encoding="utf-8")

    project = svc.get_project("p1")
    assert project is not None
    assert project["status"] == "completed"


def test_save_and_load_state_snapshot(svc: ProjectService, workspace: Path):
    svc.ensure_meta("p1")
    state = {"thread_id": "p1", "final_summary": "done", "completed_nodes": ["a"]}
    svc.save_state_snapshot("p1", state)

    loaded = svc.load_state_snapshot("p1")
    assert loaded is not None
    assert loaded["final_summary"] == "done"

    project = svc.get_project("p1")
    assert project is not None
    assert project["status"] == "completed"


def test_save_state_snapshot_with_langgraph_interrupt(svc: ProjectService, workspace: Path):
    from langgraph.types import Interrupt

    svc.ensure_meta("p1")
    state = {
        "thread_id": "p1",
        "completed_nodes": ["wv_build_chapter_1"],
        "__interrupt__": (Interrupt(value={"type": "checkpoint_chapter_1"}, id="x"),),
    }
    svc.save_state_snapshot("p1", state)
    loaded = svc.load_state_snapshot("p1")
    assert loaded is not None
    assert "__interrupt__" not in loaded
    assert loaded["thread_id"] == "p1"


def test_delete_project(svc: ProjectService, workspace: Path):
    svc.ensure_meta("p1", user_request="to delete")
    (workspace / "p1" / "script.md").write_text("x", encoding="utf-8")

    meta = svc.delete_project("p1")
    assert meta["name"] == "to delete"
    assert not (workspace / "p1").exists()


def test_delete_missing_raises(svc: ProjectService):
    with pytest.raises(FileNotFoundError):
        svc.delete_project("missing-id")


def test_bootstrap_workspace_backfills_legacy(svc: ProjectService, workspace: Path):
    legacy = workspace / "legacy-id"
    legacy.mkdir()
    (legacy / "article.md").write_text("# 我的测试文章\n正文", encoding="utf-8")

    created = svc.bootstrap_workspace()
    assert created == 1
    meta = json.loads((legacy / PROJECT_META_FILE).read_text(encoding="utf-8"))
    assert meta["name"] == "我的测试文章"
    assert meta["user_request"].startswith("# 我的测试文章")
