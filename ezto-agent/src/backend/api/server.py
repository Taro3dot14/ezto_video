"""FastAPI server entry point.

Run with:
    uvicorn backend.api.server:app --reload --port 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, set_manager, set_project_service
from backend.services.workflow_service import WorkflowManager
from backend.services.project_service import ProjectService
from configs import settings
from backend.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize workflow manager on startup."""
    logger.info("Starting ezto-agent server — port=%s", settings.port)
    mgr = WorkflowManager()
    project_svc = ProjectService(settings.workspace_root)
    backfilled = project_svc.bootstrap_workspace()
    project_count = sum(
        1 for p in project_svc._root.iterdir() if p.is_dir()
    ) if project_svc._root.exists() else 0
    logger.info(
        "Workspace ready root=%s projects=%d backfilled=%d",
        project_svc._root,
        project_count,
        backfilled,
    )
    mgr.set_project_service(project_svc)
    mgr.build_graph()
    set_manager(mgr)
    set_project_service(project_svc)
    from harness.core.live_sync import set_live_sync_handler
    from harness.core.token_usage import set_token_record_handler
    set_live_sync_handler(mgr.patch_state)
    set_token_record_handler(mgr.record_token_usage)
    from harness.workflow.node_catalog import TOTAL_NODES
    logger.info("Graph built with %d nodes, ready", TOTAL_NODES)
    yield
    logger.info("Server shutting down")


app = FastAPI(
    title="ezto-video Agent API",
    description="LangGraph-powered workflow engine for web-video-presentation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
