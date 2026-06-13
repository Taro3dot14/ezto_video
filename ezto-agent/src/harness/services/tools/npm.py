"""NPM script runner for dev server, narrations, and audio."""

from __future__ import annotations

import os
import subprocess
import signal as _signal
from pathlib import Path

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


def run_npm(
    state: VideoWorkflowState,
    script: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    _record_tool_call(
        state, "npm", {"script": script, "cwd": cwd},
        allowed=True, reason=f"npm run {script}",
    )
    cmd_env = {**subprocess._clean_environ(), **(env or {})}
    return subprocess.run(
        f"npm run {script}", shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=300,
        env=cmd_env, encoding="utf-8", errors="replace",
    )


_DEV_SERVERS: dict[str, subprocess.Popen] = {}


def run_dev_server(
    state: VideoWorkflowState,
    *,
    cwd: str | None = None,
    port: int = 5202,
) -> subprocess.Popen | None:
    ws = state.get("workspace_root", "")
    if ws and ws in _DEV_SERVERS:
        proc = _DEV_SERVERS[ws]
        if proc.poll() is None:
            logger.info("Dev server already running for %s (pid=%d)", ws, proc.pid)
            return None
        del _DEV_SERVERS[ws]

    _record_tool_call(
        state, "npm", {"script": f"dev --port {port}", "cwd": cwd},
        allowed=True, reason="Start Vite dev server",
    )

    proc = subprocess.Popen(
        f"npm run dev -- --port {port}", shell=True, cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    if ws:
        _DEV_SERVERS[ws] = proc
        import atexit
        atexit.register(_kill_dev_server, ws)

    logger.info("Dev server started (pid=%d, ws=%s)", proc.pid, ws)
    return proc


def kill_dev_server(ws_root: str) -> None:
    _kill_dev_server(ws_root)


def _kill_dev_server(ws_root: str) -> None:
    proc = _DEV_SERVERS.pop(ws_root, None)
    if proc is None or proc.poll() is not None:
        return
    logger.info("Killing dev server (pid=%d, ws=%s)", proc.pid, ws_root)
    try:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        pass


def kill_all_dev_servers() -> None:
    for ws in list(_DEV_SERVERS.keys()):
        _kill_dev_server(ws)
