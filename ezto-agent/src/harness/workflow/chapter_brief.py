"""Extract per-chapter build brief from outline.md + script.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness.core.state import VideoWorkflowState
from harness.workflow.step_indexing import (
    agent_rule_block,
    annotate_outline_dev_plan,
    brief_build_order_block,
    example_file_hints,
    format_brief_step_plan,
)


def _has_v2_kit(workspace_root: Path) -> bool:
    from harness.services.theme_kit import theme_kit_brief_block

    return theme_kit_brief_block(workspace_root) is not None

NO_AI_SLOP_BLOCK = """## Icons & anti-AI-slop (HARD FAIL — do not use emoji)

Reviewer **NO_AI_SLOP** auto-check **regex-scans** index.tsx + index.css. Emoji → instant fail → Repair round.

**Banned as icons/decor:** any Unicode emoji (🔧🔍📊📋🔒🏆🔴🟠🟡🟢🔵 …). Do not put emoji in JSX text nodes or CSS `content:`.

**Allowed symbols (not emoji):** `→` `✓` `▌` `·` `⚠`

| Visual need | Implementation |
|-------------|----------------|
| Card / tab icon | Inline `<svg viewBox="0 0 24 24">` or CSS box + `border`/`transform` |
| Status / theory dot | `<span className="dot dot-1" />` + `border-radius:50%` + `background: var(--accent)` |
| Trophy / badge | Simple SVG path or geometric CSS — never 🏆 |

Also banned: purple/pink gradients, thin decorative border cards, fake user counts/logos, **italic** (`font-style: italic`, class `serif-it`, `fontStyle: "italic"`).

**English accent copy:** use `.display-en` or `.display-en-soft` — never italic.

**Before update_registry:** run **craft_auto_check**; if emoji flagged, replace with SVG/CSS first.
"""

LAYOUT_SYSTEM_BLOCK = """## Layout Shell System (MANDATORY — locked typography + spacing)

Do **not** invent layout, font-size, or gap from scratch. Pick a shell per step:

| Shell | Root classes | Use when |
|-------|--------------|----------|
| Cover | `lx-cover-body` | Hero opener |
| Split | `lx-split-section` + `lx-split-rail` + `lx-split-module` | Index rail + rule/panel module |
| Solo | `lx-solo` + `lx-solo-panel` | Single centered demo (78% width) |
| Grid 3 | `<ListGrid>` + `<GridSlot state=…>` | List reveal — **one active slot per step** |
| Grid 2 | `lx-grid-2` | Two-column comparison |
| Quote | `lx-quote-body` + `lx-quote-text` | Closing pull-quote |
| Stack | `lx-stack` / `lx-stack-center` | Intro or transition beat |
| Terminal | `lx-terminal` + `lx-terminal-window` | Code / chat simulation |

**Typography roles** (never set raw `font-size` on primary copy):
`.lx-hero` · `.lx-title` · `.lx-subtitle` · `.lx-body` · `.lx-caption` · `.lx-kicker`

**Scene wrapper:** `SceneChrome`（**无页眉** — 禁止 brand/issue/masthead）· **List reveal:** `GridSlot` + `ListGrid`

**Chapter id on screen:** `chapter_id` 是工程路径 slug（概括本章**内容主题**），**禁止**写在 hero/kicker/正文上（不要 `Cold Open` / `Hook` / slug 大写）。画面文案只用 outline step 内容。

**Chapter id:** folder slug only — **never** show `chapter_id` or role jargon (`Cold Open`, `Hook`, `Intro`) in hero/kicker/body. Use outline step content.

**Chapter `index.css`:** only `ch-*` animation/demo classes.

Golden reference: `01-example/Example.tsx` (cover → split → grid-3 → quote).
Full catalog: `presentation/src/layouts/LAYOUT-SYSTEM.md`.
"""

THEME_KIT_BLOCK = """## Theme Kit (v2 — when `src/theme/COMPONENT-KIT.md` exists)

Prefer **`tk-*`** components from COMPONENT-KIT.md over hand-rolled card styles.

- Layout: still `lx-*` shells
- Material: `tk-card`, `tk-badge`, `tk-chip`, `tk-stat`, `tk-icon-tile`, …
- Combine: `className="lx-split-panel tk-card"`
- Motion: `mot-tk-*` + one dominant `mot-*` per step
- Do **not** invent border-radius / box-shadow on primary panels — use `tk-*`.
"""

MOTION_SYSTEM_BLOCK = """## Motion Template System (MANDATORY — read via read_chapter_context)

**Before writing index.tsx / index.css:** `read_chapter_context` returns `MOTION-SYSTEM.md` + `presets.css`.
Do **not** invent keyframes from scratch — pick presets first.

| Per step | Rule |
|----------|------|
| Dominant | **One** motion preset (`mot-hero-mask`, `mot-stamp-drop`, `mot-slot-fill`, …) |
| Accompaniment | **Optional one** (`mot-rule-grow`, `mot-caption-rise`) |
| Custom | Only if preset insufficient → `ch-*` in index.css |

**Picker (intent → motion):**
- hero opener → `mot-hero-mask` or `mot-hero-blur` on `.lx-hero`
- solo reveal → `mot-stamp-drop` + MaskReveal on image
- list-reveal → `GridSlot` active (`mot-slot-fill` / `lx-slot-drop`)
- quote close → `mot-hero-mask` + `mot-rule-grow`

**Wire MaskReveal** for text wipes; use `.mot-*` classes from `presentation/src/motion/presets.css`.
Full catalog: `presentation/src/motion/MOTION-SYSTEM.md`.

**Anti-patterns:** same fade on every step; infinite motion on hero; >2 fighting animations per step.
"""

PROJECTION_READABILITY_BLOCK = """## Projection readability (enforced by layout shells)

Design for projector / far-viewing distance. Minimum sizes on the 1920×1080 stage:

| Element | Minimum |
|---------|---------|
| Hero headline | ≥ 75px, `font-weight` ≥ 800 |
| Section title / hero numbers | ≥ 58px |
| Body / list primary copy | ≥ 28px, `font-weight` ≥ 500 |
| Auxiliary labels (kicker, caption) | ≥ 22px |
| Main content panel / card | width ≥ 55% of stage (~1056px), or full-width with stage padding |
| Type hierarchy | hero : title : body ≈ 3 : 2 : 1 |

- Primary copy: `--text` or `--text-2` only — never `--text-mute` / `--text-faint`.
- Do not default to `var(--t-body)` for primary text; use `--t-projection-body` (28px) or larger.
- Large keynote panels encouraged; avoid small decorative border cards.
- **Theme contrast**: scene bg = `--shell` / `--surface` / `--surface-2` only (no `--bg`).
  Never black-out a scene then use theme `--text` (light themes = dark ink → invisible on black).
  Borders = `--rule`; cards = `--surface-2` + `--rule`. No cinematic black-screen overrides.

**50% zoom test**: hero + each card's core message must remain readable.

### Reference scale ratios (EXAMPLES — match these proportions)

| Reference | Hero | Title | Body | Panel width |
|-----------|------|-------|------|-------------|
| hook-chapter | `--t-display-1` (124–176px) | stamp `--t-h3` | caption `--t-body` | solo frame **78%** stage |
| list-reveal | intro `--t-display-2` | slot title `--t-h2` | slot body `--t-body` | 3-col grid, `min-height: 360px` |
| 01-example (template) | `--t-display-1` cover | `--t-h1` split | `--t-projection-body` (32px) | split panel **≥ 1056px** |
"""

def _split_title_and_steps(rest: str) -> tuple[str, int | None]:
    m = re.search(r"[（(]\s*(\d+)\s*steps", rest)
    steps = int(m.group(1)) if m else None
    title = re.sub(r"\s*[（(]\s*\d+\s*steps.*$", "", rest).strip()
    return title, steps


def _parse_chapter_header(first_line: str) -> tuple[int, str, str, int | None] | None:
    """Return (index, chapter_id, title, steps) or None."""
    spec = re.match(
        r"^##\s+(\d+)\.\s+([\w-]+)\s*[—–-]\s*(.+)$",
        first_line,
        re.IGNORECASE,
    )
    if spec:
        num, cid, rest = spec.groups()
        title, steps = _split_title_and_steps(rest)
        return int(num), cid.lower().replace("-", "_"), title, steps

    legacy = re.match(
        r"^##\s+Chapter\s+(\d+)\s*(?:[—–-]|\S+)\s*(.+)$",
        first_line,
        re.IGNORECASE,
    )
    if legacy:
        num, rest = legacy.groups()
        title, steps = _split_title_and_steps(rest)
        return int(num), f"chapter_{num}", title, steps
    return None


def parse_outline_text(text: str) -> list[dict[str, Any]]:
    """Parse chapter list + section bodies from outline.md content."""
    chapters: list[dict[str, Any]] = []
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section.startswith("##"):
            continue
        first = section.split("\n", 1)[0]
        parsed_header = _parse_chapter_header(first)
        if not parsed_header:
            continue
        idx, chapter_id, title, steps = parsed_header

        chapters.append({
            "index": idx,
            "id": chapter_id,
            "title": title,
            "steps": steps,
            "section": section,
        })

    return chapters


_ARTICLE_REF_RE = re.compile(
    r"article\s+(?:"
    r"头部(?:\s+(?:metadata|code\s*block))?"
    r"|§\s*([^/\n—–-]+)"
    r"|L(\d+)"
    r")",
    re.IGNORECASE,
)


def parse_article_refs_from_outline(outline_section: str) -> list[str]:
    """Collect unique article source refs from outline 信息池 lines."""
    refs: list[str] = []
    seen: set[str] = set()
    for m in _ARTICLE_REF_RE.finditer(outline_section):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        if raw and raw not in seen:
            seen.add(raw)
            refs.append(raw)
    return refs


def _split_article_sections(article_text: str) -> tuple[str, list[tuple[str, str]]]:
    parts = re.split(r"(?=^## )", article_text, flags=re.MULTILINE)
    preamble = parts[0].strip() if parts else ""
    sections: list[tuple[str, str]] = []
    for part in parts[1:]:
        part = part.strip()
        if not part.startswith("##"):
            continue
        heading, _, body = part.partition("\n")
        sections.append((heading.lstrip("#").strip(), body.strip()))
    return preamble, sections


def _extract_article_header_part(preamble: str, ref: str) -> str:
    ref_lower = ref.lower()
    if "code block" in ref_lower or "codeblock" in ref_lower:
        m = re.search(r"```[\w]*\n(.*?)```", preamble, flags=re.DOTALL)
        return m.group(0).strip()[:2000] if m else preamble[:1500]
    if "metadata" in ref_lower:
        lines = [
            ln for ln in preamble.splitlines()
            if re.match(r"^-\s+\*\*", ln) or re.match(r"^>\s+", ln)
        ]
        return "\n".join(lines)[:2000] if lines else preamble[:1500]
    return preamble[:3500]


def _extract_article_section_by_ref(article_text: str, ref: str) -> str:
    preamble, sections = _split_article_sections(article_text)
    ref_lower = ref.lower()

    if "头部" in ref_lower or "header" in ref_lower:
        return _extract_article_header_part(preamble, ref)

    num_m = re.search(r"§\s*(\d+)", ref)
    if num_m:
        n = int(num_m.group(1))
        if n == 1:
            if preamble:
                return preamble[:4000]
            if sections:
                h, b = sections[0]
                return f"## {h}\n{b}"[:4000]
        if 1 <= n <= len(sections):
            h, b = sections[n - 1]
            return f"## {h}\n{b}"[:4000]
        return ""

    name_m = re.search(r"§\s*(.+)", ref)
    if name_m:
        name = name_m.group(1).strip().lower()
        for h, b in sections:
            if name in h.lower() or h.lower() in name:
                return f"## {h}\n{b}"[:4000]
        for part in re.split(r"(?=^### )", article_text, flags=re.MULTILINE):
            if not part.startswith("###"):
                continue
            heading = part.split("\n", 1)[0].lstrip("#").strip()
            if name in heading.lower() or heading.lower() in name:
                return part.strip()[:4000]

    line_m = re.search(r"L(\d+)", ref, re.IGNORECASE)
    if line_m:
        line_no = int(line_m.group(1))
        lines = article_text.splitlines()
        start = max(0, line_no - 16)
        end = min(len(lines), line_no + 15)
        return "\n".join(f"{i + 1}| {lines[i]}" for i in range(start, end))

    return ""


def extract_article_excerpts_for_chapter(
    article_text: str,
    outline_section: str,
    *,
    fallback_chars: int = 4000,
) -> tuple[str, list[str]]:
    """Return (combined excerpt, refs used)."""
    refs = parse_article_refs_from_outline(outline_section)
    if not refs:
        if not article_text.strip():
            return "", []
        return article_text[:fallback_chars], []

    chunks: list[str] = []
    used: list[str] = []
    for ref in refs:
        snippet = _extract_article_section_by_ref(article_text, ref)
        if snippet:
            chunks.append(f"### Source: {ref}\n{snippet}")
            used.append(ref)

    if not chunks:
        return article_text[:fallback_chars], refs
    return "\n\n".join(chunks)[:12000], used


def load_example_chapter_pattern(workspace_root: Path) -> str:
    """Bundle 01-example TSX/CSS/narrations for coding pattern reference."""
    return _load_example_chapter(workspace_root, limits={"Example.tsx": 5000, "Example.css": 2500, "narrations.ts": 1500})


def load_example_chapter_excerpt(workspace_root: Path) -> str:
    """Shorter 01-example — enough for shell + list-reveal pattern."""
    return _load_example_chapter(
        workspace_root,
        limits={"Example.tsx": 2800, "Example.css": 1200, "narrations.ts": 800},
        note="Excerpt: cover + split + grid-3 + quote. Call read_layout_catalog() for full LAYOUT-SYSTEM.md.",
    )


def _load_example_chapter(
    workspace_root: Path,
    *,
    limits: dict[str, int],
    note: str = "",
) -> str:
    example_dir = workspace_root / "presentation" / "src" / "chapters" / "01-example"
    parts = [
        "## Template reference: presentation/src/chapters/01-example/",
        "Match this coding pattern, step structure, and projection scale.",
    ]
    if note:
        parts.append(note)
    parts.append("")
    found = False
    for fname, hint in example_file_hints():
        path = example_dir / fname
        limit = limits.get(fname, 2000)
        if not path.exists():
            parts.append(f"### {fname}\nMISSING: {path}")
            continue
        found = True
        content = path.read_text(encoding="utf-8", errors="replace")
        parts += [f"### {fname} — {hint}", "```", content[:limit], "```", ""]
    if not found:
        parts.append("ERROR: 01-example not found — run scaffold first.")
    return "\n".join(parts).strip()


def load_motion_system_bundle(workspace_root: Path) -> str:
    """Full motion bundle — use read_motion_detail() when core context is not enough."""
    return _load_motion_bundle(workspace_root, spec_limit=8000, presets_limit=4500, anim_limit=3500)


def load_motion_system_summary(workspace_root: Path) -> str:
    """Condensed motion rules for first read_chapter_context."""
    return _load_motion_bundle(workspace_root, spec_limit=2400, presets_limit=1600, anim_limit=900)


def _load_motion_bundle(
    workspace_root: Path,
    *,
    spec_limit: int,
    presets_limit: int,
    anim_limit: int,
) -> str:
    motion_dir = workspace_root / "presentation" / "src" / "motion"
    parts = ["## Motion Template System (presentation/src/motion/)"]
    spec = motion_dir / "MOTION-SYSTEM.md"
    presets = motion_dir / "presets.css"
    if spec.is_file():
        parts += [
            "",
            "### MOTION-SYSTEM.md",
            spec.read_text(encoding="utf-8", errors="replace")[:spec_limit],
        ]
    else:
        parts.append("MISSING: run scaffold — MOTION-SYSTEM.md not found.")
    if presets.is_file():
        parts += [
            "",
            "### presets.css (mot-* classes — global import in App.tsx)",
            "```css",
            presets.read_text(encoding="utf-8", errors="replace")[:presets_limit],
            "```",
        ]
    else:
        parts.append("MISSING: presets.css — run scaffold.")
    anim = workspace_root / "presentation" / "src" / "styles" / "animations.css"
    if anim.is_file():
        parts += [
            "",
            "### animations.css primitives (excerpt — mask-reveal, rule-grow, keyframes)",
            "```css",
            anim.read_text(encoding="utf-8", errors="replace")[:anim_limit],
            "```",
        ]
    if spec_limit < 5000:
        parts.append("Full catalog: call read_motion_detail() before complex custom motion.")
    return "\n".join(parts).strip()


def parse_outline_chapters_from_state(state: VideoWorkflowState) -> list[dict[str, str]]:
    """Return [{id, title}] for workflow nodes."""
    path = state.get("artifact_paths", {}).get("outline.md")
    if not path or not Path(path).exists():
        return [{"id": "chapter_1", "title": "Chapter 1"}]
    parsed = parse_outline_text(Path(path).read_text(encoding="utf-8", errors="replace"))
    if not parsed:
        return [{"id": "chapter_1", "title": "Chapter 1"}]
    return [{"id": c["id"], "title": c["title"]} for c in parsed]


def get_chapter_brief(
    state: VideoWorkflowState,
    chapter_id: str,
    chapter_index: int,
) -> dict[str, Any]:
    """Build a self-contained brief so the agent need not re-read full files."""
    ws = Path(state.get("workspace_root", "."))
    paths = state.get("artifact_paths", {})

    outline_path = paths.get("outline.md")
    outline_section = ""
    expected_steps: int | None = None

    if outline_path and Path(outline_path).exists():
        chapters = parse_outline_text(Path(outline_path).read_text(encoding="utf-8", errors="replace"))
        match = next(
            (c for c in chapters if c["id"] == chapter_id or c["index"] == chapter_index),
            chapters[chapter_index - 1] if 0 < chapter_index <= len(chapters) else None,
        )
        if match:
            outline_section = match["section"]
            expected_steps = match.get("steps")

    script_excerpt = ""
    script_path = paths.get("script.md")
    if script_path and Path(script_path).exists():
        script_text = Path(script_path).read_text(encoding="utf-8", errors="replace")
        beats = [b.strip() for b in re.split(r"\n---\n", script_text) if b.strip()]
        if beats:
            total_ch = max(len(parse_outline_text(
                Path(outline_path).read_text(encoding="utf-8", errors="replace")
            )) if outline_path and Path(outline_path).exists() else 1, 1)
            per = max(len(beats) // total_ch, 1)
            start = (chapter_index - 1) * per
            chunk = beats[start : start + per + 1]
            script_excerpt = "\n---\n".join(chunk)

    article_excerpt = ""
    article_refs: list[str] = []
    article_path = paths.get("article.md")
    if article_path and Path(article_path).exists():
        article_text = Path(article_path).read_text(encoding="utf-8", errors="replace")
        article_excerpt, article_refs = extract_article_excerpts_for_chapter(
            article_text, outline_section,
        )

    example_hint = ""
    example_dir = ws / "presentation" / "src" / "chapters" / "01-example"
    example_tsx = example_dir / "Example.tsx"
    example_css = example_dir / "Example.css"
    if example_tsx.exists():
        example_hint = example_tsx.read_text(encoding="utf-8", errors="replace")[:2500]
    if example_css.exists():
        css_snippet = example_css.read_text(encoding="utf-8", errors="replace")[:1200]
        example_hint = (example_hint + "\n\n/* 01-example/Example.css (projection-friendly) */\n" + css_snippet).strip()

    return {
        "chapter_id": chapter_id,
        "chapter_index": chapter_index,
        "expected_steps": expected_steps,
        "outline_section": outline_section[:6000],
        "script_excerpt": script_excerpt[:4000],
        "article_excerpt": article_excerpt,
        "article_refs": article_refs,
        "example_hint": example_hint,
    }


def format_brief_for_prompt(
    brief: dict[str, Any],
    title: str,
    *,
    workspace_root: Path | None = None,
) -> str:
    """Render brief as markdown for the agent user prompt."""
    parts = [
        f"# Chapter Brief: {title} (`{brief['chapter_id']}`)",
        "",
    ]
    if brief.get("expected_steps"):
        parts.append(format_brief_step_plan(brief["expected_steps"]))
        parts.append("")

    parts.append(agent_rule_block())
    parts.append("")

    if brief.get("outline_section"):
        annotated = annotate_outline_dev_plan(brief["outline_section"])
        parts += [
            "## Outline section (annotated — implement each [code step k])",
            annotated,
            "",
        ]

    if brief.get("script_excerpt"):
        parts += ["## Script beats (narration source — write narrations.ts from these)", brief["script_excerpt"], ""]

    if workspace_root is not None:
        from harness.services.theme_kit import theme_kit_brief_block

        kit_brief = theme_kit_brief_block(workspace_root)
        if kit_brief:
            parts += [kit_brief, ""]

    parts += [NO_AI_SLOP_BLOCK, "", LAYOUT_SYSTEM_BLOCK, "", MOTION_SYSTEM_BLOCK, "", PROJECTION_READABILITY_BLOCK, ""]

    parts += [
        "## Source reads (MANDATORY before writing code)",
        "Call **read_chapter_context** once — it returns article excerpts + `01-example` + "
        "**LAYOUT-SYSTEM.md + MOTION-SYSTEM.md + presets.css**"
        + (" + **COMPONENT-KIT.md** (`tk-*` components)" if workspace_root and _has_v2_kit(workspace_root) else "")
        + ". "
        "Do NOT read_file article.md, 01-example, layouts/, motion/, or theme/ manually.",
        "",
    ]

    parts.append(brief_build_order_block())
    return "\n".join(parts)
