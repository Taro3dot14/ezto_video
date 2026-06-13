"""FastAPI dependencies (dependency injection)."""

from __future__ import annotations

from fastapi import Request, HTTPException
from backend.services.workflow_service import WorkflowService


async def get_workflow_service(request: Request) -> WorkflowService:
    """Get the workflow service instance from app state."""
    mgr = request.app.state.workflow_service
    if mgr is None:
        raise HTTPException(503, detail="Workflow service not initialized")
    return mgr
