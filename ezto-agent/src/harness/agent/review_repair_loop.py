"""Shared Review ↔ Repair loop for chapter build pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from backend.core.logger import logger
from configs import settings
from harness.agent.loop import AgentResult, ChapterReviewAgent, WebBuildAgent
from harness.services.tools.craft_review import (
    failed_item_ids,
    format_review_failure_report,
    persist_craft_review,
    reconcile_auto_failures,
    run_craft_auto_checks,
)


def _review_incomplete_message(reviewer: ChapterReviewAgent, *, timed_out: bool) -> str:
    pending = [k for k in reviewer.TODO_ITEMS if k not in reviewer._todo_done]
    reason = "审查超时" if timed_out else "审查未完成"
    pending_str = ", ".join(pending[:8])
    msg = f"{reason}：尚有 {len(pending)} 项未勾选"
    if pending_str:
        msg += f"（{pending_str}）"
    msg += "。无明确失败项，未进入修复。"
    return msg


def run_review_repair_loop(
    state: dict[str, Any],
    *,
    chapter_id: str,
    title: str,
    chapter_index: int,
    trace: Callable[[str, str, str], None] | None = None,
    initial_feedback: str | None = None,
) -> tuple[bool, int, int, str | None]:
    """Run Review → Repair cycles until pass, incomplete, or limits hit.

    Returns (review_ok, total_iters_delta, total_tools_delta, last_failure_report).
    """
    review_feedback: str | None = initial_feedback
    review_ok = False
    total_iters = 0
    total_tools = 0
    repairs_done = 0
    last_report: str | None = None

    for round_idx in range(1, settings.chapter_review_max_rounds + 1):
        if trace:
            trace("step", f"Reviewer 子 Agent 第 {round_idx} 轮审查…", "reviewer")

        reviewer = ChapterReviewAgent(state)
        review = reviewer.run(
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
            repair_feedback=review_feedback,
        )
        total_iters += review.iterations
        total_tools += review.tool_calls

        if isinstance(state, dict):
            persist_craft_review(state, chapter_id, reviewer._ctx)
            ws = Path(state.get("workspace_root", "."))
            run_craft_auto_checks(reviewer._ctx, workspace_root=ws, chapter_id=chapter_id)

        flipped = reconcile_auto_failures(reviewer._ctx)
        if flipped and trace:
            trace(
                "step",
                f"自动纠正误 pass → fail：{', '.join(flipped)}（将进入 Repair）",
                "reviewer",
            )
            if isinstance(state, dict):
                persist_craft_review(state, chapter_id, reviewer._ctx)

        failed = failed_item_ids(reviewer._ctx)
        review_ok = reviewer.review_ok and not failed

        if review.success and review_ok:
            break

        last_report = format_review_failure_report(
            reviewer._ctx,
            chapter_id=chapter_id,
            agent_summary=review.content,
            workspace_root=Path(state.get("workspace_root", ".")) if isinstance(state, dict) else None,
        )
        review_feedback = last_report

        if not failed and not flipped:
            return False, total_iters, total_tools, _review_incomplete_message(
                reviewer, timed_out=not review.success,
            )

        if repairs_done >= settings.chapter_repair_max_rounds:
            logger.warning(
                "Chapter %s: repair limit (%d) reached after review round %d; still failing: %s",
                chapter_id,
                settings.chapter_repair_max_rounds,
                round_idx,
                ", ".join(failed) or "see report",
            )
            return False, total_iters, total_tools, (
                f"Repair 已达上限 ({settings.chapter_repair_max_rounds})，"
                f"第 {round_idx} 轮审查仍未通过:\n{last_report}"
            )

        if trace:
            trace("step", f"Repair 子 Agent 修复审查问题（第 {round_idx} 轮）…", "repair")
        logger.info(
            "Chapter %s review round %d: %d failure(s) → Repair (%s)",
            chapter_id, round_idx, len(failed), ", ".join(failed) or "see report",
        )

        repair = WebBuildAgent(state).run(
            phase="repair",
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
            review_feedback=last_report,
        )
        total_iters += repair.iterations
        total_tools += repair.tool_calls
        repairs_done += 1

        if not repair.success:
            return False, total_iters, total_tools, f"Repair failed:\n{repair.content}"

    if not review_ok:
        return False, total_iters, total_tools, (
            "审查在所有轮次后仍未完成"
            + (f"\n{last_report}" if last_report else "")
        )

    return True, total_iters, total_tools, None
