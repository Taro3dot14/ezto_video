"""Chapter build orchestration — sub_agent and agent_team modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core import llm
from backend.core.llm import MODEL_ROLE_WEB_BUILD
from backend.core.logger import logger
from configs import settings
from configs.settings import CHAPTER_BUILD_MODE_LABELS
from harness.agent.loop import AgentResult, ChapterReviewAgent, WebBuildAgent
from harness.agent.system_prompts import TEAM_ACTION_PLAN_SYSTEM, TEAM_MEETING_ROLES
from harness.core.execution import push_event as push_trace_event
from harness.agent.review_repair_loop import run_review_repair_loop
from harness.services.tools.craft.craft_review import (
    failed_item_ids,
    format_review_failure_report,
    persist_craft_review,
    reconcile_auto_failures,
    run_craft_auto_checks,
)
from harness.services.tools.build.typescript import run_typecheck
from harness.services.tools.build.vite import check_vite
from harness.workflow.chapter_brief import format_brief_for_prompt, get_chapter_brief


def chapter_build_mode_label(mode: str | None = None) -> str:
    key = mode or settings.chapter_build_mode
    return CHAPTER_BUILD_MODE_LABELS.get(key, key)


def chapter_has_artifacts(ch_dir: Path) -> bool:
    """True when a prior build left the minimum chapter files on disk."""
    return (ch_dir / "index.tsx").is_file() and (ch_dir / "narrations.ts").is_file()


def format_user_revision_report(
    feedback: str,
    *,
    chapter_id: str,
    title: str,
) -> str:
    """Format checkpoint rejection feedback like a repair failure report."""
    return (
        f"# User checkpoint rejection — {chapter_id} ({title})\n\n"
        "The chapter was reviewed by the user and **rejected**. "
        "Make **targeted edits** to the existing files (prefer `edit_file`). "
        "Do NOT rebuild from scratch.\n\n"
        f"## Required changes\n{feedback.strip()}\n"
    )


def run_chapter_revision_pipeline(
    state: dict[str, Any],
    *,
    chapter_id: str,
    title: str,
    chapter_index: int,
    user_feedback: str,
) -> AgentResult:
    """Apply user checkpoint rejection via repair on existing chapter files."""
    if isinstance(state, dict):
        push_trace_event(
            state,
            "step",
            "验收反馈修订：保留现有文件，执行 Repair…",
            agent="orchestrator",
        )
    report = format_user_revision_report(
        user_feedback,
        chapter_id=chapter_id,
        title=title,
    )
    repair = WebBuildAgent(state).run(
        phase="repair",
        chapter_id=chapter_id,
        title=title,
        chapter_index=chapter_index,
        review_feedback=report,
    )
    if not repair.success:
        return repair

    if isinstance(state, dict):
        _trace(state, "step", "验收修订后 Verify: typecheck + vite…", agent="verify")
    verify = _run_programmatic_verify(state)
    return AgentResult(
        content=verify.content,
        tool_calls=repair.tool_calls + verify.tool_calls,
        iterations=repair.iterations + verify.iterations,
        success=verify.success,
        phase=verify.phase if not verify.success else None,
    )


def _trace(state: dict[str, Any], type_: str, content: str, *, agent: str) -> None:
    push_trace_event(state, type_, content, agent=agent)


def _reviewer_pending_keys(reviewer: ChapterReviewAgent) -> list[str]:
    return [k for k in reviewer.TODO_ITEMS if k not in reviewer._todo_done]


def _run_programmatic_verify(state: dict[str, Any]) -> AgentResult:
    """Run typecheck + check_vite directly — no LLM verify agent."""
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / "presentation"

    tc = run_typecheck(state, cwd=str(ppt))
    if tc.returncode != 0:
        err = (tc.stderr or tc.stdout or "").strip() or f"typecheck exit {tc.returncode}"
        return AgentResult(
            content=f"TypeScript 检查未通过:\n\n{err[:2500]}",
            tool_calls=0,
            iterations=0,
            success=False,
            phase="verify",
        )

    _trace(state, "step", "typecheck 通过", agent="verify")

    vite = check_vite(state, cwd=ppt)
    if not vite.success:
        return AgentResult(
            content=vite.message[:2500],
            tool_calls=0,
            iterations=0,
            success=False,
            phase="verify",
        )

    _trace(state, "step", vite.message[:200], agent="verify")
    return AgentResult(
        content=vite.message,
        tool_calls=0,
        iterations=0,
        success=True,
        phase="verify",
    )


def _review_incomplete_message(
    reviewer: ChapterReviewAgent,
    *,
    timed_out: bool,
) -> str:
    pending = _reviewer_pending_keys(reviewer)
    reason = "审查超时" if timed_out else "审查未完成"
    pending_str = ", ".join(pending[:8])
    msg = f"{reason}：尚有 {len(pending)} 项未勾选"
    if pending_str:
        msg += f"（{pending_str}）"
    msg += "。无明确失败项，未进入修复。"
    return msg


def run_chapter_pipeline(
    state: dict[str, Any],
    *,
    chapter_id: str,
    title: str,
    chapter_index: int = 1,
    total_chapters: int = 1,
    previous_chapters: str = "",
    revision_feedback: str | None = None,
) -> AgentResult:
    """Run chapter build using the configured chapter_build_mode."""
    mode = settings.chapter_build_mode
    label = chapter_build_mode_label(mode)
    logger.info("Chapter build mode=%s (%s) chapter=%s", mode, label, chapter_id)
    if isinstance(state, dict):
        push_trace_event(state, "step", f"章节构建模式: {label}", agent="orchestrator")

    if mode == "sub_agent":
        return _run_sub_agent_pipeline(
            state,
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
            total_chapters=total_chapters,
            previous_chapters=previous_chapters,
            revision_feedback=revision_feedback,
        )
    return _run_agent_team_pipeline(
        state,
        chapter_id=chapter_id,
        title=title,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        previous_chapters=previous_chapters,
        revision_feedback=revision_feedback,
    )


def _run_sub_agent_pipeline(
    state: dict[str, Any],
    *,
    chapter_id: str,
    title: str,
    chapter_index: int,
    total_chapters: int,
    previous_chapters: str,
    revision_feedback: str | None,
) -> AgentResult:
    build = WebBuildAgent(state).run(
        phase="build",
        chapter_id=chapter_id,
        title=title,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        previous_chapters=previous_chapters,
        revision_feedback=revision_feedback,
    )
    if not build.success:
        return build

    review_feedback: str | None = None
    total_iters = build.iterations
    total_tools = build.tool_calls

    def _trace_step(type_: str, content: str, agent: str) -> None:
        _trace(state, type_, content, agent=agent)

    review_ok, review_iters, review_tools, fail_msg = run_review_repair_loop(
        state,
        chapter_id=chapter_id,
        title=title,
        chapter_index=chapter_index,
        trace=_trace_step if isinstance(state, dict) else None,
    )
    total_iters += review_iters
    total_tools += review_tools

    if not review_ok:
        return AgentResult(
            content=fail_msg or "审查未通过",
            tool_calls=total_tools,
            iterations=total_iters,
            success=False,
            phase="review",
        )

    if isinstance(state, dict):
        _trace(state, "step", "Verify 阶段: typecheck + vite…", agent="verify")
    verify = _run_programmatic_verify(state)
    return AgentResult(
        content=verify.content,
        tool_calls=total_tools + verify.tool_calls,
        iterations=total_iters + verify.iterations,
        success=verify.success,
        phase=verify.phase if not verify.success else None,
    )


def _run_agent_team_pipeline(
    state: dict[str, Any],
    *,
    chapter_id: str,
    title: str,
    chapter_index: int,
    total_chapters: int,
    previous_chapters: str,
    revision_feedback: str | None,
) -> AgentResult:
    """agent_team: initial build → [review → meeting → repair]* → verify."""
    if isinstance(state, dict):
        _trace(state, "step", "Agent Team 模式: Builder 初始构建…", agent="builder")

    build = WebBuildAgent(state).run(
        phase="build",
        chapter_id=chapter_id,
        title=title,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        previous_chapters=previous_chapters,
        revision_feedback=revision_feedback,
    )
    if not build.success:
        return build

    builder_history = _format_builder_history(build)
    repair_history = ""
    total_iters = build.iterations
    total_tools = build.tool_calls
    review_ok = False
    last_review_report = ""
    repairs_done = 0

    for round_idx in range(1, settings.chapter_review_max_rounds + 1):
        if isinstance(state, dict):
            _trace(state, "step", f"Agent Team 第 {round_idx} 轮: Reviewer 审查…", agent="reviewer")

        reviewer = ChapterReviewAgent(state)
        review = reviewer.run(
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
            repair_feedback=last_review_report or None,
        )
        total_iters += review.iterations
        total_tools += review.tool_calls
        if isinstance(state, dict):
            persist_craft_review(state, chapter_id, reviewer._ctx)
            ws = Path(state.get("workspace_root", "."))
            run_craft_auto_checks(reviewer._ctx, workspace_root=ws, chapter_id=chapter_id)

        flipped = reconcile_auto_failures(reviewer._ctx)
        if flipped and isinstance(state, dict):
            _trace(
                state,
                "step",
                f"自动纠正误 pass → fail：{', '.join(flipped)}",
                agent="reviewer",
            )
            persist_craft_review(state, chapter_id, reviewer._ctx)

        failed = failed_item_ids(reviewer._ctx)
        review_ok = reviewer.review_ok and not failed
        last_review_report = format_review_failure_report(
            reviewer._ctx,
            chapter_id=chapter_id,
            agent_summary=review.content,
            workspace_root=Path(state.get("workspace_root", ".")) if isinstance(state, dict) else None,
        )

        if review.success and review_ok:
            if isinstance(state, dict):
                _trace(state, "step", f"Agent Team 第 {round_idx} 轮: 自检全部通过 ✅", agent="reviewer")
            break

        if not failed and not flipped:
            return AgentResult(
                content=_review_incomplete_message(reviewer, timed_out=not review.success),
                tool_calls=total_tools,
                iterations=total_iters,
                success=False,
                phase="review",
            )

        if repairs_done >= settings.chapter_repair_max_rounds:
            return AgentResult(
                content=(
                    f"Agent Team: Repair 已达上限 ({settings.chapter_repair_max_rounds})，"
                    f"第 {round_idx} 轮审查仍未通过:\n{last_review_report}"
                ),
                tool_calls=total_tools,
                iterations=total_iters,
                success=False,
                phase="review",
            )

        if isinstance(state, dict):
            _trace(state, "step", f"Agent Team 第 {round_idx} 轮: Review + Builder + Repair 开会…", agent="team")
        action_plan = _run_team_meeting(
            state,
            round_num=round_idx,
            title=title,
            review_report=last_review_report,
            builder_history=builder_history,
            repair_history=repair_history,
        )

        if isinstance(state, dict):
            _trace(state, "step", f"Agent Team 第 {round_idx} 轮: Repair 执行方案…", agent="repair")
        repair = WebBuildAgent(state).run(
            phase="repair",
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
            team_action_plan=action_plan,
        )
        total_iters += repair.iterations
        total_tools += repair.tool_calls
        if not repair.success:
            return AgentResult(
                content=f"Agent Team repair failed (round {round_idx}):\n{repair.content}",
                tool_calls=total_tools,
                iterations=total_iters,
                success=False,
            )
        repair_history = _append_history(repair_history, f"### Repair round {round_idx}\n", repair)
        repairs_done += 1

    if not review_ok:
        if isinstance(state, dict):
            _trace(state, "step", "Agent Team: 最终 Reviewer 复审…", agent="reviewer")
        reviewer = ChapterReviewAgent(state)
        final = reviewer.run(
            chapter_id=chapter_id,
            title=title,
            chapter_index=chapter_index,
        )
        total_iters += final.iterations
        total_tools += final.tool_calls
        review_ok = reviewer.review_ok
        if isinstance(state, dict):
            persist_craft_review(state, chapter_id, reviewer._ctx)
        last_review_report = format_review_failure_report(
            reviewer._ctx,
            chapter_id=chapter_id,
            agent_summary=final.content,
            workspace_root=Path(state.get("workspace_root", ".")) if isinstance(state, dict) else None,
        )

    if not review_ok:
        return AgentResult(
            content=(
                f"Agent Team: 自检在 {settings.chapter_review_max_rounds} 轮后仍未完成\n"
                f"{last_review_report}"
            ),
            tool_calls=total_tools,
            iterations=total_iters,
            success=False,
            phase="review",
        )

    if isinstance(state, dict):
        _trace(state, "step", "Agent Team 模式: Verify (typecheck + vite)…", agent="verify")
    verify = _run_programmatic_verify(state)
    return AgentResult(
        content=verify.content,
        tool_calls=total_tools + verify.tool_calls,
        iterations=total_iters + verify.iterations,
        success=verify.success,
        phase=verify.phase if not verify.success else None,
    )


# Backward-compatible alias for tests / imports
_run_team_discuss_pipeline = _run_agent_team_pipeline


def _format_builder_history(build: AgentResult) -> str:
    parts = [f"## Build summary\n{build.content}"]
    if build.history:
        parts.append(f"## Build tool history\n{build.history}")
    return "\n\n".join(parts)


def _append_history(existing: str, header: str, result: AgentResult) -> str:
    block = f"{header}{result.content}"
    if result.history:
        block += f"\n\nTool history:\n{result.history}"
    return f"{existing}\n\n{block}".strip() if existing else block


def _run_team_meeting(
    state: dict[str, Any],
    *,
    round_num: int,
    title: str,
    review_report: str,
    builder_history: str,
    repair_history: str,
) -> str:
    """Review + Builder + Repair discuss; facilitator outputs repair action plan."""
    context = (
        f"# Chapter: {title} — Team meeting round {round_num}\n\n"
        f"## Review report + checklist\n{review_report}\n\n"
        f"## Builder history\n{builder_history}\n"
    )
    if repair_history:
        context += f"\n## Prior repair rounds\n{repair_history}\n"

    transcript: list[str] = []
    messages: list[dict[str, str]] = [{"role": "user", "content": context}]

    for role_name, role_system in TEAM_MEETING_ROLES:
        reply = llm.chat(
            messages=[
                {"role": "system", "content": role_system},
                *messages,
            ],
            temperature=0.4,
            role=MODEL_ROLE_WEB_BUILD,
        )
        block = f"### {role_name}\n{reply.strip()}"
        transcript.append(block)
        if isinstance(state, dict):
            push_trace_event(state, "llm", f"[Team/{role_name}] {reply[:1500]}", agent=f"team-{role_name.lower()}")
        messages.append({"role": "assistant", "content": block})

    plan = llm.chat(
        messages=[
            {"role": "system", "content": TEAM_ACTION_PLAN_SYSTEM},
            {"role": "user", "content": "\n\n".join(transcript)},
        ],
        temperature=0.2,
        role=MODEL_ROLE_WEB_BUILD,
    )
    if isinstance(state, dict):
        push_trace_event(state, "llm", f"## Team Action Plan (R{round_num})\n{plan[:2500]}", agent="team-plan")
    return plan.strip()
