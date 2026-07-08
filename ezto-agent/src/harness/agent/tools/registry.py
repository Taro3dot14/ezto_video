"""Agent tool definitions — wire declarative specs to chapter runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.core.state import VideoWorkflowState

from .definitions import ALL_TOOL_SPECS
from .profiles import filter_tools_by_profile
from .runtime import ChapterToolRuntime
from .session import ChapterSessionState


@dataclass
class AgentTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Any

    def to_prompt_block(self) -> str:
        return (
            f"## {self.name}\n"
            f"{self.description}\n"
            f"```json\n{json.dumps(self.input_schema, indent=2, ensure_ascii=False)}\n```"
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def _build_tools(runtime: ChapterToolRuntime) -> list[AgentTool]:
    return [
        AgentTool(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema,
            fn=getattr(runtime, spec.handler),
        )
        for spec in ALL_TOOL_SPECS
    ]


def make_build_agent_tools(
    state: VideoWorkflowState,
    *,
    chapter_id: str = "chapter_1",
    chapter_title: str = "",
    chapter_index: int = 1,
    tool_profile: str = "builder",
    preset_review_ok: bool = False,
    get_todo_status: Any = None,
    mark_todo_done: Any = None,
    verify_all_done: Any = None,
) -> tuple[list[AgentTool], ChapterSessionState]:
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / "presentation"
    session = ChapterSessionState.for_chapter(
        chapter_id=chapter_id,
        chapter_index=chapter_index,
        tool_profile=tool_profile,
        workflow_state=state,
        preset_review_ok=preset_review_ok,
    )
    runtime = ChapterToolRuntime(
        state,
        session,
        ws=ws,
        ppt=ppt,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        mark_todo_done=mark_todo_done,
        verify_all_done=verify_all_done,
        get_todo_status=get_todo_status,
    )
    tools = filter_tools_by_profile(_build_tools(runtime), tool_profile)
    return tools, session
