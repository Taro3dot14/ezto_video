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
from langgraph.errors import GraphInterrupt

from harness.core.token_usage import empty_usage, merge_usage
from harness.workflow.guards import init_workspace
from harness.workflow.interruptions import pop_last_interrupt_payload
from harness.core.state_snapshot import state_for_snapshot
from harness.core.execution import derive_runtime
from harness.core.state import VideoWorkflowState
from configs import settings
from backend.core.logger import logger
from backend.services.project_service import ProjectService


_THEMES_DIR = Path(settings.themes_dir)


class WorkflowManager:
    """Manages workflow instances, each identified by thread_id."""

    def __init__(self):
        self._graph: StateGraph | None = None
        # In-memory store; replace with DB for production
        self._threads: dict[str, Any] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._project_service: ProjectService | None = None

    def set_project_service(self, svc: ProjectService) -> None:
        self._project_service = svc

    def active_thread_ids(self) -> set[str]:
        return set(self._threads.keys())

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
            "current_node": "",
            "completed_nodes": [],
            "execution_trace": [],
            "execution_revision": 0,
            "token_usage": empty_usage(),
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
            "approved_chapter_ids": [],
            "chapter_missing_assets": {},
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

        if self._project_service:
            self._project_service.ensure_meta(
                thread_id,
                user_request=user_request,
                input_type=input_type,
                language=language,
            )

        if self._graph is None:
            self.build_graph()

        config = {"configurable": {"thread_id": thread_id}}
        self._threads[thread_id] = {"state": dict(state), "config": config}
        self._persist_state(thread_id, state)

        # Launch the graph in background — frontend tracks via SSE
        self._launch_task(thread_id, self._run_graph(thread_id, state, config))

        return thread_id, state

    def _launch_task(self, thread_id: str, coro) -> None:
        """Track and replace any in-flight graph task for this thread."""
        prev = self._tasks.pop(thread_id, None)
        if prev and not prev.done():
            prev.cancel()

        task = asyncio.create_task(coro)
        self._tasks[thread_id] = task

        def _cleanup(t: asyncio.Task) -> None:
            if self._tasks.get(thread_id) is t:
                self._tasks.pop(thread_id, None)

        task.add_done_callback(_cleanup)

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
                self._threads[thread_id]["state"] = self._merge_preserved_fields(
                    thread_id, output,
                )

            elapsed = time.perf_counter() - t0

            # Check if the graph stopped due to a checkpoint interrupt
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info("Background graph interrupted at %s after %.0fs (type=%s)",
                            payload.get("node", "?"), elapsed, payload.get("type"))
                return

            logger.info("Background graph completed after %.0fs", elapsed)

        except GraphInterrupt:
            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info(
                    "Background graph interrupted at %s after %.0fs (type=%s)",
                    payload.get("node", "?"),
                    elapsed,
                    payload.get("type"),
                )
            else:
                logger.info("Background graph interrupted after %.0fs", elapsed)
        except asyncio.CancelledError:
            logger.warning("Background graph cancelled thread=%s", thread_id)
            thread = self._threads.get(thread_id)
            if thread:
                thread["state"]["paused"] = True
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
            thread["state"]["paused"] = False
            thread["state"].pop("paused_at", None)
            # Run in background so SSE can stream progress
            self._launch_task(
                thread_id,
                self._run_resume(thread_id, config, confirmations, t0),
            )
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
                self._threads[thread_id]["state"] = self._merge_preserved_fields(
                    thread_id, output,
                )

            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info("Resume interrupted at %s after %.0fs (type=%s)",
                            payload.get("node", "?"), elapsed, payload.get("type"))
                return

            logger.info("Resume completed after %.0fs", elapsed)
        except GraphInterrupt:
            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info(
                    "Resume interrupted at %s after %.0fs (type=%s)",
                    payload.get("node", "?"),
                    elapsed,
                    payload.get("type"),
                )
            else:
                logger.info("Resume interrupted after %.0fs", elapsed)
        except asyncio.CancelledError:
            logger.warning("Resume cancelled thread=%s", thread_id)
            thread = self._threads.get(thread_id)
            if thread:
                thread["state"]["paused"] = True
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

    async def pause_workflow(self, thread_id: str) -> VideoWorkflowState:
        """Cancel the in-flight graph task and mark the workflow paused."""
        thread = self._threads.get(thread_id)
        if thread is None:
            raise ValueError(f"Workflow not found: {thread_id}")

        state = thread["state"]
        runtime = derive_runtime(state)
        paused_node = runtime.get("current_node") or ""
        if paused_node:
            state["paused_at_node"] = paused_node

        task = self._tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        state["paused"] = True
        state["paused_at"] = time.time()
        logger.info("Workflow paused thread=%s node=%s", thread_id, paused_node)
        return state

    async def remove_workflow(self, thread_id: str) -> None:
        """Cancel any in-flight task and drop in-memory workflow state."""
        task = self._tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._threads.pop(thread_id, None):
            logger.info("Workflow removed from memory thread=%s", thread_id)

    async def continue_workflow(self, thread_id: str) -> VideoWorkflowState:
        """Resume a paused workflow from the LangGraph checkpoint."""
        thread = self._threads.get(thread_id)
        if thread is None:
            raise ValueError(f"Workflow not found: {thread_id}")

        if not thread["state"].get("paused"):
            raise ValueError("Workflow is not paused")

        config = thread.get("config")
        if config is None:
            raise ValueError(f"No config for workflow: {thread_id}")

        if self._graph is None:
            self.build_graph()

        thread["state"]["paused"] = False
        thread["state"].pop("paused_at", None)
        logger.info("Continue paused workflow thread=%s", thread_id)
        t0 = time.perf_counter()
        self._launch_task(
            thread_id,
            self._run_continue(thread_id, config, t0),
        )
        return thread["state"]

    async def _run_continue(
        self,
        thread_id: str,
        config: dict,
        t0: float,
    ) -> None:
        """Resume graph execution from checkpoint after user continue."""
        try:
            async for output in self._graph.astream(None, config, stream_mode="values"):
                self._threads[thread_id]["state"] = self._merge_preserved_fields(
                    thread_id, output,
                )

            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info(
                    "Continue interrupted at %s after %.0fs (type=%s)",
                    payload.get("node", "?"),
                    elapsed,
                    payload.get("type"),
                )
                return

            logger.info("Continue completed after %.0fs", elapsed)
        except GraphInterrupt:
            elapsed = time.perf_counter() - t0
            payload = pop_last_interrupt_payload()
            if payload:
                self._threads[thread_id]["state"]["pending_interrupt"] = payload
                logger.info(
                    "Continue interrupted at %s after %.0fs (type=%s)",
                    payload.get("node", "?"),
                    elapsed,
                    payload.get("type"),
                )
            else:
                logger.info("Continue interrupted after %.0fs", elapsed)
        except asyncio.CancelledError:
            logger.warning("Continue cancelled thread=%s", thread_id)
            thread = self._threads.get(thread_id)
            if thread:
                thread["state"]["paused"] = True
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error(
                "Continue FAILED thread=%s after %.0fs: %s",
                thread_id,
                elapsed,
                e,
            )
            state = self._threads.get(thread_id, {}).get("state")
            if state:
                state["errors"] = list(state.get("errors", [])) + [{
                    "node": "background_continue",
                    "error": str(e),
                }]
        except BaseException as e:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "Continue stopped thread=%s after %.0fs: %s",
                thread_id,
                elapsed,
                e,
            )

    def get_state(self, thread_id: str) -> VideoWorkflowState | None:
        """Get the current state of a workflow."""
        thread = self._threads.get(thread_id)
        if thread is not None:
            return thread["state"]
        return self._hydrate_from_disk(thread_id)

    def _hydrate_from_disk(self, thread_id: str) -> VideoWorkflowState | None:
        if self._project_service is None:
            return None
        snapshot = self._project_service.load_state_snapshot(thread_id)
        if snapshot is not None:
            self._threads[thread_id] = {
                "state": snapshot,
                "config": {"configurable": {"thread_id": thread_id}},
            }
            logger.info("Hydrated workflow state from disk thread=%s", thread_id)
            return snapshot

        if not self._project_service.project_dir(thread_id).is_dir():
            return None

        # Minimal state for projects created before snapshot persistence
        base: VideoWorkflowState = {
            "thread_id": thread_id,
            "run_id": thread_id,
            "user_request": "",
            "language": "zh-CN",
            "input_type": "none",
            "current_phase": "phase1",
            "current_node": "",
            "completed_nodes": [],
            "execution_trace": [],
            "execution_revision": 0,
            "token_usage": empty_usage(),
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
            "approved_chapter_ids": [],
            "chapter_missing_assets": {},
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
        base.update(init_workspace(base))
        self._threads[thread_id] = {
            "state": base,
            "config": {"configurable": {"thread_id": thread_id}},
        }
        logger.info("Hydrated minimal workflow state from workspace thread=%s", thread_id)
        return base

    def _persist_state(self, thread_id: str, state: VideoWorkflowState) -> None:
        if self._project_service is None:
            return
        try:
            self._project_service.save_state_snapshot(thread_id, state_for_snapshot(dict(state)))
        except OSError as e:
            logger.warning("Failed to persist state thread=%s: %s", thread_id, e)

    def patch_state(self, thread_id: str, patch: dict) -> None:
        """Apply a partial update (live sync during long-running nodes)."""
        thread = self._threads.get(thread_id)
        if thread is None:
            return
        thread["state"].update(patch)
        self._persist_state(thread_id, thread["state"])

    def record_token_usage(
        self,
        thread_id: str,
        model: str,
        usage: dict[str, int],
    ) -> None:
        thread = self._threads.get(thread_id)
        if thread is None:
            return
        state = thread["state"]
        state["token_usage"] = merge_usage(
            state.get("token_usage"),
            model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    def _merge_preserved_fields(
        self,
        thread_id: str,
        output: VideoWorkflowState,
    ) -> VideoWorkflowState:
        """Keep live-synced fields when LangGraph yields partial state."""
        prev = self._threads.get(thread_id, {}).get("state", {})
        merged = state_for_snapshot(dict(output))
        if prev.get("token_usage"):
            merged["token_usage"] = prev["token_usage"]
        if prev.get("execution_trace") and not merged.get("execution_trace"):
            merged["execution_trace"] = prev["execution_trace"]
            merged["execution_revision"] = prev.get("execution_revision", 0)
        self._persist_state(thread_id, merged)
        return merged

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
            if self._project_service and self._project_service.project_dir(thread_id).is_dir():
                return self._project_service.scan_disk_artifacts(thread_id)
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

    def apply_workflow_theme(self, thread_id: str, theme_id: str) -> VideoWorkflowState:
        """Swap presentation tokens.css for an active or hydrated workflow."""
        from backend.services.theme_service import apply_theme, refresh_preview_after_theme_apply

        state = self.get_state(thread_id)
        if state is None:
            raise ValueError(f"Workflow not found: {thread_id}")

        ws = state.get("workspace_root")
        if not ws:
            raise ValueError("Workflow has no workspace")

        apply_theme(Path(ws), theme_id)
        refresh_preview_after_theme_apply(ws)
        state = dict(state)
        state["selected_theme"] = theme_id
        thread = self._threads.get(thread_id)
        if thread is not None:
            thread["state"] = state
        self._persist_state(thread_id, state)
        logger.info("Applied theme %s to workflow %s", theme_id, thread_id)
        return state


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


