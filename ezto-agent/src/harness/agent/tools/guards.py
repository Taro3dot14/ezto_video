"""Agent tool invocation guards — profile and build-order policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.workflow.chapter_validation import (
    resolve_workspace_path,
    validate_no_header_footer_tsx,
    validate_theme_contrast,
    validate_tsx_css_classes,
)

from .session import ChapterSessionState

_BUILDER_BLOCKED = frozenset({
    "review_chapter_bundle", "craft_review_status", "craft_review_check",
    "typecheck", "check_vite",
})
_BUILDER_EXPLORE_BLOCKED = frozenset({
    "read_file", "list_files", "run_shell", "read_source_docs",
})
_REVIEWER_BLOCKED = frozenset({
    "write_file", "write_narrations", "edit_file", "update_registry",
    "typecheck", "check_vite", "run_shell",
})
_VERIFY_BLOCKED = frozenset({
    "write_file", "write_narrations", "update_registry", "run_shell",
    "review_chapter_bundle", "craft_review_status", "craft_review_check",
    "read_source_docs", "read_reference", "workspace_info", "list_files",
})


def _session_flags(ctx: ChapterSessionState | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ctx, ChapterSessionState):
        return {
            "profile": ctx.tool_profile,
            "chapter_context_read": ctx.chapter_context_read,
            "review_ok": ctx.review_ok,
            "typecheck_ok": ctx.typecheck_ok,
            "bundle_reviewed": bool(ctx.get("bundle_reviewed")),
        }
    return {
        "profile": ctx.get("tool_profile", "full"),
        "chapter_context_read": bool(ctx.get("chapter_context_read")),
        "review_ok": bool(ctx.get("review_ok")),
        "typecheck_ok": bool(ctx.get("typecheck_ok")),
        "bundle_reviewed": bool(ctx.get("bundle_reviewed")),
    }


def check_tool_guard(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ppt: Path,
    chapter_id: str,
    ctx: ChapterSessionState | dict[str, Any],
) -> str | None:
    """Return error message if tool call should be blocked, else None."""
    ch_dir = ppt / "src" / "chapters" / chapter_id
    nar = ch_dir / "narrations.ts"
    tsx = ch_dir / "index.tsx"

    flags = _session_flags(ctx)
    profile = flags["profile"]
    chapter_context_read = flags["chapter_context_read"]
    review_ok = flags["review_ok"]
    typecheck_ok = flags["typecheck_ok"]
    bundle_reviewed = flags["bundle_reviewed"]

    if profile == "builder" and tool_name in ("read_motion_detail", "read_layout_catalog"):
        if not chapter_context_read:
            return "❌ BLOCKED: call read_chapter_context() first — detail tools supplement Tier-A context."

    if profile == "builder" and tool_name in ("write_narrations", "write_file", "edit_file"):
        if not chapter_context_read:
            return (
                "❌ BLOCKED: call read_chapter_context() first — it bundles layout + "
                "MOTION-SYSTEM.md + mot-* presets + 01-example. Required before writing code."
            )

    if profile == "builder" and tool_name in _BUILDER_BLOCKED:
        return f"❌ BLOCKED: build-phase agent cannot call {tool_name} — reviewer/verify handles this."
    if profile == "builder" and tool_name in _BUILDER_EXPLORE_BLOCKED:
        return (
            f"❌ BLOCKED: builder 请用 read_chapter_context + read_reference(CHAPTER-CRAFT.md)，"
            f"禁止 {tool_name} 探索样式/模板/动画文件（layout + motion 已在 read_chapter_context 内）。"
        )
    if profile == "repair" and tool_name in ("list_files", "run_shell", "read_source_docs", "read_reference"):
        return (
            f"❌ BLOCKED: repair 请读下方 Reviewer failure report + read_chapter_context，"
            f"禁止 {tool_name} 广泛探索。"
        )
    if profile == "reviewer" and tool_name in _REVIEWER_BLOCKED:
        return f"❌ BLOCKED: reviewer agent is read-only — cannot call {tool_name}."
    if profile == "reviewer" and tool_name == "read_reference" and bundle_reviewed:
        return (
            "❌ BLOCKED: review_chapter_bundle already loaded chapter files + checklist — "
            "do not re-read references; use bundle content + todolist_check(ITEM_ID)."
        )
    if profile == "verify" and tool_name in _VERIFY_BLOCKED:
        return f"❌ BLOCKED: verify-phase agent cannot call {tool_name}."

    if tool_name == "typecheck":
        if not review_ok:
            return (
                "❌ BLOCKED: complete CHAPTER-CRAFT 核验清单 — "
                "Reviewer 用 review_chapter_bundle + todolist_check 逐项勾选."
            )
        missing = []
        if not nar.exists():
            missing.append("narrations.ts")
        if not tsx.exists():
            missing.append("index.tsx")
        if missing:
            return f"❌ BLOCKED: write {', '.join(missing)} before typecheck."

    if tool_name in ("review_chapter_bundle", "craft_auto_check"):
        missing = []
        if not nar.exists():
            missing.append("narrations.ts")
        if not tsx.exists():
            missing.append("index.tsx")
        if missing:
            return f"❌ BLOCKED: write {', '.join(missing)} before {tool_name}."

    if tool_name == "craft_review_check":
        return "❌ BLOCKED: craft_review_check 已移除 — Reviewer 用 todolist_check 逐项勾选。"

    if tool_name == "todolist_check":
        from harness.services.tools.craft.craft_review import REVIEWER_ONLY_TODO_IDS

        raw = arguments.get("item")
        names = (
            [str(raw).upper().strip()]
            if isinstance(raw, str)
            else [str(n).upper().strip() for n in (raw or [])]
        )
        hits = [n for n in names if n in REVIEWER_ONLY_TODO_IDS]
        if hits and profile != "reviewer":
            return (
                f"❌ BLOCKED: CHAPTER-CRAFT 核验清单 todolist 仅 Reviewer 可勾选: {', '.join(hits)}"
            )

    if tool_name == "check_vite":
        if not typecheck_ok:
            return "❌ BLOCKED: run typecheck and fix errors before check_vite."
        if not tsx.exists():
            return "❌ BLOCKED: index.tsx missing."
        css = ch_dir / "index.css"
        mismatch = validate_tsx_css_classes(ppt, chapter_id)
        if mismatch:
            return f"❌ BLOCKED: {mismatch} Fix index.css selectors before check_vite."
        if css.exists():
            contrast = validate_theme_contrast(css.read_text(encoding="utf-8"))
            if contrast:
                return f"❌ BLOCKED: {contrast} Fix index.css before check_vite."

    if tool_name == "update_registry":
        if not nar.exists() or not tsx.exists():
            return "❌ BLOCKED: write narrations.ts + index.tsx before update_registry."

    if tool_name == "edit_file":
        path = arguments.get("path", "")
        full = resolve_workspace_path(ppt.parent, path)
        if not full.exists():
            return f"❌ BLOCKED: {path} does not exist — use write_file to create it first."

    if tool_name == "write_file":
        path = arguments.get("path", "")
        content = str(arguments.get("content", ""))
        norm = path.replace("\\", "/")
        if path.endswith("index.css") and not tsx.exists():
            return "❌ BLOCKED: write index.tsx before index.css."
        if (
            profile == "builder"
            and path.endswith("index.tsx")
            and f"chapters/{chapter_id}/" in norm
            and len(content.strip()) < 180
        ):
            n = len(content.strip())
            return (
                f"❌ BLOCKED: index.tsx content is only {n} chars — pass the full file "
                "in write_file(content=...): SceneChrome + lx-* + mot-* per step."
            )
        if path.endswith("index.tsx") and f"chapters/{chapter_id}/" in norm:
            header_err = validate_no_header_footer_tsx(content)
            if header_err:
                return (
                    f"❌ BLOCKED: no page header/footer — {header_err} "
                    "Use `<SceneChrome>` content-only; no brand/issue/masthead."
                )

    return None
