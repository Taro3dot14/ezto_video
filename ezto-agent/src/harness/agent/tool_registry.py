"""Agent tool definitions — thin adapters over services/tools and workflow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.core.state import VideoWorkflowState
from harness.services.tools.chapter_bundle import review_chapter_bundle as svc_review_chapter_bundle
from harness.services.tools.craft_review import (
    CRAFT_TODO_IDS,
    REVIEWER_ONLY_TODO_IDS,
    REVIEW_BUNDLE_TODO,
    craft_auto_check as svc_craft_auto_check,
    format_craft_checklist,
    on_typecheck_pass,
    push_craft_checklist_event,
    reviewer_todo_items,
    try_check_craft_todo_item,
)
from harness.services.tools.file_ops import (
    edit_file as svc_edit_file,
    list_files as svc_list_files,
    read_files as svc_read_files,
    write_file as svc_write_file,
)
from harness.services.tools.missing_assets import report_missing_assets as svc_report_missing_assets
from harness.services.tools.narrations import write_narrations as svc_write_narrations
from harness.workflow.step_indexing import write_narrations_tool_description
from harness.services.tools.chapter_context import read_chapter_context as svc_read_chapter_context
from harness.services.tools.source_docs import read_source_docs as svc_read_source_docs
from harness.services.tools.shell import normalize_presentation_command, run_shell as svc_run_shell
from harness.services.tools.typescript import run_typecheck as svc_run_typecheck
from harness.services.tools.vite import check_vite as svc_check_vite
from harness.workflow.artifacts import sync_built_chapter_registry
from harness.workflow.chapter_ids import resolve_chapter_id
from harness.workflow.chapter_policies import check_tool_guard
from harness.workflow.guards import require_ref_loaded


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


def _resolve_path(ws: Path, path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ws / path


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
) -> tuple[list[AgentTool], dict[str, Any]]:
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / "presentation"
    ctx: dict[str, Any] = {
        "chapter_id": chapter_id,
        "chapter_index": chapter_index,
        "tool_profile": tool_profile,
        "workflow_state": state,
        "review_ok": preset_review_ok,
        "typecheck_ok": False,
        "vite_ok": False,
    }

    def _guard(tool_name: str, arguments: dict[str, Any]) -> str | None:
        return check_tool_guard(
            tool_name, arguments, ppt=ppt, chapter_id=chapter_id, ctx=ctx,
        )

    def _read_file(
        path: str | list[str],
        offset: int = 1,
        limit: int | None = None,
    ) -> str:
        if isinstance(path, str):
            paths = [str(_resolve_path(ws, path))]
        else:
            paths = [str(_resolve_path(ws, p)) for p in path]
        return svc_read_files(state, paths, offset=offset, limit=limit)

    def _read_source_docs() -> str:
        return svc_read_source_docs(state, workspace_root=ws)

    def _read_chapter_context(chapter_id: str | None = None) -> str:
        cid = (chapter_id or ctx["chapter_id"]).strip()
        return svc_read_chapter_context(
            state,
            workspace_root=ws,
            chapter_id=cid,
            chapter_index=ctx.get("chapter_index", 1),
            chapter_title=chapter_title,
        )

    def _review_chapter_bundle(chapter_id: str | None = None) -> str:
        cid = (chapter_id or ctx["chapter_id"]).strip()
        blocked = _guard("review_chapter_bundle", {"chapter_id": cid})
        if blocked:
            return blocked
        content, ok = svc_review_chapter_bundle(
            state, workspace_root=ws, chapter_id=cid, ctx=ctx,
        )
        ctx["review_ok"] = ok
        push_craft_checklist_event(state, ctx)
        return content

    def _craft_review_status() -> str:
        return format_craft_checklist(ctx)

    def _craft_auto_check(chapter_id: str | None = None) -> str:
        cid = (chapter_id or ctx["chapter_id"]).strip()
        blocked = _guard("craft_auto_check", {"chapter_id": cid})
        if blocked:
            return blocked
        content = svc_craft_auto_check(
            ctx, workspace_root=ws, chapter_id=cid,
        )
        push_craft_checklist_event(state, ctx)
        return content

    def _write_file(path: str, content: str) -> str:
        blocked = _guard("write_file", {"path": path})
        if blocked:
            return blocked
        full = _resolve_path(ws, path)
        svc_write_file(state, str(full), content)
        shell_path = path.removeprefix("presentation/") if path.startswith("presentation/") else path
        return (
            f"Written {len(content)} chars to {path}\n"
            f"Absolute: {full}\n"
            f"run_shell equivalent: {shell_path} (cwd=presentation/)"
        )

    def _edit_file(path: str, old_string: str, new_string: str) -> str:
        blocked = _guard("edit_file", {"path": path})
        if blocked:
            return blocked
        return svc_edit_file(state, str(_resolve_path(ws, path)), old_string, new_string)

    def _run_shell(command: str) -> str:
        try:
            command, hint = normalize_presentation_command(command)
        except re.error as e:
            return f"❌ Invalid shell command normalization: {e}\nUse paths without presentation/ prefix (cwd is presentation/)."
        result = svc_run_shell(state, command, cwd=str(ppt))
        out = [f"cwd: {ppt}"]
        if hint:
            out.append(hint)
        if result.stdout:
            out.append(result.stdout[:5000])
        if result.stderr:
            out.append(f"STDERR:\n{result.stderr[:2000]}")
        out.append(f"→ exit code {result.returncode}")
        return "\n".join(out)

    def _write_narrations(chapter_id: str, lines: list[str]) -> str:
        if not lines:
            return "❌ lines must be a non-empty array of narration strings"
        try:
            msg = svc_write_narrations(
                state, workspace_root=ws, chapter_id=chapter_id, lines=lines,
            )
        except ValueError as e:
            return f"❌ {e}"
        rel = f"presentation/src/chapters/{chapter_id}/narrations.ts"
        shell_path = f"src/chapters/{chapter_id}/narrations.ts"
        return (
            f"{msg}\n"
            f"run_shell equivalent: {shell_path} (cwd=presentation/)"
        )

    def _typecheck() -> str:
        blocked = _guard("typecheck", {})
        if blocked:
            return blocked
        result = svc_run_typecheck(state, cwd=str(ppt))
        if result.returncode == 0:
            ctx["typecheck_ok"] = True
            on_typecheck_pass(ctx)
            push_craft_checklist_event(state, ctx)
            return "✅ TypeScript type check passed"
        ctx["typecheck_ok"] = False
        return f"❌ TypeScript errors:\n{result.stdout[:5000]}"

    def _read_ref(name: str) -> str:
        return require_ref_loaded(state, name)

    def _list_files(pattern: str = "*") -> str:
        return svc_list_files(ws, pattern)

    def _update_registry(chapter_id: str, title: str) -> str:
        blocked = _guard("update_registry", {"chapter_id": chapter_id})
        if blocked:
            return blocked
        tsx = ppt / "src" / "chapters" / chapter_id / "index.tsx"
        nar = ppt / "src" / "chapters" / chapter_id / "narrations.ts"
        missing = []
        if not tsx.exists():
            missing.append("index.tsx")
        if not nar.exists():
            missing.append("narrations.ts")
        if missing:
            return f"❌ Cannot update registry — missing: {', '.join(missing)}. Write files first."
        return sync_built_chapter_registry(state, chapter_id, title)

    def _check_vite() -> str:
        blocked = _guard("check_vite", {})
        if blocked:
            return blocked
        result = svc_check_vite(state, cwd=ppt)
        ctx["vite_ok"] = result.success
        return result.message

    def _report_missing_assets(
        chapter_id: str | None = None,
        items: list[str] | None = None,
        note: str = "",
    ) -> str:
        raw = (chapter_id or ctx["chapter_id"]).strip()
        cid, warn = resolve_chapter_id(state, raw, default=ctx["chapter_id"])
        body = svc_report_missing_assets(
            state, chapter_id=cid, items=items, note=note,
        )
        return f"{warn}\n{body}" if warn else body

    def _todolist_check(
        item: str | list[str],
        result: str = "pass",
        reason: str = "",
        fix: str = "",
    ) -> str:
        blocked = _guard("todolist_check", {
            "item": item, "result": result, "reason": reason, "fix": fix,
        })
        if blocked:
            return blocked
        if mark_todo_done:
            return mark_todo_done(item, result=result, reason=reason, fix=fix)
        return f"todolist: {item}"

    tools = [
        AgentTool(
            name="workspace_info",
            description="Get workspace paths. Call this FIRST to understand directory layout and where to write files.",
            input_schema={"type": "object", "properties": {}},
            fn=lambda: (
                "Workspace root: " + str(ws) + "\n"
                "Presentation dir: " + str(ppt) + "\n"
                "write_file/read_file paths: presentation/src/chapters/<chapter_id>/index.tsx\n"
                "run_shell paths (cwd=presentation/): src/chapters/<chapter_id>/index.tsx\n"
                "Coding pattern: call read_chapter_context (NOT read_file on 01-example)\n"
                "Registry: presentation/src/registry/chapters.ts"
            ),
        ),
        AgentTool(
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
            fn=_read_file,
        ),
        AgentTool(
            name="read_chapter_context",
            description=(
                "Read THIS chapter's build context in one call: article excerpts "
                "(parsed from outline 信息池 sources like article §1 / article 头部), "
                "script beats for this chapter, and full 01-example template "
                "(Example.tsx + Example.css + narrations.ts). "
                "Call once at build start instead of read_file on article.md or 01-example."
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
            fn=lambda chapter_id=None: _read_chapter_context(chapter_id),
        ),
        AgentTool(
            name="read_source_docs",
            description=(
                "Read script.md and outline.md in one call. "
                "Use to cross-check chapter content against the source plan."
            ),
            input_schema={"type": "object", "properties": {}},
            fn=lambda: _read_source_docs(),
        ),
        AgentTool(
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
            fn=lambda chapter_id=None: _review_chapter_bundle(chapter_id),
        ),
        AgentTool(
            name="report_missing_assets",
            description=(
                "Record missing assets for this chapter into workflow state. "
                "Call before todolist_check(MISSING_ASSETS_NOTE). "
                "Use items=[] if nothing is missing."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "description": "Chapter id (defaults to current chapter)",
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Missing asset descriptions; empty = none missing",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional extra note for the user",
                    },
                },
            },
            fn=lambda chapter_id=None, items=None, note="": _report_missing_assets(
                chapter_id, items, note,
            ),
        ),
        AgentTool(
            name="craft_review_status",
            description="Show CHAPTER-CRAFT 完工自检 checklist progress (20 items from Part 完工自检).",
            input_schema={"type": "object", "properties": {}},
            fn=lambda: _craft_review_status(),
        ),
        AgentTool(
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
            fn=lambda chapter_id=None: _craft_auto_check(chapter_id),
        ),
        AgentTool(
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
            fn=_edit_file,
        ),
        AgentTool(
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
            fn=_write_narrations,
        ),
        AgentTool(
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
            fn=_write_file,
        ),
        AgentTool(
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
            fn=_run_shell,
        ),
        AgentTool(
            name="typecheck",
            description="Run npx tsc --noEmit in the presentation directory.",
            input_schema={"type": "object", "properties": {}},
            fn=lambda: _typecheck(),
        ),
        AgentTool(
            name="check_vite",
            description=(
                "Run npx vite build to verify ALL files compile. "
                "Catches syntax errors, import issues, and JSX escaping problems that tsc might miss."
            ),
            input_schema={"type": "object", "properties": {}},
            fn=lambda: _check_vite(),
        ),
        AgentTool(
            name="read_reference",
            description="Read a reference document.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Reference name like CHAPTER-CRAFT.md"},
                },
                "required": ["name"],
            },
            fn=_read_ref,
        ),
        AgentTool(
            name="list_files",
            description="List files in the workspace matching a glob pattern.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern", "default": "*"},
                },
            },
            fn=lambda pattern="*": _list_files(pattern),
        ),
        AgentTool(
            name="todolist_status",
            description="Show current todo list progress. Call this at the start to see what remains.",
            input_schema={"type": "object", "properties": {}},
            fn=get_todo_status or (lambda: "no todo list"),
        ),
        AgentTool(
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
            fn=lambda item, result="pass", reason="", fix="": _todolist_check(item, result, reason, fix),
        ),
        AgentTool(
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
            fn=_update_registry,
        ),
        AgentTool(
            name="done",
            description="Call this when ALL tasks are complete after review, typecheck, and check_vite.",
            input_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "What was built and verification results"},
                },
                "required": ["summary"],
            },
            fn=verify_all_done or (lambda summary: f"[DONE] {summary}"),
        ),
    ]

    _PROFILE_ALLOW: dict[str, frozenset[str] | None] = {
        "builder": frozenset({
            "workspace_info", "read_chapter_context", "read_reference",
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
    allowed = _PROFILE_ALLOW.get(tool_profile)
    if allowed is not None:
        tools = [t for t in tools if t.name in allowed]
    return tools, ctx
