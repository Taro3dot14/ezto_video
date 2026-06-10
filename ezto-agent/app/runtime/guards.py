"""Policy guards for prohibited behaviors.

Each guard checks a condition before a node executes. If the condition
is violated, a PolicyViolation is raised.
"""

from __future__ import annotations

from .ref_loader import PolicyViolation, verify_phase_refs
from .state import VideoWorkflowState


def guard_chapter_refs_loaded(state: VideoWorkflowState) -> None:
    """Guard: CHAPTER-CRAFT.md must be loaded before writing a chapter.

    Original SKILL.md rule: "每次实现单章都要重新读取，不允许只在任务
    开始时读一次。"
    """
    node = state.get("current_node", "unknown")
    missing = verify_phase_refs(state, "chapter")
    if missing:
        raise PolicyViolation(
            "Chapter refs not loaded — each chapter must re-read CHAPTER-CRAFT.md",
            node=node,
            missing_refs=missing,
        )


def guard_chapter_1_not_parallel(state: VideoWorkflowState) -> None:
    """Guard: Chapter 1 must be built on the main thread.

    Original SKILL.md rule: "第 1 章不能被并行化，也不能跳过人工验收。"
    """
    # This guard is structural (enforced by graph topology), but we add a
    # runtime check anyway for defense-in-depth.
    node = state.get("current_node", "unknown")
    if "parallel" in node:
        raise PolicyViolation(
            "Chapter 1 must be built on the main thread, not in parallel.",
            node=node,
            missing_refs=[],
        )


def guard_not_skip_checkpoint(
    state: VideoWorkflowState,
    expected_checkpoint: str,
) -> None:
    """Guard: Nodes after a checkpoint must have user confirmation.

    Verifies that the corresponding user_confirmations entry exists.
    """
    confirmations = state.get("user_confirmations", {})
    if expected_checkpoint not in confirmations:
        raise PolicyViolation(
            f"Cannot proceed: checkpoint '{expected_checkpoint}' "
            "has not been confirmed by the user.",
            node=state.get("current_node", "unknown"),
            missing_refs=[],
        )


def guard_no_bulk_ref_load(state: VideoWorkflowState) -> None:
    """Guard: Must not load all references at startup.

    Original SKILL.md rule: references must be loaded per-phase,
    not all at once. We verify that loaded_refs doesn't contain refs
    from multiple phases simultaneously.
    """
    loaded = state.get("loaded_refs", [])
    if len(loaded) >= 4:
        raise PolicyViolation(
            f"Too many refs loaded simultaneously ({len(loaded)}): "
            "references must be loaded per-phase, not all at once.",
            node=state.get("current_node", "unknown"),
            missing_refs=[],
        )
