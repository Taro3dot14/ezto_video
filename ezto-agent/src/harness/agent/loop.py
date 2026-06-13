"""Autonomous agent loop — self-driving tool-use engine."""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from typing import Any

from backend.core import llm
from backend.core.logger import logger
from configs import settings

from .tool_registry import AgentTool, make_build_agent_tools
from .system_prompts import BUILD_CHAPTER_SYSTEM
from .parser import extract_all


@dataclass
class AgentResult:
    content: str
    tool_calls: int = 0
    iterations: int = 0
    success: bool = True
    files_created: list[str] = field(default_factory=list)


def run_agent_custom(
    *,
    tools: list[AgentTool],
    system_prompt: str,
    user_prompt: str,
    state: Any = None,
    max_iterations: int = 25,
) -> AgentResult:
    return _run_loop(
        tools=tools, system_prompt=system_prompt, user_prompt=user_prompt,
        max_iterations=max_iterations, state=state,
    )


def _run_loop(
    *,
    tools: list[AgentTool],
    system_prompt: str,
    user_prompt: str,
    max_iterations: int,
    state: Any = None,
) -> AgentResult:
    tool_manifest = "\n\n".join(t.to_prompt_block() for t in tools)
    full_system = f"{system_prompt.strip()}\n\n## Available Tools\n\n{tool_manifest}"

    messages: list[dict[str, str]] = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_prompt},
    ]

    tool_calls = 0
    last_content = ""

    def _push(tp: str, msg: str) -> None:
        if state is not None and isinstance(state, dict):
            tl = state.setdefault("thinking_log", [])
            tl.append({"type": tp, "content": msg, "ts": _time.time()})

    for iteration in range(max_iterations):
        logger.debug("Agent[%d/%d] tool_calls=%d", iteration + 1, max_iterations, tool_calls)
        _push("step", f"🤔 Agent 思考中…（第 {iteration + 1} 轮）")

        response = llm.chat(messages=messages, temperature=0.0)
        last_content = response

        # ── 记录 LLM 思考过程 ──
        think_text = response.split("```tool")[0].strip() if "```tool" in response else response.strip()[:300]
        if think_text:
            logger.info("🧠 Agent: %s", think_text[:200])
            _push("llm", think_text[:500])

        # ── 解析工具调用（支持批量） ──
        parsed_list = extract_all(response)

        if not parsed_list:
            logger.warning("Agent: no tool call in response")
            _push("step", "⚠️ 调工具继续，或调 done() 结束")
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "Call a tool to continue, or call done(summary=...) if task is complete.",
            })
            continue

        # ── 执行本轮全部工具 ──
        batch_outputs: list[str] = []

        for tool_name, arguments in parsed_list:
            if tool_name == "done":
                summary = arguments.get("summary", "Task completed")
                logger.info("Agent done: %s", summary[:200])
                return AgentResult(content=summary, tool_calls=tool_calls, iterations=iteration + 1, success=True)

            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                logger.warning("Agent: unknown tool '%s'", tool_name)
                batch_outputs.append(f"Tool '{tool_name}' unknown. Available: {', '.join(t.name for t in tools)}")
                continue

            try:
                result = tool.fn(**arguments)
                output = str(result)[:8000]
                logger.info("Agent tool: %s(%s) → %d chars", tool_name, arguments, len(output))
                _push("step", f"⚡ {tool_name} → {len(output)} chars")
            except Exception as e:
                output = f"Error: {e}"
                logger.warning("Agent tool %s failed: %s", tool_name, e)
                _push("llm", f"⚠️ {tool_name} 失败: {e}")

            tool_calls += 1
            batch_outputs.append(f"[{tool_name}]:\n```\n{output}\n```")

        # ── 汇总回传 ──
        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user",
            "content": (
                f"{len(parsed_list)} tool(s) executed:\n\n"
                + "\n".join(batch_outputs)
                + "\n\nContinue. Update todo_list and call more tools or done()."
            ),
        })

    logger.warning("Agent reached max iterations (%d) without calling done()", max_iterations)
    return AgentResult(content=last_content, tool_calls=tool_calls, iterations=max_iterations, success=False)


class WebBuildAgent:
    TODO_ITEMS: dict[str, str] = {
        "CHAPTER_CRAFT": "Read CHAPTER-CRAFT.md reference",
        "SCRIPT_OUTLINE": "Read script.md and outline.md",
        "EXAMPLE_CHAPTER": "Read 01-example chapter for style",
        "INDEX_TSX": "Write index.tsx component",
        "NARRATIONS_TS": "Write narrations.ts",
        "REGISTRY": "Call update_registry",
        "TYPECHECK": "Run npx tsc --noEmit and fix until pass",
        "VITE_CHECK": "Call check_vite to verify Vite compilation",
    }

    def __init__(self, state: Any):
        self._state = state
        self._todo_done: set[str] = set()

        def mark(item: str | list[str]) -> str:
            items = [item] if isinstance(item, str) else item
            results = []
            for raw in items:
                i = raw.upper().strip()
                if i not in self.TODO_ITEMS:
                    results.append(f"\u274c Unknown: {raw}. Valid: {', '.join(self.TODO_ITEMS)}")
                    continue
                if i in self._todo_done:
                    results.append(f"\u2139\ufe0f {i} already done")
                    continue
                self._todo_done.add(i)
                results.append(f"\u2705 {i}: {self.TODO_ITEMS[i]}")
            status = self._todo_status()
            logger.info("\u2705 TODO batch(%d) -> %s", len(items), status)
            if isinstance(state, dict):
                tl = state.setdefault("thinking_log", [])
                import time
                tl.append({"type": "step", "content": "\n".join(results) + f"\n{status}", "ts": time.time()})
            return "\n".join(results) + "\n" + status

        def status() -> str:
            return self._todo_status()

        def verify(summary: str) -> str:
            r = [i for i in self.TODO_ITEMS if i not in self._todo_done]
            if r:
                return f"\u274c Cannot call done() - remaining: {', '.join(r)}"
            return f"[DONE] {summary}"

        self._tools = make_build_agent_tools(
            state,
            get_todo_status=status,
            mark_todo_done=mark,
            verify_all_done=verify,
        )

    def _todo_status(self) -> str:
        total = len(self.TODO_ITEMS)
        done = len(self._todo_done)
        lines = [f"\u2705 [{done}/{total}]"]
        for k, v in self.TODO_ITEMS.items():
            mark = "\u2705" if k in self._todo_done else "\u2610"
            lines.append(f"  {mark} {v}")
        return "\n".join(lines)

    def run(
        self,
        *,
        chapter_id: str,
        title: str,
        chapter_index: int = 1,
        total_chapters: int = 1,
        previous_chapters: str = "",
    ) -> AgentResult:
        user_prompt = (
            f"Build chapter {chapter_index}/{total_chapters}: **{title}**\n"
            f"Chapter id: {chapter_id}\n\n"
            f"Script.md and outline.md are in the workspace root. "
            f"Read them first, then write the chapter files. "
            f"Call todolist_status() first to see your task list, then "
            f"call todolist_check(ITEM) after each step. "
            f"When ALL items are checked, call done(summary=...)."
        )
        if previous_chapters:
            user_prompt += f"\n\nPrevious chapters for style reference:\n{previous_chapters[:3000]}"

        return _run_loop(
            tools=self._tools,
            system_prompt=BUILD_CHAPTER_SYSTEM,
            user_prompt=user_prompt,
            max_iterations=settings.web_build_agent_max_iterations,
            state=self._state,
        )
