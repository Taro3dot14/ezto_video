"""Scaffold runner — creates Vite + React + TS presentation projects."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import (
    _record_tool_call, _push_scaffold_log,
)
from configs.settings import settings

_SCRIPTS_DIR = Path(settings.cmd_dir)


def _find_bash() -> str:
    if sys.platform != "win32":
        return "bash"
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        r"C:\msys64\usr\bin\bash.exe",
        r"C:\cygwin64\bin\bash.exe",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return "bash"


def run_scaffold(
    state: VideoWorkflowState,
    target_dir: str,
    theme: str,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    full_script = str(_SCRIPTS_DIR / "scaffold.sh")
    bash_exe = _find_bash()

    if cwd is None:
        cwd = state.get("workspace_root", ".")
    cwd = str(Path(cwd).resolve())
    logger.info("Scaffold cwd=%s target=%s theme=%s", cwd, target_dir, theme)
    command = f'"{bash_exe}" "{full_script}" "{target_dir}" --theme="{theme}"'

    _record_tool_call(
        state, "scaffold", {"target": target_dir, "theme": theme, "bash": bash_exe},
        allowed=True, reason="Scaffold Vite + React + TS presentation project",
    )

    proc = subprocess.Popen(
        command, shell=True, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    thread_id = state.get("thread_id", "unknown")

    def _read_stream(stream, sink, log_fn):
        assert stream is not None
        for line in iter(stream.readline, ""):
            line = line.rstrip("\n")
            sink.append(line)
            log_fn("[scaffold] %s", line)
            _push_scaffold_log(thread_id, line)

    threads = [
        threading.Thread(target=_read_stream, args=(proc.stdout, stdout_lines, logger.info), daemon=True),
        threading.Thread(target=_read_stream, args=(proc.stderr, stderr_lines, logger.warning), daemon=True),
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
        args=command, returncode=proc.returncode or 0,
        stdout="\n".join(stdout_lines), stderr="\n".join(stderr_lines),
    )
