"""Declarative agent tool specs — schema + handler binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.workflow.step_indexing import write_narrations_tool_description


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: str


ALL_TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="workspace_info",
        description=(
            "Get workspace paths. Call this FIRST to understand directory layout and where to write files."
        ),
        input_schema={"type": "object", "properties": {}},
        handler="workspace_info",
    ),
    ToolSpec(
        name="read_file",
        description="Read file(s) with optional line range. Paths relative to workspace root.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                },
                "offset": {"type": "integer", "description": "Start line (1-based)", "default": 1},
                "limit": {"type": "integer", "description": "Max lines to read"},
            },
            "required": ["path"],
        },
        handler="read_file",
    ),
    ToolSpec(
        name="read_chapter_context",
        description=(
            "Read THIS chapter's Tier-A build context: article excerpts, script beats, "
            "01-example excerpt, motion summary (MOTION-SYSTEM + mot-* excerpt). "
            "**Call once at build start before write_narrations/write_file.** "
            "Use read_motion_detail / read_layout_catalog only if you need the full catalogs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {
                    "type": "string",
                    "description": "Chapter folder id (defaults to current chapter)",
                },
            },
        },
        handler="read_chapter_context",
    ),
    ToolSpec(
        name="read_motion_detail",
        description=(
            "Full MOTION-SYSTEM.md + presets.css + animations.css — optional after read_chapter_context "
            "when you need custom/complex motion beyond the summary."
        ),
        input_schema={"type": "object", "properties": {}},
        handler="read_motion_detail",
    ),
    ToolSpec(
        name="read_layout_catalog",
        description=(
            "Full LAYOUT-SYSTEM.md shell catalog — optional after read_chapter_context "
            "when picking an uncommon shell layout."
        ),
        input_schema={"type": "object", "properties": {}},
        handler="read_layout_catalog",
    ),
    ToolSpec(
        name="read_source_docs",
        description=(
            "Read script.md and outline.md in one call. "
            "Use to cross-check chapter content against the source plan."
        ),
        input_schema={"type": "object", "properties": {}},
        handler="read_source_docs",
    ),
    ToolSpec(
        name="review_chapter_bundle",
        description=(
            "Read all files for one chapter (narrations.ts, index.tsx, index.css) "
            "plus registry files. Initializes CHAPTER-CRAFT checklist (pending). "
            "Use craft_auto_check separately for programmatic hints. "
            "Omit chapter_id to use the current chapter folder (e.g. hook, coldopen) — "
            "never pass chapter_1 unless that is the real folder name."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {
                    "type": "string",
                    "description": "Chapter folder id from outline (e.g. hook). Defaults to current chapter.",
                },
            },
        },
        handler="review_chapter_bundle",
    ),
    ToolSpec(
        name="report_missing_assets",
        description=(
            "Record missing assets for this chapter into workflow state. "
            "Call before todolist_check(MISSING_ASSETS_NOTE). "
            "Use items=[] if nothing is missing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "string", "description": "Chapter id (defaults to current chapter)"},
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Missing asset descriptions; empty = none missing",
                },
                "note": {"type": "string", "description": "Optional extra note for the user"},
            },
        },
        handler="report_missing_assets",
    ),
    ToolSpec(
        name="craft_review_status",
        description="Show CHAPTER-CRAFT 完工自检 checklist progress (20 items from Part 完工自检).",
        input_schema={"type": "object", "properties": {}},
        handler="craft_review_status",
    ),
    ToolSpec(
        name="craft_auto_check",
        description=(
            "Run programmatic CHAPTER-CRAFT auto checks (emoji, tokens, narrations sync, etc.). "
            "Builder: call after writing index.tsx+css — if NO_AI_SLOP reports emoji, "
            "replace with inline SVG/CSS before update_registry. "
            "Results are advisory only — they do NOT block todolist_check. "
            "Call after review_chapter_bundle when you want machine hints before manual attestation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {
                    "type": "string",
                    "description": "Chapter folder id (defaults to current chapter)",
                },
            },
        },
        handler="craft_auto_check",
    ),
    ToolSpec(
        name="edit_file",
        description=(
            "Replace exact text in an existing file. Use for fixes after typecheck/vite errors. "
            "old_string must match exactly once. Prefer over write_file for small fixes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        handler="edit_file",
    ),
    ToolSpec(
        name="write_narrations",
        description=write_narrations_tool_description(),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "string", "description": "e.g. chapter_1"},
                "lines": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Narration text per step",
                },
            },
            "required": ["chapter_id", "lines"],
        },
        handler="write_narrations",
    ),
    ToolSpec(
        name="write_file",
        description=(
            "Write content to a file. Creates parent directories if needed. "
            "Icons: use inline SVG or CSS — never emoji (NO_AI_SLOP hard-fail)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["path", "content"],
        },
        handler="write_file",
    ),
    ToolSpec(
        name="run_shell",
        description=(
            "Run a shell command. cwd is the presentation/ directory — "
            "use src/chapters/..., NOT presentation/src/chapters/..."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command"},
            },
            "required": ["command"],
        },
        handler="run_shell",
    ),
    ToolSpec(
        name="typecheck",
        description="Run npx tsc --noEmit in the presentation directory.",
        input_schema={"type": "object", "properties": {}},
        handler="typecheck",
    ),
    ToolSpec(
        name="check_vite",
        description=(
            "Run npx vite build to verify ALL files compile. "
            "Catches syntax errors, import issues, and JSX escaping problems that tsc might miss."
        ),
        input_schema={"type": "object", "properties": {}},
        handler="check_vite",
    ),
    ToolSpec(
        name="read_reference",
        description="Read a reference document.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Reference name like CHAPTER-CRAFT.md"},
            },
            "required": ["name"],
        },
        handler="read_reference",
    ),
    ToolSpec(
        name="list_files",
        description="List files in the workspace matching a glob pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern", "default": "*"},
            },
        },
        handler="list_files",
    ),
    ToolSpec(
        name="todolist_status",
        description="Show current todo list progress. Call this at the start to see what remains.",
        input_schema={"type": "object", "properties": {}},
        handler="todolist_status",
    ),
    ToolSpec(
        name="todolist_check",
        description=(
            "Mark todo item(s) as reviewed. "
            "Reviewer pass: result=\"pass\" when item meets CHAPTER-CRAFT. "
            "Reviewer fail: result=\"fail\" with reason (what is wrong) AND fix (concrete repair plan). "
            "After any fail, call done() — Repair runs automatically. "
            "Never mark pass to unblock done() when the item should fail. "
            "Builder/verify: omit result."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "item": {
                    "oneOf": [
                        {"type": "string", "description": "Single item name"},
                        {"type": "array", "items": {"type": "string"}, "description": "Multiple item names"},
                    ],
                    "description": "Item name(s) to mark as reviewed",
                },
                "result": {
                    "type": "string",
                    "enum": ["pass", "fail"],
                    "description": "Reviewer: pass ✅ or fail ❌ after manual verification",
                    "default": "pass",
                },
                "reason": {
                    "type": "string",
                    "description": "Required when result=fail — problem description + file/step",
                },
                "fix": {
                    "type": "string",
                    "description": "Required when result=fail — concrete repair plan (file, class, old→new)",
                },
            },
            "required": ["item"],
        },
        handler="todolist_check",
    ),
    ToolSpec(
        name="update_registry",
        description=(
            "Register a chapter in chapters.ts so typecheck sees it. "
            "ONLY call AFTER writing both index.tsx and narrations.ts — it will refuse if files are missing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "string", "description": "e.g. chapter_1"},
                "title": {"type": "string", "description": "Chapter title"},
            },
            "required": ["chapter_id", "title"],
        },
        handler="update_registry",
    ),
    ToolSpec(
        name="done",
        description="Call this when ALL tasks are complete after review, typecheck, and check_vite.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "What was built and verification results"},
            },
            "required": ["summary"],
        },
        handler="done",
    ),
)

TOOL_SPECS_BY_NAME = {spec.name: spec for spec in ALL_TOOL_SPECS}
