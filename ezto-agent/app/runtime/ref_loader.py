"""Reference loading policy enforcement.

Original SKILL.md rule: references must be loaded per-phase, not all at
once at startup. Each node must verify the required refs are loaded before
proceeding.
"""

from __future__ import annotations

from pathlib import Path

from .state import VideoWorkflowState

# ── Reference path constants ──

from app.core import settings

_REFERENCES_DIR = Path(settings.project_root) / "app" / "references"

REF_PATHS: dict[str, str] = {
    "SCRIPT-STYLE.md": str(_REFERENCES_DIR / "SCRIPT-STYLE.md"),
    "OUTLINE-FORMAT.md": str(_REFERENCES_DIR / "OUTLINE-FORMAT.md"),
    "CHAPTER-CRAFT.md": str(_REFERENCES_DIR / "CHAPTER-CRAFT.md"),
    "THEMES.md": str(_REFERENCES_DIR / "THEMES.md"),
    "AUDIO.md": str(_REFERENCES_DIR / "AUDIO.md"),
    "RECORDING.md": str(_REFERENCES_DIR / "RECORDING.md"),
}

# Per-phase required refs (from skill-flow-parity.md §3)
PHASE_REFS: dict[str, list[str]] = {
    "phase1": ["SCRIPT-STYLE.md", "OUTLINE-FORMAT.md"],
    "chapter": ["CHAPTER-CRAFT.md"],
    "theme": ["THEMES.md"],
    "audio": ["AUDIO.md"],
    "recording": ["RECORDING.md"],
}


class PolicyViolation(Exception):
    """Raised when a node violates a reference-loading policy."""

    def __init__(self, message: str, node: str, missing_refs: list[str]):
        self.node = node
        self.missing_refs = missing_refs
        super().__init__(f"[{node}] policy violation: missing refs {missing_refs} — {message}")


def require_ref_loaded(
    state: VideoWorkflowState,
    ref_name: str,
    *,
    scope: str = "",
    reload_each_time: bool = False,
) -> str:
    """Assert that a reference is loaded, or load it now.

    Args:
        state: Current workflow state (mutated in place).
        ref_name: Key into REF_PATHS (e.g. "CHAPTER-CRAFT.md").
        scope: Scope string for the error message (e.g. "chapter:2").
        reload_each_time: If True, always re-read even if already loaded.

    Returns:
        The loaded file content as a string.

    Raises:
        PolicyViolation: If the ref path is unknown.
    """
    path = REF_PATHS.get(ref_name)
    if path is None:
        raise PolicyViolation(
            f"Unknown reference '{ref_name}'",
            node=state.get("current_node", "unknown"),
            missing_refs=[ref_name],
        )

    full_path = path

    if reload_each_time or ref_name not in state.get("loaded_refs", []):
        _do_load(state, ref_name, full_path)

    return _read_file(full_path)


def _do_load(state: VideoWorkflowState, ref_name: str, full_path: str) -> None:
    """Record a reference as loaded and verify it exists on disk."""
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


def verify_phase_refs(
    state: VideoWorkflowState, phase_key: str
) -> list[str]:
    """Verify all refs for a phase are loaded.

    Returns list of missing ref names (empty = all loaded).
    """
    needed = PHASE_REFS.get(phase_key, [])
    loaded = state.get("loaded_refs", [])
    return [r for r in needed if r not in loaded]


def reset_loaded_refs(state: VideoWorkflowState) -> None:
    """Clear loaded refs (used when transitioning phases)."""
    state["loaded_refs"] = []
