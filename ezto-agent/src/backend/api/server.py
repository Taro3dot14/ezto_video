"""FastAPI server entry point.

Run with:
    uvicorn backend.api.server:app --reload --port 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, set_manager
from backend.services.workflow_service import WorkflowManager
from configs import settings
from backend.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize workflow manager on startup."""
    logger.info("Starting ezto-agent server — port=%s", settings.port)
    mgr = WorkflowManager()
    mgr.build_graph()
    set_manager(mgr)
    logger.info("Graph built with 27 nodes, ready")
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
