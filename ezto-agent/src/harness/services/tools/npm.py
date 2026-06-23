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


def _prune_dead_servers() -> None:
    for ws in list(_DEV_SERVERS.keys()):
        if _DEV_SERVERS[ws].poll() is not None:
            del _DEV_SERVERS[ws]


def _live_dev_server_workspace() -> str | None:
    _prune_dead_servers()
    for ws, proc in _DEV_SERVERS.items():
        if proc.poll() is None:
            return ws
    return None


def _port_responds(port: int, *, timeout: float = 3.0) -> bool:
    import urllib.request

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _vite_serves_chapter_ids(port: int, chapter_ids: list[str], *, timeout: float = 5.0) -> bool:
    """Best-effort check that Vite is serving the expected registry chapter ids."""
    if not chapter_ids:
        return True
    import urllib.request

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        url = f"http://127.0.0.1:{port}/src/registry/chapters.ts"
        with opener.open(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return all(f'"{cid}"' in body or f"'{cid}'" in body for cid in chapter_ids)
    except Exception:
        return False


def _free_port(port: int) -> None:
    """Kill any process listening on *port* (tracked dev server or orphan)."""
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            pids: set[str] = set()
            suffix = f":{port}"
            for line in out.stdout.splitlines():
                if "LISTENING" not in line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                if parts[1].endswith(suffix):
                    pids.add(parts[-1])
            for pid in pids:
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logger.info("Freed port %d (killed pid %s)", port, pid)
        except Exception as e:
            logger.warning("Could not free port %d on Windows: %s", port, e)
        return

    try:
        proc = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for pid in proc.stdout.strip().split():
            if pid.isdigit():
                try:
                    os.kill(int(pid), _signal.SIGTERM)
                    logger.info("Freed port %d (killed pid %s)", port, pid)
                except OSError:
                    pass
    except FileNotFoundError:
        subprocess.run(
            f"fuser -k {port}/tcp",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning("Could not free port %d: %s", port, e)


def ensure_dev_server(
    state: VideoWorkflowState,
    *,
    cwd: str | Path,
    port: int = 5202,
) -> None:
    """Ensure the shared preview port serves this workflow's presentation."""
    ws = state.get("workspace_root", "") or ""
    cwd = str(cwd)
    _prune_dead_servers()

    live_ws = _live_dev_server_workspace()
    port_ok = _port_responds(port)

    if port_ok and live_ws is None:
        logger.warning(
            "Port %d occupied by untracked process; freeing for ws=%s", port, ws,
        )
        _free_port(port)
        port_ok = False

    if live_ws == ws and port_ok:
        return

    if live_ws and live_ws != ws:
        logger.info("Switching preview dev server: %s → %s (port %d)", live_ws, ws, port)
        _kill_dev_server(live_ws)

    if live_ws == ws and not port_ok:
        logger.warning("Dev server for %s not responding on port %d, restarting", ws, port)
        _kill_dev_server(ws)

    if not _port_responds(port) or _live_dev_server_workspace() != ws:
        run_dev_server(state, cwd=cwd, port=port)


def restart_dev_server(
    state: VideoWorkflowState,
    *,
    cwd: str | Path,
    port: int = 5202,
    expected_chapter_ids: list[str] | None = None,
) -> None:
    """Kill and restart Vite so registry/chapter modules reload in the browser."""
    import time

    ws = state.get("workspace_root", "") or ""
    cwd = str(cwd)

    for attempt in range(2):
        for other_ws in list(_DEV_SERVERS.keys()):
            _kill_dev_server(other_ws)
        if ws:
            _kill_dev_server(ws)
        _free_port(port)
        time.sleep(0.4)
        run_dev_server(state, cwd=cwd, port=port)

        for _ in range(24):
            if _port_responds(port):
                break
            time.sleep(0.25)
        else:
            logger.warning(
                "Dev server not responding on port %d (attempt %d)", port, attempt + 1,
            )
            continue

        if expected_chapter_ids and not _vite_serves_chapter_ids(port, expected_chapter_ids):
            logger.warning(
                "Preview registry mismatch (expected %s); retrying restart",
                expected_chapter_ids,
            )
            continue

        logger.info("Dev server ready on port %d (ws=%s)", port, ws)
        return

    logger.warning("Dev server restart did not confirm registry on port %d", port)


def run_dev_server(
    state: VideoWorkflowState,
    *,
    cwd: str | None = None,
    port: int = 5202,
) -> subprocess.Popen | None:
    ws = state.get("workspace_root", "")
    _prune_dead_servers()

    # All workflows share one preview port — stop other projects first.
    for other_ws in list(_DEV_SERVERS.keys()):
        if other_ws != ws:
            _kill_dev_server(other_ws)

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
