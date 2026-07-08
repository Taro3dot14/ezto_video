"""Tool profile allowlists — single source for native + legacy parser."""

from __future__ import annotations

from harness.agent.tools.definitions import ALL_TOOL_SPECS

PROFILE_ALLOW: dict[str, frozenset[str] | None] = {
    "builder": frozenset({
        "workspace_info", "read_chapter_context", "read_motion_detail", "read_layout_catalog",
        "read_reference",
        "write_narrations", "write_file", "edit_file", "craft_auto_check",
        "update_registry",
        "todolist_status", "todolist_check", "done",
    }),
    "reviewer": frozenset({
        "workspace_info", "read_file", "read_source_docs", "read_reference", "list_files",
        "review_chapter_bundle", "craft_auto_check", "craft_review_status", "report_missing_assets",
        "todolist_status", "todolist_check", "done",
    }),
    "verify": frozenset({
        "read_file", "edit_file", "typecheck", "check_vite",
        "todolist_status", "todolist_check", "done",
    }),
    "repair": frozenset({
        "read_chapter_context", "read_file", "edit_file", "report_missing_assets",
        "craft_auto_check", "craft_review_status",
        "write_narrations", "write_file",
        "todolist_status", "todolist_check", "done",
    }),
}

# All registered tool names (union of profiles + legacy/deprecated names).
ALL_TOOL_NAMES: frozenset[str] = frozenset(spec.name for spec in ALL_TOOL_SPECS) | frozenset({
    "run_shell",
    "craft_review_check",
})


def filter_tools_by_profile(tools: list, profile: str) -> list:
    allowed = PROFILE_ALLOW.get(profile)
    if allowed is None:
        return tools
    return [t for t in tools if t.name in allowed]
