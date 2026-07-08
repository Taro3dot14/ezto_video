"""Post-write and static validation for chapter artifacts (non-guard)."""

from __future__ import annotations

import re
from pathlib import Path

from harness.workflow.step_indexing import (
    count_narration_lines,
    narrations_mismatch_hint,
    parse_max_code_step,
)

_GLOBAL_CLASSES = frozenset({
    "arrow", "badge-mono", "brand", "card", "card-glass", "center", "click-cue",
    "corner-mark", "display-en", "dot-accent", "fade-in", "fill", "hero-num",
    "in", "is-accent", "issue", "kicker", "label-mono", "letter", "letter-stagger",
    "mask-reveal", "mono", "masthead", "mot-delay-200", "mot-delay-400",
    "no-advance", "ord", "pull-quote", "row", "rule", "rule-accent", "rule-grow",
    "scene", "scene-pad", "serif-cn", "display-en-soft", "slash", "stack",
    "tr-rule", "visible",
})
_GLOBAL_CLASS_PREFIXES = ("lx-", "mot-")


def is_template_global_class(name: str) -> bool:
    """True if className is defined in shared template CSS (not chapter index.css)."""
    if name in _GLOBAL_CLASSES:
        return True
    return any(name.startswith(p) for p in _GLOBAL_CLASS_PREFIXES)


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


def classify_tsx_css_classes(
    ppt: Path,
    chapter_id: str,
) -> tuple[list[str], list[str]]:
    """Return (chapter_missing, global_skipped) class names not in index.css."""
    ch_dir = ppt / "src" / "chapters" / chapter_id
    tsx = ch_dir / "index.tsx"
    css = ch_dir / "index.css"
    if not tsx.exists() or not css.exists():
        return [], []

    tsx_classes = _extract_tsx_classes(tsx.read_text(encoding="utf-8"))
    css_classes = _extract_css_classes(css.read_text(encoding="utf-8"))
    not_in_css = sorted(c for c in tsx_classes if c not in css_classes)
    global_skipped = sorted(c for c in not_in_css if is_template_global_class(c))
    chapter_missing = sorted(c for c in not_in_css if not is_template_global_class(c))
    return chapter_missing, global_skipped


def validate_tsx_css_classes(ppt: Path, chapter_id: str) -> str | None:
    """Return error if chapter-specific TSX classNames are missing from index.css."""
    chapter_missing, _global_skipped = classify_tsx_css_classes(ppt, chapter_id)
    if not chapter_missing:
        return None
    preview = ", ".join(f".{name}" for name in chapter_missing[:8])
    extra = f" (+{len(chapter_missing) - 8} more)" if len(chapter_missing) > 8 else ""
    return (
        f"index.css missing selectors for chapter TSX classes: {preview}{extra}. "
        "Every chapter-specific className (e.g. ch-*) must have a matching rule in index.css. "
        "Global lx-*/mot-*/mask-reveal/in are defined in layouts.css / motion/ — do not duplicate."
    )


def validate_no_header_footer_tsx(tsx_text: str) -> str | None:
    """Return error if chapter TSX adds page header/footer chrome."""
    from harness.services.tools.craft.craft_review import _check_no_header_footer

    ok, msg = _check_no_header_footer(tsx_text)
    if ok:
        return None
    return msg


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

    header_err = validate_no_header_footer_tsx(tsx_text)
    if header_err:
        hints.append(f"❌ auto_validate: NO_HEADER_FOOTER — {header_err}")

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


def resolve_workspace_path(ws: Path, path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ws / path
