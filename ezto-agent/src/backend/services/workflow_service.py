"""LangGraph workflow orchestration manager.

Handles invoke, interrupt resume, and state query for the
web-video-presentation LangGraph.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph
from langgraph.types import Command

from harness.workflow.guards import init_workspace
from harness.workflow.interruptions import pop_last_interrupt_payload
from harness.core.state import VideoWorkflowState
from configs import settings
from backend.core.logger import logger


_THEMES_DIR = Path(settings.themes_dir)


class WorkflowManager:
    """Manages workflow instances, each identified by thread_id."""

    def __init__(self):
        self._graph: StateGraph | None = None
        # In-memory store; replace with DB for production
        self._threads: dict[str, Any] = {}

    # ── Graph construction ──

    def build_graph(self) -> StateGraph:
        """Build the workflow graph with all 22 nodes."""
        from harness.workflow.builder import build_web_video_graph
        self._graph = build_web_video_graph()
        return self._graph

    # ── Workflow lifecycle ──

    async def start_workflow(
        self,
        user_request: str,
        language: str = "zh-CN",
        input_type: str | None = None,
    ) -> tuple[str, VideoWorkflowState]:
        """Start a new workflow.

        Creates the thread and returns immediately. The graph runs in the
        background; the frontend can track progress via /events SSE.

        Returns (thread_id, initial_state).
        """
        thread_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        if input_type is None:
            input_type = _detect_input_type(user_request)

        state: VideoWorkflowState = {
            "thread_id": thread_id,
            "run_id": run_id,
            "user_request": user_request,
            "language": language,
            "input_type": input_type,
            "current_phase": "phase1",
            "current_node": "wv_identify_input",
            "completed_nodes": [],
            "current_chapter_index": 0,
            "total_chapters": 0,
            "thinking_log": [],
            "pending_interrupt": None,
            "required_refs": [],
            "loaded_refs": [],
            "workspace_root": settings.workspace_root,
            "artifact_paths": {},
            "created_files": [],
            "modified_files": [],
            "user_confirmations": {},
            "selected_theme": None,
            "selected_mode": None,
            "synthesize_audio": None,
            "validation_results": [],
            "repair_history": [],
            "errors": [],
            "allowed_tools": [],
            "denied_tools": [],
            "tool_calls": [],
            "final_summary": None,
        }

        # Initialize workspace
        ws_update = init_workspace(state)
        state.update(ws_update)

        if self._graph is None:
            self.build_graph()

        config = {"configurable": {"thread_id": thread_id}}
        self._threads[thread_id] = {"state": dict(state), "config": config}

        # Launch the graph in background — frontend tracks via SSE
        asyncio.create_task(self._run_graph(thread_id, state, config))

        return thread_id, state

    async def _run_graph(
        self,
        thread_id: str,
        state: VideoWorkflowState,
        config: dict,
    ) -> None:
        """Execute the graph with astream, updating thread store after each node."""
        logger.info("Background graph start thread=%s", thread_id)
        t0 = time.perf_counter()
        try:
            async for output in self._graph.astream(state, config, stream_mode="values"):
                self._threads[thread_id]["state"] = output

            elapsed = time.perf_counter() - t0

            # Check if the graph stopped due to a checkpoint interrupt
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info("Background graph interrupted at %s after %.0fs (type=%s)",
                            payload.get("node", "?"), elapsed, payload.get("type"))
                return

            logger.info("Background graph completed after %.0fs", elapsed)

        except asyncio.CancelledError:
            logger.warning("Background graph cancelled thread=%s", thread_id)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error("Background graph FAILED thread=%s after %.0fs: %s",
                         thread_id, elapsed, e)
            state = self._threads.get(thread_id, {}).get("state", state)
            if state:
                state["errors"] = list(state.get("errors", [])) + [{
                    "node": "background",
                    "error": str(e),
                }]
        except BaseException as e:
            elapsed = time.perf_counter() - t0
            logger.warning("Background graph stopped thread=%s after %.0fs: %s",
                           thread_id, elapsed, e)

    async def resume_workflow(
        self,
        thread_id: str,
        confirmations: dict[str, Any],
    ) -> VideoWorkflowState:
        """Resume an interrupted workflow with user confirmations."""
        thread = self._threads.get(thread_id)
        if thread is None:
            raise ValueError(f"Workflow not found: {thread_id}")

        config = thread.get("config")
        if config is None:
            raise ValueError(f"No config for workflow: {thread_id}")

        if self._graph is None:
            self.build_graph()

        logger.info("Resume thread=%s confirm=%s", thread_id, list(confirmations.keys()))
        t0 = time.perf_counter()
        try:
            # Clear pending_interrupt immediately so the frontend stops showing
            # the checkpoint UI and transitions to loading state
            thread["state"]["pending_interrupt"] = None
            # Run in background so SSE can stream progress
            asyncio.create_task(self._run_resume(thread_id, config, confirmations, t0))
            # Return the (now cleared) state — SSE will push updates
            return thread["state"]
        except Exception as e:
            logger.error("Workflow %s resume launch failed: %s", thread_id, e)
            state = thread["state"]
            state["errors"] = list(state.get("errors", [])) + [{
                "node": "resume",
                "error": str(e),
            }]
            return state

    async def _run_resume(
        self,
        thread_id: str,
        config: dict,
        confirmations: dict[str, Any],
        t0: float,
    ) -> None:
        """Execute the graph after resume, streaming state updates."""
        # Clear stale pending_interrupt so the frontend stops showing
        # the checkpoint UI and transitions to loading state
        current = self._threads.get(thread_id, {}).get("state")
        if current:
            current["pending_interrupt"] = None

        try:
            async for output in self._graph.astream(
                Command(resume=confirmations), config, stream_mode="values",
            ):
                self._threads[thread_id]["state"] = output

            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info("Resume interrupted at %s after %.0fs (type=%s)",
                            payload.get("node", "?"), elapsed, payload.get("type"))
                return

            logger.info("Resume completed after %.0fs", elapsed)
        except asyncio.CancelledError:
            logger.warning("Resume cancelled thread=%s", thread_id)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error("Resume FAILED thread=%s after %.0fs: %s",
                         thread_id, elapsed, e)
            state = self._threads.get(thread_id, {}).get("state")
            if state:
                state["errors"] = list(state.get("errors", [])) + [{
                    "node": "background_resume",
                    "error": str(e),
                }]
        except BaseException as e:
            elapsed = time.perf_counter() - t0
            logger.warning("Resume stopped thread=%s after %.0fs: %s",
                           thread_id, elapsed, e)

    def get_state(self, thread_id: str) -> VideoWorkflowState | None:
        """Get the current state of a workflow."""
        thread = self._threads.get(thread_id)
        if thread is None:
            return None
        return thread["state"]

    def list_themes(self) -> list[dict]:
        """List all available themes from the themes directory."""
        themes_dir = Path(_THEMES_DIR)
        if not themes_dir.exists():
            return []

        themes = []
        for theme_dir in sorted(themes_dir.iterdir()):
            if not theme_dir.is_dir():
                continue
            meta_file = theme_dir / "theme.json"
            if not meta_file.exists():
                continue
            try:
                import json
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                themes.append({
                    "id": meta.get("id", theme_dir.name),
                    "name": meta.get("name", ""),
                    "nameZh": meta.get("nameZh", ""),
                    "description": meta.get("description", ""),
                    "descriptionZh": meta.get("descriptionZh", ""),
                    "mood": meta.get("mood", []),
                    "bestFor": meta.get("bestFor", []),
                    "preview": meta.get("preview"),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return themes

    def get_artifacts(self, thread_id: str) -> list[dict]:
        """List all artifact files for a workflow."""
        state = self.get_state(thread_id)
        if state is None:
            return []

        artifacts = []
        for logical, path in state.get("artifact_paths", {}).items():
            p = Path(path)
            artifacts.append({
                "logical_name": logical,
                "path": str(path),
                "exists": p.exists(),
                "size": p.stat().st_size if p.exists() else None,
            })
        return artifacts


# ── Internal helpers ──


def _detect_input_type(text: str) -> str:
    """Detect whether the user gave an article, a script, or nothing."""
    text = text.strip()
    if not text or len(text) < 20:
        return "none"
    # Simple heuristic: if text has markdown headers or long paragraphs, it's an article
    if text.startswith("#") or len(text) > 500:
        return "article"
    return "script"


