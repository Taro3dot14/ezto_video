"""Autonomous agent loop — self-driving tool-use engine."""

from __future__ import annotations

import json
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core import llm
from backend.core.llm import ChatResult, ToolCall, MODEL_ROLE_WEB_BUILD
from backend.core.logger import logger
from configs import settings

from harness.core.execution import push_event as push_trace_event
from harness.core.token_usage import bind_workflow_thread, reset_workflow_thread
from harness.workflow.chapter_brief import format_brief_for_prompt, get_chapter_brief
from .stall import StallDetector
from .tools import (
    ChapterSessionState,
    execute_tool,
    format_result_for_llm,
    make_build_agent_tools,
    push_tool_audit,
)
from .tools.registry import AgentTool
from .tools.legacy_parser import extract_all
from harness.workflow.chapter_policies import auto_validate_chapter
from harness.workflow.step_indexing import todo_index_tsx_label, todo_narrations_label
from .system_prompts import (
    BUILD_ONLY_SYSTEM,
    VERIFY_ONLY_SYSTEM,
    REPAIR_SYSTEM,
    REVIEW_AGENT_SYSTEM,
)

_MAX_MESSAGE_TURNS = 8


@dataclass
class AgentResult:
    content: str
    tool_calls: int = 0
    iterations: int = 0
    success: bool = True
    files_created: list[str] = field(default_factory=list)
    history: str = ""
    phase: str | None = None


_AGENT_ROLE_LABELS = {
    "builder": "构建",
    "reviewer": "审查",
    "repair": "修复",
    "verify": "验收检查",
}

_THINKING_SNIPPET_MARKERS = (
    "now let me",
    "let me run",
    "i'll run",
    "i will run",
    "let me check",
    "i need to",
)


def format_agent_timeout_message(
    agent_role: str,
    max_iterations: int,
    last_content: str,
) -> str:
    """Human-readable timeout — never surface bare LLM planning text as the error."""
    label = _AGENT_ROLE_LABELS.get(agent_role, "Agent")
    snippet = last_content.strip().replace("\n", " ")
    lower = snippet.lower()
    if snippet and any(m in lower[:80] for m in _THINKING_SNIPPET_MARKERS):
        snippet = ""
    if len(snippet) > 100:
        snippet = snippet[:100] + "…"
    msg = f"{label}阶段在 {max_iterations} 轮内未完成（未调用 done()）。"
    if snippet:
        msg += f" 最后输出：{snippet}"
    msg += " 请查看执行日志或重试。"
    return msg


def run_agent_custom(
    *,
    tools: list[AgentTool],
    system_prompt: str,
    user_prompt: str,
    state: Any = None,
    max_iterations: int = 25,
    chapter_id: str = "chapter_1",
) -> AgentResult:
    _, ctx = make_build_agent_tools(state or {}, chapter_id=chapter_id)
    return _run_loop(
        tools=tools,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_iterations=max_iterations,
        state=state,
        ctx=ctx,
        chapter_id=chapter_id,
    )


def _trim_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trim history while keeping assistant+tool message chains intact."""
    if len(messages) <= 2 + _MAX_MESSAGE_TURNS * 3:
        return messages

    head = messages[:2]
    rest = messages[2:]

    # Collect complete turns from the tail (newest first).
    turns: list[list[dict[str, Any]]] = []
    i = len(rest) - 1
    while i >= 0 and len(turns) < _MAX_MESSAGE_TURNS:
        if rest[i]["role"] == "tool":
            tools: list[dict[str, Any]] = []
            while i >= 0 and rest[i]["role"] == "tool":
                tools.insert(0, rest[i])
                i -= 1
            if i < 0 or rest[i]["role"] != "assistant" or not rest[i].get("tool_calls"):
                continue
            turns.insert(0, [rest[i], *tools])
            i -= 1
        else:
            turns.insert(0, [rest[i]])
            i -= 1

    if not turns:
        return messages

    tail = [m for turn in turns for m in turn]
    return head + [{"role": "user", "content": "[Earlier conversation truncated]"}] + tail


def _sanitize_tool_chains(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure OpenAI tool-call protocol: every tool follows assistant tool_calls."""
    cleaned: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")

        if role == "assistant" and msg.get("tool_calls"):
            expected_ids = [tc.get("id") for tc in msg["tool_calls"] if tc.get("id")]
            tool_msgs: list[dict[str, Any]] = []
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                tool_msgs.append(messages[j])
                j += 1
            got_ids = {t.get("tool_call_id") for t in tool_msgs}
            if expected_ids and set(expected_ids).issubset(got_ids):
                cleaned.append(msg)
                cleaned.extend(tool_msgs)
                i = j
                continue
            # Incomplete pairing — keep text only, drop broken tool_calls.
            stripped = dict(msg)
            stripped.pop("tool_calls", None)
            cleaned.append(stripped)
            i += 1
            continue

        if role == "tool":
            prev = cleaned[-1] if cleaned else None
            if prev and prev.get("role") == "assistant" and prev.get("tool_calls"):
                cleaned.append(msg)
            i += 1
            continue

        cleaned.append(msg)
        i += 1
    return cleaned


def _openai_tools(tools: list[AgentTool]) -> list[dict[str, Any]]:
    return [t.to_openai_tool() for t in tools]


def _tool_call_to_api(tc: ToolCall) -> dict[str, Any]:
    return {
        "id": tc.id,
        "type": "function",
        "function": {
            "name": tc.name,
            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
        },
    }


def _assistant_message(
    *,
    content: str,
    tool_calls: list[ToolCall] | None = None,
    reasoning_content: str | None = None,
) -> dict[str, Any]:
    """Build assistant message for API history (includes thinking-mode fields)."""
    msg: dict[str, Any] = {"role": "assistant", "content": content or None}
    if reasoning_content:
        msg["reasoning_content"] = reasoning_content
    if tool_calls:
        msg["tool_calls"] = [_tool_call_to_api(tc) for tc in tool_calls]
    return msg


def _execute_one(
    tool_name: str,
    arguments: dict[str, Any],
    tools: list[AgentTool],
    *,
    ppt: Path,
    chapter_id: str,
) -> tuple[str, bool]:
    """Legacy wrapper — delegates to execute_tool."""
    result, _rec = execute_tool(
        tool_name, arguments, tools,
        ppt=ppt, chapter_id=chapter_id,
        post_validate=_maybe_auto_validate,
    )
    return format_result_for_llm(tool_name, result), result.done


def _maybe_auto_validate(
    tool_name: str,
    arguments: dict[str, Any],
    output: str,
    *,
    ppt: Path,
    chapter_id: str,
) -> str:
    if tool_name not in ("write_file", "write_narrations", "edit_file"):
        return output
    path = arguments.get("path", "")
    if tool_name == "write_narrations":
        path = f"presentation/src/chapters/{arguments.get('chapter_id', chapter_id)}/narrations.ts"
    if not str(path).endswith((".tsx", ".ts", ".css")):
        return output
    hint = auto_validate_chapter(ppt, chapter_id, written_path=str(path))
    if hint:
        return output + "\n\n" + hint
    return output


def _run_loop(
    *,
    tools: list[AgentTool],
    system_prompt: str,
    user_prompt: str,
    max_iterations: int,
    state: Any = None,
    ctx: ChapterSessionState | dict[str, Any] | None = None,
    chapter_id: str = "chapter_1",
    trace_build_todo: bool = False,
    agent_role: str = "builder",
) -> AgentResult:
    use_native = settings.agent_use_native_tools
    if not use_native:
        logger.warning(
            "agent_use_native_tools=False — legacy text parser path is deprecated; "
            "set agent_use_native_tools=True for production.",
        )
    ws = Path(state.get("workspace_root", ".")) if isinstance(state, dict) else Path(".")
    ppt = ws / "presentation"

    if use_native:
        full_system = system_prompt.strip()
    else:
        tool_manifest = "\n\n".join(t.to_prompt_block() for t in tools)
        full_system = f"{system_prompt.strip()}\n\n## Available Tools\n\n{tool_manifest}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_prompt},
    ]

    tool_calls_count = 0
    last_content = ""
    history_lines: list[str] = []
    stall = StallDetector()
    openai_tools = _openai_tools(tools) if use_native else None

    def _push(tp: str, msg: str) -> None:
        if state is not None and isinstance(state, dict):
            push_trace_event(state, tp, msg, agent=agent_role)

    thread_ctx = (
        bind_workflow_thread(state.get("thread_id"))
        if isinstance(state, dict) and state.get("thread_id")
        else None
    )

    try:
        for iteration in range(max_iterations):
            logger.debug("Agent[%d/%d] tool_calls=%d", iteration + 1, max_iterations, tool_calls_count)

            messages = _sanitize_tool_chains(_trim_messages(messages))
            native_calls: list[ToolCall] = []
            assistant_content = ""
            reasoning_content: str | None = None

            if use_native:
                chat_result: ChatResult = llm.chat_with_tools(
                    messages=messages, tools=openai_tools, temperature=0.0,
                    role=MODEL_ROLE_WEB_BUILD,
                )
                assistant_content = chat_result.content or ""
                reasoning_content = chat_result.reasoning_content
                native_calls = chat_result.tool_calls
                parsed_list = [(tc.name, tc.arguments) for tc in native_calls]
                last_content = assistant_content or str(parsed_list)
            else:
                response = llm.chat(messages=messages, temperature=0.0, role=MODEL_ROLE_WEB_BUILD)
                last_content = response
                assistant_content = response
                parsed_list = extract_all(response)

            think_text = (reasoning_content or "").strip() or assistant_content.strip()
            if think_text:
                logger.info("🧠 Agent: %s", think_text[:200])
                _push("llm", think_text)

            if not parsed_list:
                logger.warning("Agent: no tool call in response")
                nudge = "Call a tool to continue, or call done(summary=...) if task is complete."
                if agent_role == "builder" and ctx is not None:
                    session = ctx if isinstance(ctx, ChapterSessionState) else None
                    chapter_context_read = (
                        session.chapter_context_read if session
                        else bool(ctx.get("chapter_context_read"))
                    )
                    narrations_written = (
                        session.narrations_written if session
                        else bool(ctx.get("narrations_written"))
                    )
                    index_tsx_written = (
                        session.index_tsx_written if session
                        else bool(ctx.get("index_tsx_written"))
                    )
                    preflight_done = (
                        session.preflight_done if session
                        else bool(ctx.get("preflight_done"))
                    )
                    if chapter_context_read and not narrations_written:
                        nudge = (
                            "Next required step: write_narrations(chapter_id, lines=[...]) "
                            "— one string per code step 0..N-1."
                        )
                    elif narrations_written and not index_tsx_written:
                        nudge = (
                            f"Next required step: write_file index.tsx + index.css "
                            f"under presentation/src/chapters/{chapter_id}/ "
                            "(SceneChrome + lx-* + mot-* per step)."
                        )
                    elif index_tsx_written and not preflight_done:
                        nudge = "Next: craft_auto_check — fix NO_AI_SLOP before update_registry."
                _push("step", "⚠️ 调工具继续，或调 done() 结束")
                if use_native:
                    messages.append(_assistant_message(
                        content=assistant_content or "(no tool call)",
                        reasoning_content=reasoning_content,
                    ))
                else:
                    messages.append({"role": "assistant", "content": assistant_content or "(no tool call)"})
                messages.append({
                    "role": "user",
                    "content": nudge,
                })
                continue

            outputs: list[str] = []
            done_summary: str | None = None

            for tool_name, arguments in parsed_list:
                stall.record(tool_name, arguments)

                tool_result, exec_rec = execute_tool(
                    tool_name, arguments, tools,
                    ppt=ppt, chapter_id=chapter_id,
                    post_validate=_maybe_auto_validate,
                    session=ctx if isinstance(ctx, ChapterSessionState) else None,
                )
                if tool_result.done:
                    done_summary = tool_result.message
                    break

                shaped = format_result_for_llm(tool_name, tool_result)
                log_args = exec_rec.args_summary
                history_lines.append(f"{tool_name}: {shaped[:300]}")
                if tool_name == "todolist_status" and trace_build_todo:
                    _push("todo", shaped)
                if isinstance(state, dict):
                    push_tool_audit(state, exec_rec, agent=agent_role)
                outputs.append(shaped)
                tool_calls_count += 1

            if done_summary is not None:
                logger.info("Agent done: %s", done_summary[:200])
                return AgentResult(
                    content=done_summary, tool_calls=tool_calls_count,
                    iterations=iteration + 1, success=True,
                    history="\n".join(history_lines[-40:]),
                )

            if use_native and native_calls:
                messages.append(_assistant_message(
                    content=assistant_content,
                    tool_calls=native_calls,
                    reasoning_content=reasoning_content,
                ))
                for tc, out in zip(native_calls, outputs):
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
            else:
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"{len(parsed_list)} tool(s) executed:\n\n"
                        + "\n".join(f"[{parsed_list[i][0]}]:\n```\n{outputs[i]}\n```"
                                    for i in range(len(outputs)))
                        + "\n\nContinue. Update todo_list and call more tools or done()."
                    ),
                })

            if stall_msg := stall.check():
                logger.warning("Agent stall: %s", stall_msg)
                _push("step", f"⚠️ {stall_msg}")
                messages.append({"role": "user", "content": stall_msg})
                stall = StallDetector()

        logger.warning("Agent reached max iterations (%d) without calling done()", max_iterations)
        timeout_msg = format_agent_timeout_message(agent_role, max_iterations, last_content)
        _push("step", timeout_msg)
        return AgentResult(
            content=timeout_msg,
            tool_calls=tool_calls_count,
            iterations=max_iterations,
            success=False,
            history="\n".join(history_lines[-40:]),
            phase=agent_role,
        )
    finally:
        if thread_ctx is not None:
            reset_workflow_thread(thread_ctx)


class WebBuildAgent:
    TODO_BUILD: dict[str, str] = {
        "SOURCE_READ": "read_chapter_context (layout + MOTION-SYSTEM + presets) + read_reference(CHAPTER-CRAFT.md)",
        "NARRATIONS_TS": todo_narrations_label(),
        "INDEX_TSX": todo_index_tsx_label(),
        "PREFLIGHT": "craft_auto_check — fix NO_AI_SLOP (emoji/slop) in TSX+CSS before registry",
        "REGISTRY": "Call update_registry",
    }
    TODO_VERIFY: dict[str, str] = {
        "TYPECHECK": "Run typecheck and fix until pass",
        "VITE_CHECK": "Call check_vite to verify build",
    }
    TODO_REPAIR: dict[str, str] = {
        "REPAIR": "Fix all reviewer-reported failures",
    }

    _PHASE_TODOS: dict[str, dict[str, str]] = {
        "build": TODO_BUILD,
        "verify": TODO_VERIFY,
        "repair": TODO_REPAIR,
    }

    _PHASE_SYSTEM: dict[str, str] = {
        "build": BUILD_ONLY_SYSTEM,
        "verify": VERIFY_ONLY_SYSTEM,
        "repair": REPAIR_SYSTEM,
    }

    def __init__(self, state: Any):
        self._state = state
        self._phase = "build"
        self._todo_items: dict[str, str] = dict(self.TODO_BUILD)
        self._todo_done: set[str] = set()
        self._chapter_id = "chapter_1"
        self._chapter_title = ""

        def mark(item: str | list[str], *, result: str = "pass", reason: str = "", fix: str = "") -> str:
            from harness.services.tools.craft.craft_review import resolve_todo_item_id
            _ = result, reason, fix
            items = [item] if isinstance(item, str) else item
            results = []
            for raw in items:
                i = resolve_todo_item_id(raw, self._todo_items)
                if i is None:
                    valid = ", ".join(self._todo_items)
                    results.append(f"\u274c Unknown: {raw}. Valid IDs: {valid}")
                    continue
                if i in self._todo_done:
                    results.append(f"\u2139\ufe0f {i} already done")
                    continue
                self._todo_done.add(i)
                results.append(f"\u2705 {i}: {self._todo_items[i]}")
            status = self._todo_status()
            if isinstance(state, dict) and self._phase == "build":
                push_trace_event(state, "todo", status, agent="builder")
            return "\n".join(results) + "\n" + status

        def status() -> str:
            return self._todo_status()

        def verify(summary: str) -> str:
            r = [i for i in self._todo_items if i not in self._todo_done]
            if r:
                return f"\u274c Cannot call done() - remaining: {', '.join(r)}"
            return f"[DONE] {summary}"

        self._mark = mark
        self._verify = verify
        self._tools: list[AgentTool] = []
        self._ctx: ChapterSessionState | dict[str, Any] = ChapterSessionState()

    def _bind_chapter(
        self,
        chapter_id: str,
        title: str,
        *,
        chapter_index: int = 1,
        tool_profile: str = "builder",
        preset_review_ok: bool = False,
    ) -> None:
        self._chapter_id = chapter_id
        self._chapter_title = title
        self._tools, self._ctx = make_build_agent_tools(
            self._state,
            chapter_id=chapter_id,
            chapter_title=title,
            chapter_index=chapter_index,
            tool_profile=tool_profile,
            preset_review_ok=preset_review_ok,
            get_todo_status=self._todo_status,
            mark_todo_done=self._mark,
            verify_all_done=self._verify,
        )

    def _todo_status(self) -> str:
        total = len(self._todo_items)
        done = len(self._todo_done)
        lines = [f"\u2705 [{done}/{total}]"]
        for k, v in self._todo_items.items():
            m = "\u2705" if k in self._todo_done else "\u2610"
            lines.append(f"  {m} {v}")
        return "\n".join(lines)

    def run(
        self,
        *,
        phase: str = "build",
        chapter_id: str,
        title: str,
        chapter_index: int = 1,
        total_chapters: int = 1,
        previous_chapters: str = "",
        revision_feedback: str | None = None,
        review_feedback: str | None = None,
        build_plan: str | None = None,
        team_action_plan: str | None = None,
        preset_review_ok: bool = False,
    ) -> AgentResult:
        self._phase = phase
        self._todo_done.clear()
        self._todo_items = dict(self._PHASE_TODOS.get(phase, self.TODO_BUILD))

        profile = {
            "build": "builder",
            "verify": "verify",
            "repair": "repair",
        }.get(phase, "builder")

        self._bind_chapter(
            chapter_id, title,
            chapter_index=chapter_index,
            tool_profile=profile,
            preset_review_ok=preset_review_ok or phase == "verify",
        )

        brief = get_chapter_brief(self._state, chapter_id, chapter_index)
        user_prompt = format_brief_for_prompt(brief, title)
        user_prompt += (
            f"\n\nChapter {chapter_index}/{total_chapters}.\n"
            f"## Paths (fixed — do not explore)\n"
            f"- narrations: presentation/src/chapters/{chapter_id}/narrations.ts\n"
            f"- chapter TSX: presentation/src/chapters/{chapter_id}/index.tsx\n"
            f"- chapter CSS: presentation/src/chapters/{chapter_id}/index.css\n"
            f"- registry: presentation/src/registry/chapters.ts\n"
            f"- article + layout + motion templates: call read_chapter_context() once\n"
        )
        if phase == "build":
            user_prompt += (
                "Call todolist_status() then read_chapter_context + read_reference(CHAPTER-CRAFT.md).\n"
                "read_chapter_context includes MOTION-SYSTEM.md + mot-* presets — pick motion before index.tsx.\n"
                "**Icons:** inline SVG or CSS shapes only — **never emoji** (NO_AI_SLOP hard-fail). "
                "Run craft_auto_check after index.tsx+css; fix emoji before update_registry."
            )
        elif phase == "verify":
            user_prompt += "Craft review passed. Run typecheck then check_vite."
        elif phase == "repair":
            user_prompt += (
                "Execute the Reviewer failure report below. "
                "Use ONLY theme tokens from the report — never invent `--bg`. "
                "Prefer **edit_file** for surgical fixes; avoid full rewrites.\n"
            )
            ws_root = Path(self._state.get("workspace_root", ".")) if isinstance(self._state, dict) else None
            if ws_root:
                from harness.workflow.css_projection_checks import format_theme_token_catalog
                catalog = format_theme_token_catalog(ws_root / "presentation")
                if catalog:
                    user_prompt += f"\n\n{catalog}\n"

        if team_action_plan:
            user_prompt += f"\n\n## Team Action Plan (execute exactly)\n{team_action_plan[:6000]}"
        elif build_plan:
            user_prompt += f"\n\n## Team Build Plan (binding)\n{build_plan[:6000]}"
        if previous_chapters:
            user_prompt += f"\n\n## Previous chapter style reference\n{previous_chapters[:2000]}"
        if revision_feedback:
            user_prompt += (
                "\n\n## User review feedback (MUST address)\n"
                "The previous build was rejected at checkpoint. Revise the chapter to fix:\n"
                f"{revision_feedback}"
            )
        if review_feedback:
            user_prompt += (
                "\n\n## Reviewer failure report (MUST fix all)\n"
                f"{review_feedback}"
            )
            if phase == "repair" and isinstance(self._state, dict):
                ws_root = Path(self._state.get("workspace_root", "."))
                ch_dir = ws_root / "presentation" / "src" / "chapters" / chapter_id
                snippets: list[str] = ["\n\n## Current chapter files (for edit_file — do not re-read bundle)"]
                for fname in ("index.tsx", "index.css", "narrations.ts"):
                    fp = ch_dir / fname
                    if fp.is_file():
                        text = fp.read_text(encoding="utf-8", errors="replace")
                        snippets.append(f"### {fname}\n```\n{text[:4500]}\n```")
                user_prompt += "\n".join(snippets)

        system_prompt = self._PHASE_SYSTEM.get(phase, BUILD_ONLY_SYSTEM)

        agent_role = {"build": "builder", "repair": "repair", "verify": "verify"}.get(phase, "builder")

        return _run_loop(
            tools=self._tools,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_iterations=settings.web_build_agent_max_iterations,
            state=self._state,
            ctx=self._ctx,
            chapter_id=chapter_id,
            trace_build_todo=(phase == "build"),
            agent_role=agent_role,
        )


def _craft_label(item_id: str) -> str:
    from harness.services.tools.craft.craft_review import _ITEM_BY_ID
    craft = _ITEM_BY_ID.get(item_id)
    return f"{item_id}: {craft.label}" if craft else item_id


class ChapterReviewAgent:
    @classmethod
    def _build_todo_items(cls, *, recheck_ids: list[str] | None = None) -> dict[str, str]:
        from harness.services.tools.craft.craft_review import reviewer_todo_items
        return reviewer_todo_items(recheck_ids=recheck_ids)

    def __init__(self, state: Any):
        self._state = state
        self.TODO_ITEMS = self._build_todo_items()
        self._todo_done: set[str] = set()
        self._chapter_id = "chapter_1"
        self._tools: list[AgentTool] = []
        self._ctx: ChapterSessionState | dict[str, Any] = ChapterSessionState()

        def mark(item: str | list[str], *, result: str = "pass", reason: str = "", fix: str = "") -> str:
            from harness.services.tools.craft.craft_review import (
                REVIEW_BUNDLE_TODO,
                format_attest_ok_message,
                resolve_todo_item_id,
                try_check_craft_todo_item,
            )

            verdict = result.lower().strip()
            if verdict not in ("pass", "fail"):
                return f'\u274c result must be "pass" or "fail", got: {result!r}'

            items = [item] if isinstance(item, str) else item
            results = []
            for raw in items:
                i = resolve_todo_item_id(raw, self.TODO_ITEMS)
                if i is None:
                    valid = ", ".join(self.TODO_ITEMS)
                    results.append(f"\u274c Unknown: {raw}. Valid IDs: {valid}")
                    continue
                if i in self._todo_done:
                    results.append(f"\u2139\ufe0f {i} already reviewed")
                    continue
                check_result = "pass" if i == REVIEW_BUNDLE_TODO else verdict
                check_reason = "" if i == REVIEW_BUNDLE_TODO else reason
                check_fix = "" if i == REVIEW_BUNDLE_TODO else fix
                if check_result == "fail":
                    if not check_reason.strip():
                        results.append(
                            f"\u274c {i}: result=fail requires reason (problem + file/step)"
                        )
                        continue
                    if not check_fix.strip():
                        results.append(
                            f"\u274c {i}: result=fail requires fix (concrete repair plan)"
                        )
                        continue
                err = try_check_craft_todo_item(
                    self._ctx, i,
                    result=check_result, reason=check_reason, fix=check_fix,
                )
                if err:
                    results.append(err)
                    continue
                self._todo_done.add(i)
                if i == REVIEW_BUNDLE_TODO:
                    results.append(f"\u2705 {i}: {self.TODO_ITEMS[i]}")
                else:
                    results.append(format_attest_ok_message(self._ctx, i))
            status = self._todo_status()
            if isinstance(self._state, dict):
                from harness.services.tools.craft.craft_review import push_craft_checklist_event
                push_craft_checklist_event(self._state, self._ctx)
            return "\n".join(results) + "\n" + status

        def verify(summary: str) -> str:
            store = self._ctx.get("craft_review", {}).get("items", {})

            def _needs_attestation(item_id: str) -> bool:
                if item_id in self._todo_done:
                    return False
                entry = store.get(item_id, {})
                st = entry.get("state", "pending")
                ev = str(entry.get("evidence", ""))
                if st == "pass" and (ev.startswith("auto:") or ev.startswith("precheck:")):
                    return False
                return True

            remaining = [i for i in self.TODO_ITEMS if _needs_attestation(i)]
            if remaining:
                preview = ", ".join(remaining[:6])
                extra = f" (+{len(remaining) - 6} more)" if len(remaining) > 6 else ""
                return f"\u274c Cannot call done() - review remaining manual items: {preview}{extra}"

            store = self._ctx.get("craft_review", {}).get("items", {})
            failed = [
                k for k in self.TODO_ITEMS
                if k != "REVIEW_BUNDLE"
                and store.get(k, {}).get("state") == "fail"
            ]
            if failed:
                preview = ", ".join(failed[:8])
                return (
                    f"[DONE] Review complete with failures ({preview}) "
                    f"— Repair will fix. {summary}"
                )
            if not self._ctx.get("review_ok"):
                return (
                    "\u274c Cannot call done() - checklist not fully passed. "
                    "Mark remaining items with todolist_check (pass or fail), "
                    "never pass to unblock when you mean fail."
                )
            return f"[DONE] {summary}"

        self._mark = mark
        self._verify = verify
        self._recheck_mode = False
        self._passed_frozen: list[str] = []

    def _todo_status(self) -> str:
        total = len(self.TODO_ITEMS)
        done = len(self._todo_done)
        store = self._ctx.get("craft_review", {}).get("items", {})
        lines = [f"Reviewed [{done}/{total}]"]
        if self._recheck_mode and self._passed_frozen:
            lines.append("  --- 已通过（本轮跳过）---")
            for pid in self._passed_frozen:
                craft_label = _craft_label(pid)
                lines.append(f"  \u2705 [跳过] {craft_label}")
            lines.append("  --- 本轮复审 ---")
        for k, v in self.TODO_ITEMS.items():
            if k not in self._todo_done:
                m = "\u2610"
            elif k == "REVIEW_BUNDLE":
                m = "\u2705"
            else:
                st = store.get(k, {}).get("state")
                m = "\u2705" if st == "pass" else "\u274c" if st == "fail" else "\u2705"
            lines.append(f"  {m} {v}")
        return "\n".join(lines)

    @property
    def review_ok(self) -> bool:
        return bool(self._ctx.get("review_ok"))

    def craft_checklist_text(self) -> str:
        from harness.services.tools.craft.craft_review import format_craft_checklist
        return format_craft_checklist(self._ctx)

    def run(
        self,
        *,
        chapter_id: str,
        title: str,
        chapter_index: int = 1,
        repair_feedback: str | None = None,
    ) -> AgentResult:
        self._chapter_id = chapter_id
        self._todo_done.clear()
        self._recheck_mode = False
        self._passed_frozen = []
        self._tools, self._ctx = make_build_agent_tools(
            self._state,
            chapter_id=chapter_id,
            chapter_title=title,
            tool_profile="reviewer",
            get_todo_status=self._todo_status,
            mark_todo_done=self._mark,
            verify_all_done=self._verify,
        )

        from harness.services.tools.craft.craft_review import (
            load_craft_review_into_ctx,
            passed_item_ids,
            prepare_recheck_round,
        )

        if repair_feedback and isinstance(self._state, dict):
            if load_craft_review_into_ctx(self._ctx, self._state, chapter_id):
                recheck_ids = prepare_recheck_round(self._ctx)
                self._passed_frozen = passed_item_ids(self._ctx)
                self._recheck_mode = bool(recheck_ids)
                self.TODO_ITEMS = self._build_todo_items(recheck_ids=recheck_ids or None)
        else:
            self.TODO_ITEMS = self._build_todo_items()

        if self._recheck_mode:
            user_prompt = (
                f"**复审轮** chapter {chapter_index}: **{title}** (`{chapter_id}`)\n"
                f"上一轮 {len(self._passed_frozen)} 项已通过，**本轮只复审** "
                f"{len(self.TODO_ITEMS) - 1} 项打叉修复结果。\n"
                "1. `review_chapter_bundle()` → `todolist_check(REVIEW_BUNDLE)` "
                "(**ITEM_ID only**; skip re-read if bundle unchanged)\n"
                "2. 仅对本轮 [复审] 项 `todolist_check(ITEM_ID, result=pass|fail)`\n"
                "3. `done()` when 本轮 todo 全部核查完"
            )
        else:
            user_prompt = (
                f"Review chapter {chapter_index}: **{title}**\n"
                f"**Chapter folder id: `{chapter_id}`** — use this for all tools. "
                f"Do NOT use `chapter_1`.\n"
                "Call `todolist_status()` → `review_chapter_bundle()` → `todolist_check(REVIEW_BUNDLE)`.\n"
                "Use **ITEM_ID** only (REVIEW_BUNDLE, VISUAL_DEMOS, …) — not Chinese labels.\n"
                "Auto ✅ items are pre-marked — only `todolist_check` **manual** items (+ fail auto/precheck if disagree).\n"
                "Optional: `craft_auto_check()` for machine hints.\n"
                "Per manual item: `todolist_check(ITEM, result=\"pass\")` if OK;\n"
                "  `todolist_check(ITEM, result=\"fail\", reason=\"问题\", fix=\"修复方案\")` if not.\n"
                "done() when ALL items reviewed. All pass → verify; any fail → repair."
            )
        if repair_feedback:
            user_prompt += f"\n\n## Repair 后上下文\n{repair_feedback[:4000]}"

        return _run_loop(
            tools=self._tools,
            system_prompt=REVIEW_AGENT_SYSTEM,
            user_prompt=user_prompt,
            max_iterations=settings.web_build_agent_max_iterations,
            state=self._state,
            ctx=self._ctx,
            chapter_id=chapter_id,
            agent_role="reviewer",
        )
