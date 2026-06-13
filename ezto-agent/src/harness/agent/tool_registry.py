"""Agent tool definitions — wraps services/tools with LLM-friendly schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import run_shell as svc_run_shell
from harness.services.tools.file_ops import read_file as svc_read_file, write_file as svc_write_file
from harness.services.tools.typescript import run_typecheck as svc_run_typecheck
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


def make_build_agent_tools(
    state: VideoWorkflowState,
    *,
    get_todo_status: Any = None,
    mark_todo_done: Any = None,
    verify_all_done: Any = None,
) -> list[AgentTool]:
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / "presentation"

    def _read_file(path: str | list[str]) -> str:
        if isinstance(path, str):
            files = [path]
        else:
            files = path
        results = []
        for p in files:
            full = ws / p if not Path(p).is_absolute() else Path(p)
            try:
                content = svc_read_file(state, str(full))
                results.append(f"--- {p} ---\n{content}")
            except Exception as e:
                results.append(f"--- {p} ---\nERROR: {e}")
        return "\n\n".join(results)

    def _write_file(path: str, content: str) -> str:
        full = ws / path if not Path(path).is_absolute() else Path(path)
        svc_write_file(state, str(full), content)
        return f"Written {len(content)} chars to {path}"

    def _run_shell(command: str) -> str:
        result = svc_run_shell(state, command, cwd=str(ppt))
        out = []
        if result.stdout:
            out.append(result.stdout[:5000])
        if result.stderr:
            out.append(f"STDERR:\n{result.stderr[:2000]}")
        out.append(f"→ exit code {result.returncode}")
        return "\n".join(out)

    def _typecheck() -> str:
        result = svc_run_typecheck(state, cwd=str(ppt))
        if result.returncode == 0:
            return "✅ TypeScript type check passed"
        return f"❌ TypeScript errors:\n{result.stdout[:5000]}"

    def _read_ref(name: str) -> str:
        return require_ref_loaded(state, name)

    def _list_files(pattern: str = "*") -> str:
        matched = list(ws.rglob(pattern))
        if not matched:
            return f"No files matching '{pattern}'"
        return "\n".join(str(p.relative_to(ws)) for p in sorted(matched)[:50])

    def _update_registry(chapter_id: str, title: str) -> str:
        """Update chapters.ts. Verifies files exist first."""
        tsx = ppt / "src" / "chapters" / chapter_id / "index.tsx"
        nar = ppt / "src" / "chapters" / chapter_id / "narrations.ts"
        missing = []
        if not tsx.exists():
            missing.append("index.tsx")
        if not nar.exists():
            missing.append("narrations.ts")
        if missing:
            return f"❌ Cannot update registry — missing: {', '.join(missing)}. Write files first."
        reg_file = ppt / "src" / "registry" / "chapters.ts"
        imports = (
            f"import {chapter_id} from '@/chapters/{chapter_id}';\n"
            f"import {{ narrations as {chapter_id}Narrations }} from '@/chapters/{chapter_id}/narrations';\n"
        )
        entries = (
            f"  {{\n    id: '{chapter_id}',\n    title: '{title}',\n"
            f"    narrations: {chapter_id}Narrations,\n    Component: {chapter_id},\n  }},"
        )
        content = (
            "import type { ChapterDef } from './types';\n"
            f"{imports}\n"
            "export const CHAPTERS: ChapterDef[] = [\n"
            f"{entries}\n];\n"
        )
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        reg_file.write_text(content, encoding="utf-8")
        return f"✅ Registry updated: {chapter_id} — {title}"

    def _check_vite() -> str:
        """vite build → curl existing dev server to verify page loads."""
        import subprocess, urllib.request
        from configs import settings

        # 1. vite build (catches compile errors)
        proc = subprocess.run(
            ["npx", "vite", "build"],
            cwd=str(ppt),
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
        stdout = (proc.stdout or "") + "\n" + (proc.stderr or "")
        all_lines = stdout.splitlines()
        errors = [l for l in all_lines if "error" in l.lower() and "warning" not in l.lower()]

        if proc.returncode != 0 or errors:
            return (
                f"❌ VITE BUILD FAILED (exit={proc.returncode}, {len(errors)} errors):\n"
                + "\n".join(errors[:10])
                + f"\n\nFull output:\n```\n{stdout[-3000:]}\n```\n\nACTION: Fix the errors above, then run check_vite again."
            )

        # 2. Curl the existing dev server (started by scaffold)
        port = settings.presentation_port
        page_ok = False
        page_error = ""
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/?chapter=0", timeout=10)
            body = resp.read().decode(errors="replace")
            if "<div id=\"root\">" in body and "<script" in body:
                page_ok = True
            else:
                page_error = f"Page returned {resp.status} but missing expected HTML elements"
        except Exception as e:
            page_error = str(e)

        if page_ok:
            return f"✅ Build OK, page loads at http://localhost:{port}/?chapter=0"
        return (
            f"❌ Build OK but page FAILED to load at http://localhost:{port}/?chapter=0\n"
            f"Error: {page_error}\n\nACTION: Fix the page load error, then run check_vite again."
        )


    return [
        AgentTool(
            name="workspace_info",
            description="Get workspace paths. Call this FIRST to understand directory layout and where to write files.",
            input_schema={"type": "object", "properties": {}},
            fn=lambda: ("Workspace root: " + str(ws) + "\n"
                       "Presentation dir: " + str(ppt) + "\n"
                       "Chapter files: presentation/src/chapters/<chapter_id>/\n"
                       "To read example: presentation/src/chapters/01-example/Example.tsx\n"
                       "Registry: presentation/src/registry/chapters.ts"),
        ),
        AgentTool(
            name="read_file",
            description="Read one or more files. Pass a single path string or an array of paths. Paths relative to workspace root.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                },
                "required": ["path"],
            },
            fn=_read_file,
        ),
        AgentTool(
            name="write_file",
            description="Write content to a file. Creates parent directories if needed.",
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
            description="Run a shell command in the presentation directory.",
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
            description="Run npx vite build to verify ALL files compile. Catches syntax errors, import issues, and JSX escaping problems that tsc might miss.",
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
            description="Mark one or more todo items as completed. Pass a single item name or an array of names. Use todolist_status() first to see available items and their descriptions.",
            input_schema={
                "type": "object",
                "properties": {
                    "item": {
                        "oneOf": [
                            {"type": "string", "description": "Single item name"},
                            {"type": "array", "items": {"type": "string"}, "description": "Multiple item names"},
                        ],
                        "description": "Item name(s) to mark as done",
                    },
                },
                "required": ["item"],
            },
            fn=mark_todo_done or (lambda item: f"todolist: {item}"),
        ),
        AgentTool(
            name="update_registry",
            description="Register a chapter in chapters.ts so typecheck sees it. ONLY call AFTER writing both index.tsx and narrations.ts — it will refuse if files are missing.",
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
            description="Call this when ALL tasks are complete after writing files, typecheck, and check_vite.",
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
