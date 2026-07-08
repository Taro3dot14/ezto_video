"""Chapter-scoped tool runtime — guard + handler execution."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness.core.state import VideoWorkflowState
from harness.services.tools.build.typescript import run_typecheck as svc_run_typecheck
from harness.services.tools.build.vite import check_vite as svc_check_vite
from harness.services.tools.chapter.chapter_bundle import review_chapter_bundle as svc_review_chapter_bundle
from harness.services.tools.chapter.chapter_context import (
    read_chapter_context as svc_read_chapter_context,
    read_layout_catalog as svc_read_layout_catalog,
    read_motion_detail as svc_read_motion_detail,
)
from harness.services.tools.chapter.missing_assets import report_missing_assets as svc_report_missing_assets
from harness.services.tools.chapter.narrations import write_narrations as svc_write_narrations
from harness.services.tools.chapter.source_docs import read_source_docs as svc_read_source_docs
from harness.services.tools.core.shell import normalize_presentation_command, run_shell as svc_run_shell
from harness.services.tools.craft.craft_review import (
    craft_auto_check as svc_craft_auto_check,
    format_craft_checklist,
    on_typecheck_pass,
    push_craft_checklist_event,
)
from harness.services.tools.fs.file_ops import (
    edit_file as svc_edit_file,
    list_files as svc_list_files,
    read_files as svc_read_files,
    write_file as svc_write_file,
)
from harness.workflow.artifacts import sync_built_chapter_registry
from harness.workflow.chapter_ids import resolve_chapter_id
from harness.workflow.guards import require_ref_loaded

from .guards import check_tool_guard
from .result import ToolResult
from .session import ChapterSessionState


def _strip_blocked_prefix(msg: str) -> str:
    return msg.removeprefix("❌ BLOCKED:").strip()


class ChapterToolRuntime:
    """Binds workspace paths, session state, and policy guards to tool handlers."""

    def __init__(
        self,
        state: VideoWorkflowState,
        session: ChapterSessionState,
        *,
        ws: Path,
        ppt: Path,
        chapter_id: str,
        chapter_title: str = "",
        mark_todo_done: Callable[..., str] | None = None,
        verify_all_done: Callable[..., str] | None = None,
        get_todo_status: Callable[[], str] | None = None,
    ) -> None:
        self.state = state
        self.session = session
        self.ws = ws
        self.ppt = ppt
        self.chapter_id = chapter_id
        self.chapter_title = chapter_title
        self._mark_todo_done = mark_todo_done
        self._verify_all_done = verify_all_done
        self._get_todo_status = get_todo_status

    def guarded(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        action: Callable[[], str | ToolResult],
    ) -> ToolResult:
        blocked = check_tool_guard(
            tool_name,
            arguments,
            ppt=self.ppt,
            chapter_id=self.chapter_id,
            ctx=self.session,
        )
        if blocked:
            return ToolResult.blocked(_strip_blocked_prefix(blocked))
        try:
            out = action()
        except Exception as e:
            return ToolResult.exec_error(str(e))
        if isinstance(out, ToolResult):
            return out
        return ToolResult.from_handler_output(str(out), tool_name=tool_name)

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else self.ws / path

    # --- Handlers (return ToolResult) ---

    def workspace_info(self) -> ToolResult:
        return ToolResult.success(
            "Workspace root: " + str(self.ws) + "\n"
            "Presentation dir: " + str(self.ppt) + "\n"
            "write_file/read_file paths: presentation/src/chapters/<chapter_id>/index.tsx\n"
            "run_shell paths (cwd=presentation/): src/chapters/<chapter_id>/index.tsx\n"
            "Coding pattern: call read_chapter_context (layout + motion + 01-example — NOT read_file)\n"
            "Registry: presentation/src/registry/chapters.ts"
        )

    def read_file(
        self,
        path: str | list[str],
        offset: int = 1,
        limit: int | None = None,
    ) -> ToolResult:
        if isinstance(path, str):
            paths = [str(self._resolve_path(path))]
        else:
            paths = [str(self._resolve_path(p)) for p in path]
        return ToolResult.success(
            svc_read_files(self.state, paths, offset=offset, limit=limit),
        )

    def read_chapter_context(self, chapter_id: str | None = None) -> ToolResult:
        cid = (chapter_id or self.session.chapter_id).strip()
        body = svc_read_chapter_context(
            self.state,
            workspace_root=self.ws,
            chapter_id=cid,
            chapter_index=self.session.get("chapter_index", 1),
            chapter_title=self.chapter_title,
        )
        return ToolResult.success(body)

    def read_motion_detail(self) -> ToolResult:
        return self.guarded("read_motion_detail", {}, lambda: svc_read_motion_detail(
            self.state, workspace_root=self.ws,
        ))

    def read_layout_catalog(self) -> ToolResult:
        return self.guarded("read_layout_catalog", {}, lambda: svc_read_layout_catalog(
            self.state, workspace_root=self.ws,
        ))

    def read_source_docs(self) -> ToolResult:
        return ToolResult.success(svc_read_source_docs(self.state, workspace_root=self.ws))

    def review_chapter_bundle(self, chapter_id: str | None = None) -> ToolResult:
        cid = (chapter_id or self.session.chapter_id).strip()

        def _run() -> str:
            content, ok = svc_review_chapter_bundle(
                self.state, workspace_root=self.ws, chapter_id=cid, ctx=self.session,
            )
            self.session.mark_bundle_reviewed(review_ok=ok)
            push_craft_checklist_event(self.state, self.session)
            return content

        return self.guarded("review_chapter_bundle", {"chapter_id": cid}, _run)

    def craft_review_status(self) -> ToolResult:
        return ToolResult.success(format_craft_checklist(self.session))

    def craft_auto_check(self, chapter_id: str | None = None) -> ToolResult:
        cid = (chapter_id or self.session.chapter_id).strip()

        def _run() -> str:
            content = svc_craft_auto_check(self.session, workspace_root=self.ws, chapter_id=cid)
            push_craft_checklist_event(self.state, self.session)
            return content

        return self.guarded("craft_auto_check", {"chapter_id": cid}, _run)

    def write_file(self, path: str, content: str) -> ToolResult:
        def _run() -> str:
            full = self._resolve_path(path)
            svc_write_file(self.state, str(full), content)
            shell_path = path.removeprefix("presentation/") if path.startswith("presentation/") else path
            return (
                f"Written {len(content)} chars to {path}\n"
                f"Absolute: {full}\n"
                f"run_shell equivalent: {shell_path} (cwd=presentation/)"
            )

        return self.guarded("write_file", {"path": path, "content": content}, _run)

    def edit_file(self, path: str, old_string: str, new_string: str) -> ToolResult:
        return self.guarded(
            "edit_file",
            {"path": path},
            lambda: svc_edit_file(
                self.state, str(self._resolve_path(path)), old_string, new_string,
            ),
        )

    def run_shell(self, command: str) -> ToolResult:
        def _run() -> str:
            try:
                cmd, hint = normalize_presentation_command(command)
            except re.error as e:
                return (
                    f"❌ Invalid shell command normalization: {e}\n"
                    "Use paths without presentation/ prefix (cwd is presentation/)."
                )
            result = svc_run_shell(self.state, cmd, cwd=str(self.ppt))
            out = [f"cwd: {self.ppt}"]
            if hint:
                out.append(hint)
            if result.stdout:
                out.append(result.stdout[:5000])
            if result.stderr:
                out.append(f"STDERR:\n{result.stderr[:2000]}")
            out.append(f"→ exit code {result.returncode}")
            return "\n".join(out)

        return self.guarded("run_shell", {"command": command}, _run)

    def write_narrations(self, chapter_id: str, lines: list[str]) -> ToolResult:
        if not lines:
            return ToolResult.success("❌ lines must be a non-empty array of narration strings")

        def _run() -> str:
            try:
                msg = svc_write_narrations(
                    self.state, workspace_root=self.ws, chapter_id=chapter_id, lines=lines,
                )
            except ValueError as e:
                return f"❌ {e}"
            shell_path = f"src/chapters/{chapter_id}/narrations.ts"
            return f"{msg}\nrun_shell equivalent: {shell_path} (cwd=presentation/)"

        return self.guarded(
            "write_narrations",
            {"chapter_id": chapter_id, "lines": lines},
            _run,
        )

    def typecheck(self) -> ToolResult:
        def _run() -> str:
            result = svc_run_typecheck(self.state, cwd=str(self.ppt))
            if result.returncode == 0:
                self.session.mark_typecheck(ok=True)
                on_typecheck_pass(self.session)
                push_craft_checklist_event(self.state, self.session)
                return "✅ TypeScript type check passed"
            self.session.mark_typecheck(ok=False)
            return f"❌ TypeScript errors:\n{result.stdout[:5000]}"

        return self.guarded("typecheck", {}, _run)

    def check_vite(self) -> ToolResult:
        def _run() -> str:
            result = svc_check_vite(self.state, cwd=self.ppt)
            self.session.mark_vite(ok=result.success)
            return result.message

        return self.guarded("check_vite", {}, _run)

    def read_reference(self, name: str) -> ToolResult:
        return ToolResult.success(require_ref_loaded(self.state, name))

    def list_files(self, pattern: str = "*") -> ToolResult:
        return ToolResult.success(svc_list_files(self.ws, pattern))

    def update_registry(self, chapter_id: str, title: str) -> ToolResult:
        def _run() -> str:
            tsx = self.ppt / "src" / "chapters" / chapter_id / "index.tsx"
            nar = self.ppt / "src" / "chapters" / chapter_id / "narrations.ts"
            missing = []
            if not tsx.exists():
                missing.append("index.tsx")
            if not nar.exists():
                missing.append("narrations.ts")
            if missing:
                return f"❌ Cannot update registry — missing: {', '.join(missing)}. Write files first."
            return sync_built_chapter_registry(self.state, chapter_id, title)

        return self.guarded("update_registry", {"chapter_id": chapter_id}, _run)

    def report_missing_assets(
        self,
        chapter_id: str | None = None,
        items: list[str] | None = None,
        note: str = "",
    ) -> ToolResult:
        raw = (chapter_id or self.session.chapter_id).strip()
        cid, warn = resolve_chapter_id(self.state, raw, default=self.session.chapter_id)
        body = svc_report_missing_assets(
            self.state, chapter_id=cid, items=items, note=note,
        )
        text = f"{warn}\n{body}" if warn else body
        return ToolResult.success(text)

    def todolist_status(self) -> ToolResult:
        if self._get_todo_status:
            return ToolResult.success(self._get_todo_status())
        return ToolResult.success("no todo list")

    def todolist_check(
        self,
        item: str | list[str],
        result: str = "pass",
        reason: str = "",
        fix: str = "",
    ) -> ToolResult:
        args = {"item": item, "result": result, "reason": reason, "fix": fix}

        def _run() -> str:
            if self._mark_todo_done:
                return self._mark_todo_done(item, result=result, reason=reason, fix=fix)
            return f"todolist: {item}"

        return self.guarded("todolist_check", args, _run)

    def done(self, summary: str) -> ToolResult:
        if self._verify_all_done:
            return ToolResult.from_handler_output(
                self._verify_all_done(summary), tool_name="done",
            )
        return ToolResult.done_summary(summary)
