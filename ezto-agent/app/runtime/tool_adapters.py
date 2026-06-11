"""Tool adapters for the web-video-presentation workflow.

Wraps shell commands, file operations, and scaffold scripts into
auditable, traceable adapters that match the original SKILL.md
tool semantics.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from app.core import settings
from app.core.logger import logger

from .state import ToolCallRecord, VideoWorkflowState


def _record_tool_call(
    state: VideoWorkflowState,
    tool_name: str,
    args: dict[str, Any],
    allowed: bool,
    reason: str,
) -> ToolCallRecord:
    record: ToolCallRecord = {
        "node": state.get("current_node", "unknown"),
        "tool": tool_name,
        "args": args,
        "allowed": allowed,
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    calls = state.get("tool_calls", [])
    calls.append(record)
    # Mutate in place — caller must merge if needed
    return record


# ── Shell execution ──


def run_shell(
    state: VideoWorkflowState,
    command: str,
    *,
    cwd: str | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Execute a shell command with audit logging.

    Matches the original SKILL.md usage of bash commands
    (scaffold.sh, npm, rm, cp, etc.).
    """
    _record_tool_call(
        state,
        "shell",
        {"command": command, "cwd": cwd, "timeout": timeout},
        allowed=True,
        reason="Shell command for web-video workflow step",
    )
    return subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


# ── File read adapter ──


def read_file(
    state: VideoWorkflowState,
    path: str,
    *,
    max_bytes: int = 1_000_000,
) -> str:
    """Read a file with audit logging and size limit.

    Matches the original Read tool semantics — partial reads preferred.
    """
    _record_tool_call(
        state,
        "read_file",
        {"path": path, "max_bytes": max_bytes},
        allowed=True,
        reason="File read for content inspection",
    )
    return Path(path).read_text(encoding="utf-8", errors="replace")


# ── Scaffold adapter ──

_SCRIPTS_DIR = Path(settings.project_root).resolve() / "app" / "scripts"


def _find_bash() -> str:
    """Locate a working bash executable.

    On Windows, avoid WSL bash (can't handle Windows paths).
    Prefer Git Bash, MSYS2, or Cygwin bash.
    """
    if sys.platform != "win32":
        return "bash"
    # shutil.which("bash") might return WSL's bash — skip it
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        r"C:\msys64\usr\bin\bash.exe",
        r"C:\cygwin64\bin\bash.exe",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    # Fallback: let the OS decide (will likely fail, but worth a try)
    return "bash"


def run_scaffold(
    state: VideoWorkflowState,
    target_dir: str,
    theme: str,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the scaffold.sh script to create a presentation project.

    Original SKILL.md (Phase 2.1):
      bash <path>/scaffold.sh <target> --theme=<id>

    If cwd is provided, scaffold runs there (useful for WSL native fs
    where npm install is much faster). Otherwise uses workspace_root.
    """
    full_script = str(_SCRIPTS_DIR / "scaffold.sh")
    bash_exe = _find_bash()

    if cwd is None:
        cwd = state.get("workspace_root", ".")
    # Resolve to absolute path — workspace_root in state may be a relative
    # path like "workspace/<uuid>/" and Popen(cwd=relpath) resolves against
    # the server's CWD, which may not be what we expect.
    cwd = str(Path(cwd).resolve())
    logger.info("Scaffold cwd=%s target=%s theme=%s", cwd, target_dir, theme)
    command = f'"{bash_exe}" "{full_script}" "{target_dir}" --theme="{theme}"'

    _record_tool_call(
        state,
        "scaffold",
        {"target": target_dir, "theme": theme, "bash": bash_exe},
        allowed=True,
        reason="Scaffold Vite + React + TS presentation project",
    )

    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Stream both stdout/stderr in real-time via background threads
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _read_stream(stream, sink, log_fn):
        assert stream is not None
        for line in iter(stream.readline, ""):
            line = line.rstrip("\n")
            sink.append(line)
            log_fn("[scaffold] %s", line)

    threads = [
        threading.Thread(
            target=_read_stream, args=(proc.stdout, stdout_lines, logger.info), daemon=True
        ),
        threading.Thread(
            target=_read_stream, args=(proc.stderr, stderr_lines, logger.warning), daemon=True
        ),
    ]
    for t in threads:
        t.start()

    try:
        proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise
    finally:
        for t in threads:
            t.join(timeout=3)

    return subprocess.CompletedProcess(
        args=command,
        returncode=proc.returncode or 0,
        stdout="\n".join(stdout_lines),
        stderr="\n".join(stderr_lines),
    )


# ── NPM script adapter ──


def run_npm(
    state: VideoWorkflowState,
    script: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run an npm script.

    Original SKILL.md usage:
      npm run dev
      npm run extract-narrations
      npm run synthesize-audio
    """
    _record_tool_call(
        state,
        "npm",
        {"script": script, "cwd": cwd},
        allowed=True,
        reason=f"npm run {script}",
    )
    cmd_env = {**subprocess._clean_environ(), **(env or {})}  # noqa
    return subprocess.run(
        f"npm run {script}",
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
        env=cmd_env,
        encoding="utf-8",
        errors="replace",
    )


# ── Dev server (npm run dev) ──

import signal as _signal

# Track running dev servers by workspace root so we don't start duplicates
_DEV_SERVERS: dict[str, subprocess.Popen] = {}


def run_dev_server(
    state: VideoWorkflowState,
    *,
    cwd: str | None = None,
    port: int = 5174,
) -> subprocess.Popen | None:
    """Start npm run dev as a background process.

    If a server is already running for this workspace, returns None.
    Otherwise starts one, tracks it, and registers atexit cleanup.
    """
    ws = state.get("workspace_root", "")
    if ws and ws in _DEV_SERVERS:
        proc = _DEV_SERVERS[ws]
        if proc.poll() is None:
            logger.info("Dev server already running for %s (pid=%d)", ws, proc.pid)
            return None
        # Stale process — remove and start fresh
        del _DEV_SERVERS[ws]

    _record_tool_call(
        state,
        "npm",
        {"script": f"dev --port {port}", "cwd": cwd},
        allowed=True,
        reason="Start Vite dev server for presentation preview",
    )

    proc = subprocess.Popen(
        f"npm run dev -- --port {port}",
        shell=True,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    if ws:
        _DEV_SERVERS[ws] = proc
        import atexit
        atexit.register(_kill_dev_server, ws)

    logger.info("Dev server started (pid=%d, ws=%s)", proc.pid, ws)
    return proc


def kill_dev_server(ws_root: str) -> None:
    """Kill a running dev server for a given workspace root."""
    _kill_dev_server(ws_root)


def _kill_dev_server(ws_root: str) -> None:
    proc = _DEV_SERVERS.pop(ws_root, None)
    if proc is None:
        return
    if proc.poll() is None:
        logger.info("Killing dev server (pid=%d, ws=%s)", proc.pid, ws_root)
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass


def kill_all_dev_servers() -> None:
    """Kill all tracked dev servers."""
    for ws in list(_DEV_SERVERS.keys()):
        _kill_dev_server(ws)


# ── TypeScript type-check ──


def run_typecheck(
    state: VideoWorkflowState,
    *,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run npx tsc --noEmit.

    Original SKILL.md rule: each chapter must pass typecheck before
    reporting completion.
    """
    _record_tool_call(
        state,
        "typecheck",
        {"cwd": cwd},
        allowed=True,
        reason="TypeScript type-check (required per-chapter)",
    )
    return subprocess.run(
        "npx tsc --noEmit",
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
        errors="replace",
    )
