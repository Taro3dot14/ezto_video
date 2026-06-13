"""Phase 4 — Recording Guidance node."""

from __future__ import annotations

from harness.core.state import VideoWorkflowState


def wv_recording_guidance(state: VideoWorkflowState) -> dict:
    ws = state.get("workspace_root", ".")
    theme = state.get("selected_theme", "default")
    return {"final_summary": (
        f"Presentation complete!\nWorkspace: {ws}/presentation\nTheme: {theme}\n\n"
        f"To record:\n1. cd {ws}/presentation\n2. npm run dev\n"
        f"3. Open browser, add ?auto=1 for auto-advance\n4. Screen record"
    ), "current_node": "wv_recording_guidance"}
