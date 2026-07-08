"""Structured tool execution results for the agent loop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolErrorCode(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    PARSE = "parse"
    NOT_FOUND = "not_found"
    EXEC = "exec"


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool invocation."""

    code: ToolErrorCode
    message: str
    done: bool = False

    @property
    def ok(self) -> bool:
        return self.code == ToolErrorCode.OK

    @property
    def failed(self) -> bool:
        """Handler returned OK but message indicates user-visible failure."""
        return self.code == ToolErrorCode.OK and self.message.startswith("❌")

    def for_llm(self) -> str:
        """Format for the LLM tool channel — distinct tone per error class."""
        if self.code == ToolErrorCode.BLOCKED:
            return (
                "❌ POLICY BLOCKED — fix the issue below before retrying the same call:\n"
                f"{self.message}"
            )
        if self.code == ToolErrorCode.PARSE:
            return f"❌ ARGUMENT PARSE ERROR:\n{self.message}"
        if self.code == ToolErrorCode.NOT_FOUND:
            return f"❌ UNKNOWN TOOL:\n{self.message}"
        if self.code == ToolErrorCode.EXEC:
            return f"❌ EXECUTION ERROR:\n{self.message}"
        return self.message

    @classmethod
    def success(cls, message: str) -> ToolResult:
        return cls(ToolErrorCode.OK, message)

    @classmethod
    def blocked(cls, message: str) -> ToolResult:
        return cls(ToolErrorCode.BLOCKED, message)

    @classmethod
    def parse_error(cls, message: str) -> ToolResult:
        return cls(ToolErrorCode.PARSE, message)

    @classmethod
    def not_found(cls, message: str) -> ToolResult:
        return cls(ToolErrorCode.NOT_FOUND, message)

    @classmethod
    def exec_error(cls, message: str) -> ToolResult:
        return cls(ToolErrorCode.EXEC, message)

    @classmethod
    def done_summary(cls, summary: str) -> ToolResult:
        return cls(ToolErrorCode.OK, summary, done=True)

    @classmethod
    def from_handler_output(cls, output: str, *, tool_name: str) -> ToolResult:
        """Wrap legacy str-returning handlers."""
        if tool_name == "done":
            if output.startswith("[DONE]"):
                return cls.done_summary(output.removeprefix("[DONE] ").strip())
            if output.startswith("❌") or output.lower().startswith("cannot"):
                return cls(ToolErrorCode.OK, output, done=False)
            return cls(ToolErrorCode.OK, output, done=False)
        if output.startswith("❌ BLOCKED:"):
            return cls.blocked(output.removeprefix("❌ BLOCKED:").strip())
        if output.startswith("❌"):
            return cls(ToolErrorCode.OK, output)
        return cls.success(output)


@dataclass
class ToolExecutionRecord:
    """Structured audit entry for one tool call."""

    tool_name: str
    code: ToolErrorCode
    duration_ms: float
    output_chars: int
    blocked: bool
    done: bool
    args_summary: dict[str, Any]
