"""FastAPI routes for the workflow API."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.core.logger import logger, log_api_request
from backend.services.event_service import event_generator

from .models import (
    ArtifactInfo,
    ErrorResponse,
    ProjectDetail,
    ProjectSummary,
    RenameProjectRequest,
    DeleteProjectResponse,
    ResumeRequest,
    StartRequest,
    StartWorkflowResponse,
    ResumeWorkflowResponse,
    PauseWorkflowResponse,
    ContinueWorkflowResponse,
    ThemeInfo,
    WorkflowStateResponse,
)
from backend.services.workflow_service import WorkflowManager
from backend.services.project_service import ProjectService
from harness.core.execution import derive_runtime, total_node_count

router = APIRouter(prefix="/api")

# Shared manager instance (set by server.py on startup)
_manager: WorkflowManager | None = None
_project_service: ProjectService | None = None


def get_manager() -> WorkflowManager:
    assert _manager is not None, "WorkflowManager not initialized"
    return _manager


def get_project_service() -> ProjectService:
    assert _project_service is not None, "ProjectService not initialized"
    return _project_service


def set_manager(m: WorkflowManager) -> None:
    global _manager
    _manager = m


def set_project_service(s: ProjectService) -> None:
    global _project_service
    _project_service = s


# Helper to read file content with path traversal protection
import os
from pathlib import Path


def _safe_read_artifact(workspace_root: str, relative_path: str) -> str:
    """Read an artifact file, preventing path traversal."""
    full = Path(workspace_root).resolve() / relative_path
    full = full.resolve()
    if not str(full).startswith(str(Path(workspace_root).resolve())):
        raise HTTPException(403, detail="Path traversal denied")
    if not full.exists():
        raise HTTPException(404, detail="File not found")
    return full.read_text(encoding="utf-8", errors="replace")


# ── Endpoints ──


@router.post(
    "/workflow/start",
    response_model=StartWorkflowResponse,
    responses={400: {"model": ErrorResponse}},
)
async def start_workflow(req: StartRequest):
    """Start a new web-video-presentation workflow."""
    if not req.user_request.strip():
        raise HTTPException(400, detail="user_request must not be empty")

    t0 = time.perf_counter()
    mgr = get_manager()
    thread_id, state = await mgr.start_workflow(
        user_request=req.user_request,
        language=req.language,
        input_type=req.input_type,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    log_api_request("POST", "/workflow/start", 200, elapsed)
    logger.info("Workflow started thread=%s input_type=%s len=%d",
                thread_id, state.get("input_type"), len(req.user_request))

    return StartWorkflowResponse(
        thread_id=thread_id,
        state=_state_to_response(state),
    )


@router.post(
    "/workflow/{thread_id}/resume",
    response_model=ResumeWorkflowResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def resume_workflow(thread_id: str, req: ResumeRequest):
    """Resume an interrupted workflow with user confirmations."""
    t0 = time.perf_counter()
    mgr = get_manager()

    if mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    logger.info("Resume workflow=%s confirm_keys=%s",
                thread_id, list(req.confirmations.keys()))
    try:
        state = await mgr.resume_workflow(thread_id, req.confirmations)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    elapsed = (time.perf_counter() - t0) * 1000
    log_api_request("POST", f"/workflow/{thread_id}/resume", 200, elapsed)
    return ResumeWorkflowResponse(
        thread_id=thread_id,
        state=_state_to_response(state),
    )


@router.post(
    "/workflow/{thread_id}/pause",
    response_model=PauseWorkflowResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def pause_workflow(thread_id: str):
    """Pause a running workflow by cancelling the background graph task."""
    t0 = time.perf_counter()
    mgr = get_manager()

    if mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    try:
        state = await mgr.pause_workflow(thread_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    elapsed = (time.perf_counter() - t0) * 1000
    log_api_request("POST", f"/workflow/{thread_id}/pause", 200, elapsed)
    return PauseWorkflowResponse(
        thread_id=thread_id,
        state=_state_to_response(state),
    )


@router.post(
    "/workflow/{thread_id}/continue",
    response_model=ContinueWorkflowResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def continue_workflow(thread_id: str):
    """Continue a paused workflow from the LangGraph checkpoint."""
    t0 = time.perf_counter()
    mgr = get_manager()

    if mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    try:
        state = await mgr.continue_workflow(thread_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    elapsed = (time.perf_counter() - t0) * 1000
    log_api_request("POST", f"/workflow/{thread_id}/continue", 200, elapsed)
    return ContinueWorkflowResponse(
        thread_id=thread_id,
        state=_state_to_response(state),
    )


@router.get(
    "/workflow/{thread_id}",
    response_model=WorkflowStateResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_workflow_state(thread_id: str):
    """Get the current state of a workflow."""
    mgr = get_manager()
    state = mgr.get_state(thread_id)
    if state is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    return _state_to_response(state)


@router.get(
    "/workflow/{thread_id}/events",
    responses={404: {"model": ErrorResponse}},
)
async def workflow_events(
    thread_id: str,
    request: Request,
    from_: int = Query(0, alias="from", ge=0),
):
    """SSE event stream for workflow state changes."""
    mgr = get_manager()
    if mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    return StreamingResponse(
        event_generator(
            thread_id,
            mgr,
            revision_from=from_,
            last_event_id=request.headers.get("last-event-id"),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/workflow/{thread_id}/artifacts",
    responses={404: {"model": ErrorResponse}},
)
async def list_artifacts(thread_id: str):
    """List all artifact files for a workflow."""
    mgr = get_manager()
    artifacts = mgr.get_artifacts(thread_id)
    if not artifacts and mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")
    return {"artifacts": artifacts}


@router.get(
    "/workflow/{thread_id}/artifact/{path:path}",
    responses={404: {"model": ErrorResponse}},
)
async def read_artifact(thread_id: str, path: str):
    """Read an artifact file content."""
    mgr = get_manager()
    state = mgr.get_state(thread_id)
    if state is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    workspace = state.get("workspace_root", "")
    content = _safe_read_artifact(workspace, path)
    return {"content": content, "path": path}


@router.get("/themes", response_model=list[ThemeInfo])
async def list_themes():
    """List all available presentation themes."""
    mgr = get_manager()
    themes = mgr.list_themes()
    return [ThemeInfo(**t) for t in themes]


# ── Project management ──


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects():
    """List all workspace projects (historical + active)."""
    mgr = get_manager()
    svc = get_project_service()
    active_ids = mgr.active_thread_ids()
    rows = svc.list_projects(active_ids)
    return [ProjectSummary(**{k: v for k, v in r.items() if k != "user_request"}) for r in rows]


@router.get(
    "/projects/{project_id}",
    response_model=ProjectDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_project(project_id: str):
    """Get project metadata and disk artifacts."""
    mgr = get_manager()
    svc = get_project_service()
    active = project_id in mgr.active_thread_ids()
    project = svc.get_project(project_id, active=active)
    if project is None:
        raise HTTPException(404, detail=f"Project {project_id} not found")
    return ProjectDetail(
        **{k: v for k, v in project.items() if k != "artifacts"},
        artifacts=[ArtifactInfo(**a) for a in project["artifacts"]],
    )


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectSummary,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def rename_project(project_id: str, req: RenameProjectRequest):
    """Rename a project."""
    mgr = get_manager()
    svc = get_project_service()
    try:
        meta = svc.rename_project(project_id, req.name)
    except FileNotFoundError:
        raise HTTPException(404, detail=f"Project {project_id} not found")
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    active = project_id in mgr.active_thread_ids()
    row = svc.get_project(project_id, active=active) or meta
    return ProjectSummary(
        id=row["id"],
        name=row["name"],
        status=row.get("status", "empty"),
        artifact_count=row.get("artifact_count", 0),
        is_active=active,
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
        input_type=row.get("input_type"),
    )


@router.delete(
    "/projects/{project_id}",
    response_model=DeleteProjectResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def delete_project(project_id: str):
    """Delete a project workspace and drop any in-memory workflow."""
    mgr = get_manager()
    svc = get_project_service()
    try:
        meta = svc.get_project(project_id)
        if meta is None:
            raise FileNotFoundError(f"Project {project_id} not found")
        await mgr.remove_workflow(project_id)
        svc.delete_project(project_id)
    except FileNotFoundError:
        raise HTTPException(404, detail=f"Project {project_id} not found")
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except OSError as e:
        raise HTTPException(500, detail=f"Failed to delete project: {e}")

    log_api_request("DELETE", f"/projects/{project_id}", 200, 0)
    return DeleteProjectResponse(id=project_id, name=meta.get("name", ""))


@router.get(
    "/projects/{project_id}/artifacts",
    responses={404: {"model": ErrorResponse}},
)
async def list_project_artifacts(project_id: str):
    """List artifact files for a project (disk scan)."""
    svc = get_project_service()
    if not svc.project_dir(project_id).is_dir():
        raise HTTPException(404, detail=f"Project {project_id} not found")
    artifacts = svc.scan_disk_artifacts(project_id)
    return {"artifacts": artifacts}


@router.get(
    "/projects/{project_id}/artifact/{path:path}",
    responses={404: {"model": ErrorResponse}},
)
async def read_project_artifact(project_id: str, path: str):
    """Read a project artifact from disk."""
    svc = get_project_service()
    try:
        content, resolved = svc.read_artifact(project_id, path)
    except FileNotFoundError:
        raise HTTPException(404, detail=f"Artifact not found: {path}")
    except PermissionError:
        raise HTTPException(403, detail="Path traversal denied")
    return {"content": content, "path": resolved}


# ── Internal ──


def _state_to_response(state: VideoWorkflowState) -> WorkflowStateResponse:
    """Convert internal state to API response."""
    from harness.core.state import VideoWorkflowState

    artifacts = []
    for logical, path in state.get("artifact_paths", {}).items():
        p = Path(path) if path else None
        artifacts.append(
            ArtifactInfo(
                logical_name=logical,
                path=str(path) if path else "",
                exists=p.exists() if p else False,
                size=p.stat().st_size if p and p.exists() else None,
            )
        )

    runtime = derive_runtime(state)

    return WorkflowStateResponse(
        thread_id=state.get("thread_id", ""),
        current_phase=runtime["current_phase"],
        current_node=runtime["current_node"],
        completed_nodes=runtime["completed_nodes"],
        execution_trace=state.get("execution_trace", []),
        execution_revision=state.get("execution_revision", 0),
        total_nodes=total_node_count(),
        token_usage=state.get("token_usage") or {},
        thinking_log=[],
        pending_interrupt=state.get("pending_interrupt"),
        errors=state.get("errors", []),
        artifacts=artifacts,
        selected_theme=state.get("selected_theme"),
        selected_mode=state.get("selected_mode"),
        final_summary=state.get("final_summary"),
        repair_history=state.get("repair_history", []),
        validation_results=state.get("validation_results", []),
        user_confirmations=state.get("user_confirmations", {}),
        presentation_url=state.get("presentation_url"),
        paused=bool(state.get("paused")),
        paused_at=state.get("paused_at"),
    )
