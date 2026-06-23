"""Policy checks: reference loading, guards, and artifact contract enforcement.

Merged from the original ref_loader.py, guards.py, and artifact_manager.py
into a single module organized by function class.
"""

from __future__ import annotations

from pathlib import Path

from configs import settings

from ..core.state import VideoWorkflowState


# ═══════════════════════════════════════════════════════════════════
# Reference paths & phase mapping
# ═══════════════════════════════════════════════════════════════════

_REFERENCES_DIR = Path(settings.references_dir)

REF_PATHS: dict[str, str] = {
    "SCRIPT-STYLE.md": str(_REFERENCES_DIR / "SCRIPT-STYLE.md"),
    "OUTLINE-FORMAT.md": str(_REFERENCES_DIR / "OUTLINE-FORMAT.md"),
    "CHAPTER-CRAFT.md": str(_REFERENCES_DIR / "CHAPTER-CRAFT.md"),
    "THEMES.md": str(_REFERENCES_DIR / "THEMES.md"),
    "AUDIO.md": str(_REFERENCES_DIR / "AUDIO.md"),
    "RECORDING.md": str(_REFERENCES_DIR / "RECORDING.md"),
}

PHASE_REFS: dict[str, list[str]] = {
    "phase1": ["SCRIPT-STYLE.md", "OUTLINE-FORMAT.md"],
    "chapter": ["CHAPTER-CRAFT.md"],
    "theme": ["THEMES.md"],
    "audio": ["AUDIO.md"],
    "recording": ["RECORDING.md"],
}


# ═══════════════════════════════════════════════════════════════════
# Artifact layout
# ═══════════════════════════════════════════════════════════════════

ARTIFACT_LAYOUT: dict[str, str] = {
    "article.md": "article.md",
    "script.md": "script.md",
    "outline.md": "outline.md",
    "presentation": "presentation",
    "audio-segments.json": "presentation/audio-segments.json",
    "public/audio": "presentation/public/audio",
}

MANDATORY_ARTIFACTS: dict[str, bool] = {
    "script.md": False,
    "outline.md": False,
    "presentation": False,
    "article.md": True,
    "audio-segments.json": True,
    "public/audio": True,
}


# ═══════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════


class PolicyViolation(Exception):
    """Raised when a node violates a reference-loading or guard policy."""

    def __init__(self, message: str, node: str, missing_refs: list[str]):
        self.node = node
        self.missing_refs = missing_refs
        super().__init__(f"[{node}] policy violation: missing refs {missing_refs} — {message}")


# ═══════════════════════════════════════════════════════════════════
# Reference loading
# ═══════════════════════════════════════════════════════════════════


def require_ref_loaded(
    state: VideoWorkflowState,
    ref_name: str,
    *,
    scope: str = "",
    reload_each_time: bool = False,
) -> str:
    """Assert that a reference is loaded, or load it now.

    Returns the loaded file content.
    """
    path = REF_PATHS.get(ref_name)
    if path is None:
        raise PolicyViolation(
            f"Unknown reference '{ref_name}'",
            node=state.get("current_node", "unknown"),
            missing_refs=[ref_name],
        )
    if reload_each_time or ref_name not in state.get("loaded_refs", []):
        _do_load(state, ref_name, path)
    return _read_file(path)


def _do_load(state: VideoWorkflowState, ref_name: str, full_path: str) -> None:
    path = Path(full_path)
    if not path.exists():
        raise PolicyViolation(
            f"Reference file not found: {full_path}",
            node=state.get("current_node", "unknown"),
            missing_refs=[ref_name],
        )
    if ref_name not in state.setdefault("loaded_refs", []):
        state["loaded_refs"].append(ref_name)


def _read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def verify_phase_refs(state: VideoWorkflowState, phase_key: str) -> list[str]:
    """Return missing ref names for a phase (empty = all loaded)."""
    needed = PHASE_REFS.get(phase_key, [])
    loaded = state.get("loaded_refs", [])
    return [r for r in needed if r not in loaded]


def reset_loaded_refs(state: VideoWorkflowState) -> None:
    """Clear loaded refs (used when transitioning phases)."""
    state["loaded_refs"] = []


# ═══════════════════════════════════════════════════════════════════
# Policy guards
# ═══════════════════════════════════════════════════════════════════


def guard_chapter_refs_loaded(state: VideoWorkflowState) -> None:
    """Guard: CHAPTER-CRAFT.md must be loaded before writing a chapter."""
    node = state.get("current_node", "unknown")
    missing = verify_phase_refs(state, "chapter")
    if missing:
        raise PolicyViolation(
            "Chapter refs not loaded — each chapter must re-read CHAPTER-CRAFT.md",
            node=node,
            missing_refs=missing,
        )


def guard_chapter_1_not_parallel(state: VideoWorkflowState) -> None:
    """Guard: Chapter 1 must be built on the main thread."""
    node = state.get("current_node", "unknown")
    if "parallel" in node:
        raise PolicyViolation(
            "Chapter 1 must be built on the main thread, not in parallel.",
            node=node,
            missing_refs=[],
        )


def guard_not_skip_checkpoint(state: VideoWorkflowState, expected_checkpoint: str) -> None:
    """Guard: Nodes after a checkpoint must have user confirmation."""
    confirmations = state.get("user_confirmations", {})
    if expected_checkpoint not in confirmations:
        raise PolicyViolation(
            f"Cannot proceed: checkpoint '{expected_checkpoint}' has not been confirmed.",
            node=state.get("current_node", "unknown"),
            missing_refs=[],
        )
    if expected_checkpoint in {
        "checkpoint_chapter_1",
        "checkpoint_chapter_n",
        "checkpoint_remaining_batch",
    }:
        conf = confirmations[expected_checkpoint]
        if not (isinstance(conf, dict) and conf.get("approved") is True):
            raise PolicyViolation(
                f"Cannot proceed: checkpoint '{expected_checkpoint}' was not approved.",
                node=state.get("current_node", "unknown"),
                missing_refs=[],
            )


def guard_no_bulk_ref_load(state: VideoWorkflowState) -> None:
    """Guard: Must not load all references at startup."""
    loaded = state.get("loaded_refs", [])
    if len(loaded) >= 4:
        raise PolicyViolation(
            f"Too many refs loaded simultaneously ({len(loaded)}): "
            "references must be loaded per-phase, not all at once.",
            node=state.get("current_node", "unknown"),
            missing_refs=[],
        )


# ═══════════════════════════════════════════════════════════════════
# Workspace & artifact management
# ═══════════════════════════════════════════════════════════════════


def resolve_workspace(workspace_root: str, thread_id: str) -> str:
    return f"{workspace_root}/{thread_id}"


def init_workspace(state: VideoWorkflowState) -> dict:
    """Create workspace directory and set artifact_paths."""
    workspace = str(
        Path(resolve_workspace(state.get("workspace_root", "workspace"), state["thread_id"])).resolve()
    )
    Path(workspace).mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    for logical, relative in ARTIFACT_LAYOUT.items():
        paths[logical] = f"{workspace}/{relative}"

    return {"artifact_paths": paths, "workspace_root": workspace}


def ensure_workspace_ready(state: VideoWorkflowState) -> dict:
    """Ensure per-thread workspace dir exists and artifact_paths are populated."""
    paths = state.get("artifact_paths") or {}
    ws = state.get("workspace_root", "")
    workspace_path = Path(ws) if ws else None
    if (
        not state.get("thread_id")
        or not paths.get("script.md")
        or workspace_path is None
        or not workspace_path.is_dir()
    ):
        return init_workspace(state)
    workspace_path.mkdir(parents=True, exist_ok=True)
    return {"workspace_root": str(workspace_path), "artifact_paths": paths}


def ensure_artifact_parent(path: str | Path) -> Path:
    """Create parent dirs for an artifact file path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def record_creation(state: VideoWorkflowState, logical_name: str) -> dict:
    path = state.get("artifact_paths", {}).get(logical_name)
    if path:
        created = state.get("created_files", [])
        if path not in created:
            created.append(path)
        return {"created_files": created}
    return {}


def record_modification(state: VideoWorkflowState, logical_name: str) -> dict:
    path = state.get("artifact_paths", {}).get(logical_name)
    if path:
        modified = state.get("modified_files", [])
        if path not in modified:
            modified.append(path)
        return {"modified_files": modified}
    return {}


def check_artifact_contract(state: VideoWorkflowState, phase: int) -> list[str]:
    """Verify mandatory artifacts for a phase exist. Returns missing logical names."""
    missing: list[str] = []
    paths = state.get("artifact_paths", {})
    for logical, optional in MANDATORY_ARTIFACTS.items():
        if optional:
            continue
        if phase == 1 and logical not in ("article.md", "script.md", "outline.md"):
            continue
        if phase == 2 and logical not in ("presentation",):
            continue
        p = paths.get(logical)
        if p is None or not Path(p).exists():
            missing.append(logical)
    return missing
