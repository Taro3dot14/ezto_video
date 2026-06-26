"""Chapter build order policies and post-write validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness.workflow.step_indexing import (
    count_narration_lines,
    narrations_mismatch_hint,
    parse_max_code_step,
)

# Primitive / global classes from base.css — not required in chapter index.css
_GLOBAL_CLASSES = frozenset({
    "arrow", "badge-mono", "brand", "card", "card-glass", "center", "click-cue",
    "corner-mark", "display-en", "dot-accent", "fade-in", "fill", "hero-num",
    "is-accent", "issue", "kicker", "label-mono", "mono", "masthead", "no-advance",
    "ord", "pull-quote", "row", "rule", "rule-accent", "scene", "scene-pad",
    "serif-cn", "display-en", "display-en-soft", "slash", "stack", "tr-rule", "visible",
})


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


def check_tool_guard(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ppt: Path,
    chapter_id: str,
    ctx: dict[str, Any],
) -> str | None:
    """Return error message if tool call should be blocked, else None."""
    ch_dir = ppt / "src" / "chapters" / chapter_id
    nar = ch_dir / "narrations.ts"
    tsx = ch_dir / "index.tsx"

    profile = ctx.get("tool_profile", "full")
    if profile == "builder" and tool_name in _BUILDER_BLOCKED:
        return f"❌ BLOCKED: build-phase agent cannot call {tool_name} — reviewer/verify handles this."
    if profile == "builder" and tool_name in _BUILDER_EXPLORE_BLOCKED:
        return (
            f"❌ BLOCKED: builder 请用 read_chapter_context + read_reference(CHAPTER-CRAFT.md)，"
            f"禁止 {tool_name} 探索样式/模板文件。"
        )
    if profile == "repair" and tool_name in ("list_files", "run_shell", "read_source_docs", "read_reference"):
        return (
            f"❌ BLOCKED: repair 请读下方 Reviewer failure report + read_chapter_context，"
            f"禁止 {tool_name} 广泛探索。"
        )
    if profile == "reviewer" and tool_name in _REVIEWER_BLOCKED:
        return f"❌ BLOCKED: reviewer agent is read-only — cannot call {tool_name}."
    if profile == "verify" and tool_name in _VERIFY_BLOCKED:
        return f"❌ BLOCKED: verify-phase agent cannot call {tool_name}."

    if tool_name == "typecheck":
        if not ctx.get("review_ok"):
            return (
                "❌ BLOCKED: complete CHAPTER-CRAFT 完工自检 — "
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
        from harness.services.tools.craft_review import REVIEWER_ONLY_TODO_IDS

        raw = arguments.get("item")
        names = (
            [str(raw).upper().strip()]
            if isinstance(raw, str)
            else [str(n).upper().strip() for n in (raw or [])]
        )
        hits = [n for n in names if n in REVIEWER_ONLY_TODO_IDS]
        if hits and profile != "reviewer":
            return (
                f"❌ BLOCKED: CHAPTER-CRAFT 自检 todolist 仅 Reviewer 可勾选: {', '.join(hits)}"
            )

    if tool_name == "check_vite":
        if not ctx.get("typecheck_ok"):
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
        full = _resolve(ppt.parent, path)
        if not full.exists():
            return f"❌ BLOCKED: {path} does not exist — use write_file to create it first."

    if tool_name == "write_file":
        path = arguments.get("path", "")
        if path.endswith("index.css") and not tsx.exists():
            return "❌ BLOCKED: write index.tsx before index.css."

    return None


def _extract_tsx_classes(tsx_text: str) -> set[str]:
    classes: set[str] = set()
    for match in re.finditer(r'className="([^"]+)"', tsx_text):
        for token in match.group(1).split():
            if token and not token.startswith("{"):
                classes.add(token)
    return classes


def _extract_css_classes(css_text: str) -> set[str]:
    return set(re.findall(r"\.([a-z][\w-]*)", css_text))


_INVALID_THEME_TOKENS = ("--bg", "--border")
_DARK_BG_PATTERN = re.compile(
    r"background\s*:\s*(?:var\(\s*--bg|#0[0-9a-f]{2,5}\b|rgb\(\s*0\s*,\s*0\s*,\s*0)",
    re.IGNORECASE,
)


def validate_theme_contrast(css_text: str) -> str | None:
    """Return error if chapter CSS uses invalid tokens or dark-bg + theme-text trap."""
    issues: list[str] = []
    for token in _INVALID_THEME_TOKENS:
        if token in css_text:
            issues.append(
                f"uses invented token {token} — use --shell/--surface/--surface-2 for bg, --rule for borders"
            )
    if _DARK_BG_PATTERN.search(css_text) and "var(--text" in css_text:
        issues.append(
            "dark scene background with theme --text — on light themes text is dark ink and becomes unreadable"
        )
    if not issues:
        return None
    return "Theme contrast: " + "; ".join(issues) + "."


def validate_tsx_css_classes(ppt: Path, chapter_id: str) -> str | None:
    """Return error if index.tsx classNames are missing from index.css."""
    ch_dir = ppt / "src" / "chapters" / chapter_id
    tsx = ch_dir / "index.tsx"
    css = ch_dir / "index.css"
    if not tsx.exists() or not css.exists():
        return None

    tsx_classes = _extract_tsx_classes(tsx.read_text(encoding="utf-8"))
    css_classes = _extract_css_classes(css.read_text(encoding="utf-8"))
    chapter_classes = {c for c in tsx_classes if c not in _GLOBAL_CLASSES}
    missing = sorted(chapter_classes - css_classes)
    if not missing:
        return None
    preview = ", ".join(f".{name}" for name in missing[:8])
    extra = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
    return (
        f"index.css missing selectors for TSX classes: {preview}{extra}. "
        "Every chapter-specific className must have a matching rule in index.css."
    )


def validate_chapter_tsx_contract(tsx_text: str) -> str | None:
    """Return error if index.tsx uses wrong step wiring (e.g. hallucinated store)."""
    if "useChapterStore" in tsx_text or "/store/useChapterStore" in tsx_text:
        return (
            "index.tsx imports useChapterStore — this module does not exist. "
            "Use `import type { ChapterStepProps } from \"../../registry/types\"` "
            "and `export default function ...({ step }: ChapterStepProps)`."
        )
    if "ChapterStepProps" not in tsx_text and "step }: {" not in tsx_text:
        if re.search(r"export\s+default\s+function\s+\w+\s*\(\s*\)", tsx_text):
            return (
                "index.tsx chapter component takes no props — step must come from "
                "ChapterStepProps: `export default function X({ step }: ChapterStepProps)`."
            )
    return None


def auto_validate_chapter(
    ppt: Path,
    chapter_id: str,
    *,
    written_path: str = "",
) -> str | None:
    """Quick post-write checks; returns hint string or None."""
    ch_dir = ppt / "src" / "chapters" / chapter_id
    nar = ch_dir / "narrations.ts"
    tsx = ch_dir / "index.tsx"
    if not nar.exists() or not tsx.exists():
        return None

    hints: list[str] = []

    nar_text = nar.read_text(encoding="utf-8")
    nar_count = count_narration_lines(nar_text)

    tsx_text = tsx.read_text(encoding="utf-8")
    contract_err = validate_chapter_tsx_contract(tsx_text)
    if contract_err:
        hints.append(f"❌ auto_validate: {contract_err}")

    max_step = parse_max_code_step(tsx_text)
    if max_step is not None:
        mismatch = narrations_mismatch_hint(nar_count=nar_count, max_code_step=max_step)
        if mismatch:
            hints.append(f"⚠️ auto_validate: {mismatch}")

    if written_path.endswith((".tsx", ".css")):
        mismatch = validate_tsx_css_classes(ppt, chapter_id)
        if mismatch:
            hints.append(f"⚠️ auto_validate: {mismatch}")

    if written_path.endswith(".css"):
        css_text = (ch_dir / "index.css").read_text(encoding="utf-8")
        from harness.workflow.css_projection_checks import (
            collect_font_size_violations,
            format_auto_validate_font_hint,
        )
        font_hint = format_auto_validate_font_hint(
            collect_font_size_violations(css_text, ppt=ppt),
        )
        if font_hint:
            hints.append(font_hint)
        contrast = validate_theme_contrast(css_text)
        if contrast:
            hints.append(f"⚠️ auto_validate: {contrast}")

    return "\n".join(hints) if hints else None


def _resolve(ws: Path, path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ws / path
