"""Runtime utilities — workspace init, artifact paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from configs.settings import settings
from harness.core.state import VideoWorkflowState

ARTIFACT_LAYOUT: dict[str, str] = {
    "article.md": "article.md",
    "script.md": "script.md",
    "outline.md": "outline.md",
    "presentation": "presentation",
    "audio-segments.json": "presentation/audio-segments.json",
    "public/audio": "presentation/public/audio",
}


def resolve_workspace(workspace_root: str, thread_id: str) -> str:
    return f"{workspace_root}/{thread_id}"


def load_workspace(state: VideoWorkflowState) -> dict:
    """Create workspace directory and set artifact_paths."""
    workspace = str(
        Path(resolve_workspace(
            state.get("workspace_root", "workspace"),
            state["thread_id"],
        )).resolve()
    )
    Path(workspace).mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    for logical, relative in ARTIFACT_LAYOUT.items():
        paths[logical] = f"{workspace}/{relative}"

    return {"artifact_paths": paths, "workspace_root": workspace}
