"""Vite build and dev-server verification."""

from __future__ import annotations

import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from configs import settings
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


@dataclass
class ViteCheckResult:
    success: bool
    message: str


def check_vite(
    state: VideoWorkflowState,
    *,
    cwd: str | Path,
    port: int | None = None,
) -> ViteCheckResult:
    """Run vite build and verify the dev server page loads."""
    cwd = str(cwd)
    port = port if port is not None else settings.presentation_port
    _record_tool_call(
        state, "check_vite", {"cwd": cwd, "port": port},
        allowed=True, reason="Vite build + page load verification",
    )

    proc = subprocess.run(
        ["npx", "vite", "build"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
    )
    stdout = (proc.stdout or "") + "\n" + (proc.stderr or "")
    all_lines = stdout.splitlines()
    errors = [
        line for line in all_lines
        if "error" in line.lower() and "warning" not in line.lower()
    ]

    if proc.returncode != 0 or errors:
        return ViteCheckResult(
            success=False,
            message=(
                f"❌ VITE BUILD FAILED (exit={proc.returncode}, {len(errors)} errors):\n"
                + "\n".join(errors[:10])
                + f"\n\nFull output:\n```\n{stdout[-3000:]}\n```\n\n"
                "ACTION: Fix the errors above, then run check_vite again."
            ),
        )

    page_ok = False
    page_error = ""
    try:
        # Bypass HTTP_PROXY for localhost — Clash/V2Ray often returns 502 for 127.0.0.1
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        resp = opener.open(f"http://127.0.0.1:{port}/", timeout=10)
        body = resp.read().decode(errors="replace")
        if '<div id="root">' in body and "<script" in body:
            page_ok = True
        else:
            page_error = f"Page returned {resp.status} but missing expected HTML elements"
    except Exception as e:
        page_error = str(e)

    if page_ok:
        return ViteCheckResult(
            success=True,
            message=f"✅ Build OK, page loads at http://localhost:{port}/",
        )

    return ViteCheckResult(
        success=False,
        message=(
            f"❌ Build OK but page FAILED to load at http://localhost:{port}/\n"
            f"Error: {page_error}\n\nACTION: Fix the page load error, then run check_vite again."
        ),
    )
