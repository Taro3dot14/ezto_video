"""FastAPI routes for the workflow API."""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.logger import logger, log_api_request

from .models import (
    ArtifactInfo,
    ErrorResponse,
    ResumeRequest,
    StartRequest,
    StartWorkflowResponse,
    ResumeWorkflowResponse,
    ThemeInfo,
    WorkflowStateResponse,
)
from .workflow_manager import WorkflowManager

router = APIRouter(prefix="/api")

# Shared manager instance (set by server.py on startup)
_manager: WorkflowManager | None = None


def get_manager() -> WorkflowManager:
    assert _manager is not None, "WorkflowManager not initialized"
    return _manager


def set_manager(m: WorkflowManager) -> None:
    global _manager
    _manager = m


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
async def workflow_events(thread_id: str):
    """SSE event stream for workflow state changes."""
    mgr = get_manager()
    if mgr.get_state(thread_id) is None:
        raise HTTPException(404, detail=f"Workflow {thread_id} not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        last_node_count = -1
        last_think_count = 0
        last_pending_interrupt: dict | None = None
        while True:
            state = mgr.get_state(thread_id)
            if state is None:
                yield f"event: error\ndata: {json.dumps({'message': 'workflow deleted'})}\n\n"
                break

            nodes = state.get("completed_nodes", [])
            thinking = state.get("thinking_log", [])
            current_pi = state.get("pending_interrupt")

            # Push new thinking events (incrementally)
            new_think = thinking[last_think_count:]
            if new_think:
                last_think_count = len(thinking)
                yield f"event: think\ndata: {json.dumps(new_think, ensure_ascii=False)}\n\n"

            # Push state change when nodes advance OR when pending_interrupt appears
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

    return StreamingResponse(
        event_generator(),
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


# ── Internal ──


def _state_to_response(state: VideoWorkflowState) -> WorkflowStateResponse:
    """Convert internal state to API response."""
    from app.runtime.state import VideoWorkflowState

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

    return WorkflowStateResponse(
        thread_id=state.get("thread_id", ""),
        current_phase=state.get("current_phase", ""),
        current_node=state.get("current_node", ""),
        completed_nodes=state.get("completed_nodes", []),
        thinking_log=state.get("thinking_log", []),
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
    )
