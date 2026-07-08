"""Shape tool outputs before feeding back into the agent context."""

from __future__ import annotations

import re

from configs import settings


def _shape_read_output(output: str) -> str:
    """Truncate long read_* tool results using limits from settings."""
    max_lines = settings.agent_read_max_lines
    if max_lines <= 0:
        return output

    lines = output.splitlines()
    if len(lines) <= max_lines:
        return output

    head_n = max(0, settings.agent_read_head_lines)
    tail_n = max(0, settings.agent_read_tail_lines)
    if head_n + tail_n >= len(lines):
        return output

    head = "\n".join(lines[:head_n])
    tail = "\n".join(lines[-tail_n:]) if tail_n else ""
    omitted = len(lines) - head_n - tail_n
    if tail:
        return f"{head}\n... [{omitted} lines omitted] ...\n{tail}"
    return f"{head}\n... [{omitted} lines omitted] ..."


def shape_tool_output(tool_name: str, output: str, *, success: bool = True) -> str:
    """Compress verbose tool results to save tokens."""
    if tool_name in ("write_file", "write_narrations", "edit_file"):
        return output[:500]

    if tool_name in ("read_file", "read_source_docs", "read_chapter_context", "review_chapter_bundle"):
        return _shape_read_output(output)

    if tool_name == "run_shell":
        return _shape_shell(output)

    if tool_name in ("typecheck", "check_vite"):
        return _shape_errors(output)

    if tool_name in ("todolist_status", "todolist_check", "workspace_info", "done",
                     "craft_review_status", "craft_auto_check"):
        return output[:1200]

    return output[:3000]


def _shape_shell(output: str) -> str:
    lines = output.splitlines()
    if len(lines) <= 50:
        return output[:3000]
    head = "\n".join(lines[:20])
    tail = "\n".join(lines[-15:])
    return f"{head}\n... [{len(lines) - 35} lines omitted] ...\n{tail}"


def _shape_errors(output: str) -> str:
    if "✅" in output[:20]:
        return output[:300]
    lines = [l for l in output.splitlines() if l.strip()]
    err_lines = [
        l for l in lines
        if re.search(r"error|failed|✗|❌", l, re.I) and "warning" not in l.lower()
    ]
    if not err_lines:
        err_lines = lines[-15:]
    body = "\n".join(err_lines[:12])
    if len(lines) > 15:
        body += f"\n... [{len(lines) - 12} more lines]"
    return body[:2500]
