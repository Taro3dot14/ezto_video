"""TypeScript type-check runner."""

from __future__ import annotations

import subprocess
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


def run_typecheck(
    state: VideoWorkflowState,
    *,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    _record_tool_call(
        state, "typecheck", {"cwd": cwd},
        allowed=True, reason="TypeScript type-check (required per-chapter)",
    )
    return subprocess.run(
        "npx tsc --noEmit", shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace",
    )
