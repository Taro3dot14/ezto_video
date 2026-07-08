"""Unified tool execution — parse, invoke, shape, audit."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from backend.core.logger import logger

from harness.services.tools.chapter.narration_args import resolve_tool_arguments
from .observations import shape_tool_output
from .registry import AgentTool
from .result import ToolErrorCode, ToolExecutionRecord, ToolResult
from .session import ChapterSessionState


def _summarize_args(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        k: (f"<{len(v)} chars>" if k in ("content", "lines", "old_string", "new_string")
            and isinstance(v, (str, list)) else v)
        for k, v in arguments.items()
    }


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    tools: list[AgentTool],
    *,
    ppt: Path | None = None,
    chapter_id: str = "chapter_1",
    post_validate: Any = None,
    session: ChapterSessionState | None = None,
) -> tuple[ToolResult, ToolExecutionRecord]:
    """Run one tool call; return structured result + audit record."""
    t0 = time.perf_counter()
    args_summary = _summarize_args(arguments)

    resolved = resolve_tool_arguments(tool_name, arguments)
    if "_raw" in resolved:
        raw = str(resolved.get("_raw", ""))[:200]
        result = ToolResult.parse_error(
            f"Could not extract {tool_name} arguments. "
            f"Retry with valid JSON (escape quotes in strings). Fragment: {raw}…"
        )
        return result, _record(tool_name, result, t0, args_summary)

    tool = next((t for t in tools if t.name == tool_name), None)
    if tool is None:
        result = ToolResult.not_found(f"Tool '{tool_name}' is not available in this agent profile.")
        return result, _record(tool_name, result, t0, args_summary)

    try:
        raw_output = tool.fn(**resolved)
        if isinstance(raw_output, ToolResult):
            result = raw_output
        else:
            result = ToolResult.from_handler_output(str(raw_output), tool_name=tool_name)
    except Exception as e:
        logger.warning("Agent tool %s failed: %s", tool_name, e)
        result = ToolResult.exec_error(str(e))
        return result, _record(tool_name, result, t0, args_summary)

    if result.ok and not result.done and not result.failed and post_validate is not None and ppt is not None:
        extra = post_validate(tool_name, resolved, result.message, ppt=ppt, chapter_id=chapter_id)
        if extra:
            result = ToolResult.success(result.message + "\n\n" + extra)

    if session is not None:
        session.apply_tool_outcome(result, tool_name, resolved)

    return result, _record(tool_name, result, t0, args_summary)


def format_result_for_llm(tool_name: str, result: ToolResult) -> str:
    """Apply observation shaping on tool output for the LLM channel."""
    if result.done:
        return result.message
    return shape_tool_output(tool_name, result.for_llm())


def _record(
    tool_name: str,
    result: ToolResult,
    t0: float,
    args_summary: dict[str, Any],
) -> ToolExecutionRecord:
    shaped_len = len(result.for_llm())
    duration_ms = (time.perf_counter() - t0) * 1000
    rec = ToolExecutionRecord(
        tool_name=tool_name,
        code=result.code,
        duration_ms=round(duration_ms, 2),
        output_chars=shaped_len,
        blocked=result.code == ToolErrorCode.BLOCKED,
        done=result.done,
        args_summary=args_summary,
    )
    logger.info(
        "Agent tool: %s(%s) → %s %d chars %.1fms",
        tool_name, args_summary, result.code.value, shaped_len, duration_ms,
    )
    return rec
