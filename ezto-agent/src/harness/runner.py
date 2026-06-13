"""Harness runner — unified entry point for the workflow engine.

Backend services call this module instead of directly invoking LangGraph.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from langgraph.graph import StateGraph
from langgraph.types import Command

from harness.core.state import VideoWorkflowState
from harness.core.runtime import load_workspace
from harness.workflow.builder import build_web_video_graph
from harness.workflow.interruptions import pop_last_interrupt_payload
from configs.settings import settings
from backend.core.logger import logger


class HarnessRunner:
    """Manages workflow lifecycle: start, resume, query state."""

    def __init__(self):
        self._graph: StateGraph | None = None
        self._threads: dict[str, Any] = {}

    def build(self) -> None:
        """Build the LangGraph."""
        self._graph = build_web_video_graph()
        logger.info("Harness graph built with 27 nodes")

    # ── Workflow lifecycle ──

    async def start(
        self,
        user_request: str,
        language: str = "zh-CN",
        input_type: str | None = None,
    ) -> tuple[str, VideoWorkflowState]:
        """Start a new workflow."""
        thread_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        if input_type is None:
            input_type = self._detect_input_type(user_request)

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
            "validation_results": [],
            "repair_history": [],
            "errors": [],
            "allowed_tools": [],
            "denied_tools": [],
            "tool_calls": [],
            "final_summary": None,
        }

        ws_update = load_workspace(state)
        state.update(ws_update)

        if self._graph is None:
            self.build()

        config = {"configurable": {"thread_id": thread_id}}
        self._threads[thread_id] = {"state": dict(state), "config": config}
        asyncio.create_task(self._run(thread_id, state, config))

        return thread_id, state

    async def resume(
        self,
        thread_id: str,
        confirmations: dict[str, Any],
    ) -> VideoWorkflowState:
        """Resume an interrupted workflow."""
        thread = self._threads.get(thread_id)
        if thread is None:
            raise ValueError(f"Workflow not found: {thread_id}")

        config = thread["config"]
        if self._graph is None:
            self.build()

        logger.info("Resume thread=%s confirm=%s", thread_id, list(confirmations.keys()))
        thread["state"]["pending_interrupt"] = None
        asyncio.create_task(self._run_resume(thread_id, config, confirmations))
        return thread["state"]

    def get_state(self, thread_id: str) -> VideoWorkflowState | None:
        thread = self._threads.get(thread_id)
        return thread["state"] if thread else None

    # ── Internal ──

    async def _run(self, thread_id: str, state: VideoWorkflowState, config: dict) -> None:
        logger.info("Runner start thread=%s", thread_id)
        try:
            async for output in self._graph.astream(state, config, stream_mode="values"):
                self._threads[thread_id]["state"] = output

            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info("Runner interrupted at %s (type=%s)", payload.get("node"), payload.get("type"))
                return
        except Exception as e:
            logger.error("Runner FAILED thread=%s: %s", thread_id, e)

    async def _run_resume(self, thread_id: str, config: dict, confirmations: dict) -> None:
        try:
            async for output in self._graph.astream(
                Command(resume=confirmations), config, stream_mode="values",
            ):
                self._threads[thread_id]["state"] = output

            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                return
        except Exception as e:
            logger.error("Resume FAILED thread=%s: %s", thread_id, e)

    @staticmethod
    def _detect_input_type(text: str) -> str:
        text = text.strip()
        if not text or len(text) < 20:
            return "none"
        if text.startswith("#") or len(text) > 500:
            return "article"
        return "script"
