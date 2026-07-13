"""Shared projection / theme CSS checks for auto_validate and craft review."""

from __future__ import annotations

import re
from pathlib import Path

# macOS window chrome + common terminal simulation colors (functional, not theme decoration)
_ALLOWED_LITERAL_HEX = frozenset({
    "#ff5f57", "#ff5f56", "#febc2e", "#ffbd2e", "#28c840", "#27c93f",
    "#1a1a2e", "#e0e0e0", "#2d2d2d", "#383838",
})

# Selectors whose hex colors are exempt from THEME_TOKENS (terminal / window chrome)
_DECORATIVE_HEX_SELECTOR_RE = re.compile(
    r"(?:terminal|window|win-|titlebar|chrome|traffic|"
    r"dot|code-|shell|prompt|editor|hljs|mono)",
    re.I,
)

# Auxiliary copy (captions, kickers) — floor 22px
_AUX_SELECTOR_RE = re.compile(
    r"(?:kicker|caption|tagline|cue|eyebrow|meta|subtitle|badge-sep|badge-tagline|"
    r"step-\d+-caption|terminal-caption|foot|label)",
    re.I,
)

# Decorative UI (SVG labels, code blocks, window cards) — skip font-size floor entirely
_DECORATIVE_FONT_SELECTOR_RE = re.compile(
    r"(?:\bsvg\b|tspan|foreignobject|"
    r"\bcode\b|pre|mono|terminal|window|win-|"
    r"dot|node-label|svg-label|code-body|code-out|code-label|code-line|"
    r"prompt|shell|editor|hljs|traffic|titlebar)",
    re.I,
)

_DEFAULT_TOKEN_MIN_PX: dict[str, int] = {
    "--t-projection-hero": 75,
    "--t-projection-title": 58,
    "--t-projection-body": 28,
    "--t-display-1": 75,
    "--t-display-2": 58,
    "--t-h1": 58,
    "--t-h2": 38,
    "--t-h3": 28,
    "--t-body": 28,
    "--t-cue": 22,
}


def strip_decorative_hex_for_theme_check(css: str) -> str:
    """Remove hex/rgba from terminal/window/chrome rule blocks before THEME_TOKENS scan."""
    parts: list[str] = []
    for m in re.finditer(r"([^{]+)\{([^}]+)\}", css):
        selector, body = m.group(1), m.group(2)
        if _DECORATIVE_HEX_SELECTOR_RE.search(selector):
            body = re.sub(r"#[0-9a-fA-F]{3,8}\b", "", body)
            body = re.sub(r"rgba?\([^)]+\)", "", body)
        parts.append(selector + "{" + body + "}")
    tail_start = max((m.end() for m in re.finditer(r"\}", css)), default=0)
    if tail_start < len(css):
        parts.append(css[tail_start:])
    blob = "".join(parts) if parts else css
    return _filter_allowed_literal_hex(blob)


def _filter_allowed_literal_hex(text: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        return "" if m.group(0).lower() in _ALLOWED_LITERAL_HEX else m.group(0)

    return re.sub(r"#[0-9a-fA-F]{3,8}\b", _repl, text)


def hex_colors_for_theme_check(blob: str) -> list[str]:
    return re.findall(r"#[0-9a-fA-F]{3,8}\b", blob)


def index_css_declares_font_size(css: str) -> bool:
    if re.search(r"font-size\s*:", css):
        return True
    return bool(re.search(r"font\s*:[^;{]*\d", css))


def parse_projection_token_mins(ppt: Path | None) -> dict[str, int]:
    if ppt is None:
        return dict(_DEFAULT_TOKEN_MIN_PX)
    base = ppt / "src" / "styles" / "base.css"
    if not base.exists():
        return dict(_DEFAULT_TOKEN_MIN_PX)
    text = base.read_text(encoding="utf-8", errors="replace")
    mins = dict(_DEFAULT_TOKEN_MIN_PX)
    for name, val in re.findall(r"(--t-[\w-]+)\s*:\s*([^;]+);", text):
        if not (
            "projection" in name
            or name in ("--t-display-1", "--t-display-2", "--t-h1", "--t-h2", "--t-h3", "--t-body", "--t-cue")
        ):
            continue
        px = re.search(r"(\d+)px", val)
        if px:
            mins[name] = int(px.group(1))
    return mins


def _font_floor_for_selector(selector: str) -> int | None:
    """Return min px floor, or None to skip this rule block entirely."""
    if _DECORATIVE_FONT_SELECTOR_RE.search(selector):
        return None
    if _AUX_SELECTOR_RE.search(selector):
        return 22
    return 28


def collect_font_size_violations(css: str, *, ppt: Path | None = None) -> list[str]:
    """Body/auxiliary font-size violations; decorative selectors (SVG, code, window) exempt."""
    if not index_css_declares_font_size(css):
        return []
    token_mins = parse_projection_token_mins(ppt)
    violations: list[str] = []
    for block in re.finditer(r"([^{]+)\{([^}]+)\}", css):
        selector = block.group(1)
        body = block.group(2)
        floor = _font_floor_for_selector(selector)
        if floor is None:
            continue
        for px in re.findall(r"font-size:\s*(\d+)px", body):
            size = int(px)
            if size < floor:
                violations.append(f"{size}px ({selector.strip()[:40]})")
        for var in re.findall(r"font-size:\s*var\(\s*(--[\w-]+)", body):
            size = token_mins.get(var, 28)
            if size < floor:
                violations.append(f"{var}→{size}px ({selector.strip()[:40]})")
    return violations


def format_auto_validate_font_hint(violations: list[str]) -> str | None:
    if not violations:
        return None
    return (
        "⚠️ auto_validate: body/auxiliary copy uses font-size below floor "
        f"({'; '.join(violations[:4])}). "
        "Use projection tokens (≥28px body, ≥22px auxiliary). "
        "SVG / code-block / window-card labels are exempt."
    )


# Tokens agents often invent — suggest real names from tokens.css
_BOGUS_TOKEN_SUGGESTIONS: dict[str, tuple[str, ...]] = {
    "--bg": ("--shell", "--surface", "--surface-2"),
    "--background": ("--shell", "--surface"),
    "--foreground": ("--text", "--text-2"),
    "--primary": ("--accent", "--text"),
}


def load_theme_css_vars(ppt: Path) -> set[str]:
    """Collect custom property names declared in tokens.css + base.css."""
    names: set[str] = set()
    for rel in ("src/styles/tokens.css", "src/styles/base.css"):
        path = ppt / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        names.update(re.findall(r"(--[\w-]+)\s*:", text))
    return names


def find_invalid_css_var_refs(css: str, known: set[str]) -> list[str]:
    invalid: list[str] = []
    for var in re.findall(r"var\(\s*(--[\w-]+)", css):
        if var not in known:
            invalid.append(var)
    return sorted(set(invalid))


def format_invalid_var_message(invalid: list[str]) -> str:
    parts: list[str] = []
    for var in invalid[:6]:
        if var in _BOGUS_TOKEN_SUGGESTIONS:
            alts = ", ".join(f"`{a}`" for a in _BOGUS_TOKEN_SUGGESTIONS[var])
            parts.append(f"{var} (use {alts})")
        else:
            parts.append(var)
    return ", ".join(parts)


def format_theme_token_catalog(ppt: Path, *, max_items: int = 28) -> str:
    """Compact token list for Repair agent — only names that exist on disk."""
    known = sorted(load_theme_css_vars(ppt))
    if not known:
        return ""
    priority = [
        t for t in known
        if any(k in t for k in ("shell", "surface", "text", "accent", "rule", "ink", "font"))
    ]
    rest = [t for t in known if t not in priority]
    ordered = (priority + rest)[:max_items]
    lines = ["## Theme tokens (ONLY these exist — do not invent `--bg` etc.)"]
    lines.append(", ".join(f"`{t}`" for t in ordered))
    if len(known) > max_items:
        lines.append(f"(+{len(known) - max_items} more in tokens.css / base.css)")
    lines.append(
        "On accent backgrounds use `var(--shell)` or `var(--text)` — never undefined vars."
    )
    return "\n".join(lines)

