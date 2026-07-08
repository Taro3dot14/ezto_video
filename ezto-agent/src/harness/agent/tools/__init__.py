"""LLM agent tool layer for chapter build / review / verify.

Distinct from ``harness.services.tools`` (low-level file/shell adapters).
"""

from __future__ import annotations

from .audit import push_tool_audit
from .definitions import ALL_TOOL_SPECS, TOOL_SPECS_BY_NAME, ToolSpec
from .executor import execute_tool, format_result_for_llm
from .guards import check_tool_guard
from .legacy_parser import extract_all, has_tool_call, try_extract
from .observations import shape_tool_output
from .profiles import ALL_TOOL_NAMES, PROFILE_ALLOW, filter_tools_by_profile
from .registry import AgentTool, make_build_agent_tools
from .result import ToolErrorCode, ToolExecutionRecord, ToolResult
from .runtime import ChapterToolRuntime
from .session import ChapterSessionState

__all__ = [
    "ALL_TOOL_NAMES",
    "ALL_TOOL_SPECS",
    "AgentTool",
    "ChapterSessionState",
    "ChapterToolRuntime",
    "PROFILE_ALLOW",
    "TOOL_SPECS_BY_NAME",
    "ToolErrorCode",
    "ToolExecutionRecord",
    "ToolResult",
    "ToolSpec",
    "check_tool_guard",
    "execute_tool",
    "extract_all",
    "filter_tools_by_profile",
    "format_result_for_llm",
    "has_tool_call",
    "make_build_agent_tools",
    "push_tool_audit",
    "shape_tool_output",
    "try_extract",
]
