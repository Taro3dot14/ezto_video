"""Artifact path management.

Enforces the output directory contract from the original SKILL.md.
All file paths are relative to a per-thread workspace root, using
forward slashes on all platforms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import VideoWorkflowState

# ── Logical -> relative path mapping ──
# Keys are logical names used in artifact_paths.
# Values are relative paths under workspace_root.

ARTIFACT_LAYOUT: dict[str, str] = {
    # Phase 1: content
    "article.md": "article.md",
    "script.md": "script.md",
    "outline.md": "outline.md",
    # Phase 2: presentation project
    "presentation": "presentation",
    # Phase 3: audio
    "audio-segments.json": "presentation/audio-segments.json",
    "public/audio": "presentation/public/audio",
}

# Files that must exist after their phase completes (optional = False)
MANDATORY_ARTIFACTS: dict[str, bool] = {
    "script.md": False,
    "outline.md": False,
    "presentation": False,
    "article.md": True,
    "audio-segments.json": True,
    "public/audio": True,
}


def resolve_workspace(workspace_root: str, thread_id: str) -> str:
    """Resolve the workspace path for a given thread (forward slashes)."""
    return f"{workspace_root}/{thread_id}"


def init_workspace(state: VideoWorkflowState) -> dict:
    """Create workspace directory and set artifact_paths.

    Returns partial state update with workspace_root and artifact_paths.
    """
    workspace = resolve_workspace(
        state.get("workspace_root", "workspace"),
        state["thread_id"],
    )
    Path(workspace).mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    for logical, relative in ARTIFACT_LAYOUT.items():
        paths[logical] = f"{workspace}/{relative}"

    # Create subdirectories for presentation structure
    _ensure_presentation_dirs(workspace)

    return {
        "artifact_paths": paths,
        "workspace_root": workspace,
    }


def _ensure_presentation_dirs(workspace: str) -> None:
    """Create expected subdirectories under the presentation scaffold."""
    dirs = [
        "presentation/src/chapters",
        "presentation/src/registry",
        "presentation/src/styles",
        "presentation/src/hooks",
        "presentation/src/components",
        "presentation/scripts/tts-providers",
        "presentation/public/audio",
    ]
    for d in dirs:
        Path(workspace, d).mkdir(parents=True, exist_ok=True)


def record_creation(state: VideoWorkflowState, logical_name: str) -> dict:
    """Record that a file was created.

    Returns partial state update to merge.
    """
    path = state.get("artifact_paths", {}).get(logical_name)
    if path:
        created = state.get("created_files", [])
        if path not in created:
            created.append(path)
        return {"created_files": created}
    return {}


def record_modification(state: VideoWorkflowState, logical_name: str) -> dict:
    """Record that a file was modified."""
    path = state.get("artifact_paths", {}).get(logical_name)
    if path:
        modified = state.get("modified_files", [])
        if path not in modified:
            modified.append(path)
        return {"modified_files": modified}
    return {}


def check_artifact_contract(
    state: VideoWorkflowState,
    phase: int,
) -> list[str]:
    """Verify that mandatory artifacts for a phase exist on disk.

    Returns list of missing artifact logical names (empty = all present).
    """
    missing: list[str] = []
    paths = state.get("artifact_paths", {})
    for logical, optional in MANDATORY_ARTIFACTS.items():
        if optional:
            continue
        if phase == 1 and logical not in ("article.md", "script.md", "outline.md"):
            continue
        if phase == 2 and logical not in ("presentation",):
            continue
        path = paths.get(logical)
        if path is None or not Path(path).exists():
            missing.append(logical)
    return missing
