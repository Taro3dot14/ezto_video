"""Step index contract — single source of truth for chapter build agents.

First principles (runtime, immutable):
- App passes `step: number` into each chapter component (0-based).
- One full-screen layout per step: `if (step === k) return <Scene />`.
- `narrations[i]` is spoken on `step === i`.
- `narrations.length` === number of screens === max(code step) + 1.

Authoring (outline.md only):
- Humans label steps 1..N in the dev-plan. Never use 1..N in index.tsx.
"""

from __future__ import annotations

import re

# ── Namespace conversion (outline ↔ code) ──────────────────────────────────


def outline_step_to_code(outline_step: int) -> int:
    """Outline dev-plan label (1-based) → runtime/code index (0-based)."""
    return outline_step - 1


def code_step_to_outline(code_step: int) -> int:
    """Runtime/code index → outline dev-plan label."""
    return code_step + 1


def code_step_range(step_count: int) -> range:
    """Valid code steps for N screens: 0 .. N-1."""
    if step_count <= 0:
        return range(0)
    return range(0, step_count)


# ── Agent-facing copy (import everywhere — do not rephrase) ────────────────


def agent_invariant_line() -> str:
    return (
        "One invariant: **N outline steps → N narrations → code `step` 0..N-1** "
        "(outline step K → `step === K-1`, `narrations[K-1]`)."
    )


def agent_rule_block() -> str:
    """Full rule for chapter brief / read_chapter_context."""
    return "\n".join([
        "## Steps: outline labels vs code (do not mix namespaces)",
        "",
        "| Outline dev-plan | Code `index.tsx` | `narrations.ts` |",
        "|------------------|------------------|-------------------|",
        "| step 1 | `if (step === 0)` | `narrations[0]` |",
        "| step 2 | `if (step === 1)` | `narrations[1]` |",
        "| step N | `if (step === N - 1)` | `narrations[N - 1]` |",
        "",
        agent_invariant_line(),
        "",
        "**Wrong:** 5 outline steps + 5 narrations but `step === 1` … `step === 5` "
        "(needs 6 narrations for steps 0..5).",
        "",
        "Silent beats: use `\"\"` in `narrations.ts`; still add `if (step === k)`.",
    ])


def format_brief_step_plan(step_count: int) -> str:
    """Concrete plan when outline declares N steps."""
    last = step_count - 1
    return (
        f"**{step_count} screens** for this chapter: "
        f"code `step === 0` … `step === {last}`, "
        f"`write_narrations` with **{step_count}** strings."
    )


def annotate_outline_dev_plan(section: str) -> str:
    """Inline code-step labels on outline dev-plan bullets so agents need not convert."""
    def _repl(m: re.Match[str]) -> str:
        outline_n = int(m.group(1))
        code_n = outline_step_to_code(outline_n)
        tail = m.group(2) or ""
        return f"- **[code step {code_n}]** outline step {outline_n}{tail}"

    return re.sub(
        r"^- step (\d+)((?:\s*\([^)]*\))?[^\n]*)",
        _repl,
        section,
        flags=re.MULTILINE | re.IGNORECASE,
    )


def todo_narrations_label() -> str:
    return "write_narrations — one string per code step (narrations[i] ↔ step === i)"


def todo_index_tsx_label() -> str:
    return "index.tsx — one full-screen branch per code step 0..N-1 (N = narrations.length)"


def write_narrations_tool_description() -> str:
    return (
        "Write narrations.ts. Call FIRST. "
        "Pass one string per **code step** (0-based): "
        "lines.length must equal the number of `if (step === k)` screens in index.tsx. "
        "Inline double quotes in narration text are auto-converted to 「」."
    )


def narrations_mismatch_hint(*, nar_count: int, max_code_step: int) -> str | None:
    """Human-readable hint when narrations and index.tsx step branches disagree."""
    expected = max_code_step + 1
    if nar_count == expected:
        return None
    hint = (
        f"narrations has {nar_count} lines but index.tsx uses steps 0..{max_code_step} "
        f"({expected} expected)."
    )
    if nar_count == max_code_step and max_code_step >= 1:
        hint += (
            f" Likely used outline numbering in code — use "
            f"`step === 0`..`step === {nar_count - 1}`, not `step === 1`..`step === {nar_count}`."
        )
    return hint


def brief_build_order_block() -> str:
    """Strict build sequence — same wording in brief and read_chapter_context."""
    return "\n".join([
        "## Build order (strict)",
        "1. **`read_chapter_context`** — article + 01-example + LAYOUT-SYSTEM + **MOTION-SYSTEM + presets.css**",
        "2. `write_narrations` — one string per **code step** (`narrations.length` = screen count)",
        "3. `write_file` index.tsx — SceneChrome + one shell per step + **one mot-* dominant motion**",
        "   - Typography: `.lx-hero` / `.lx-title` / `.lx-body` — never raw font-size on copy",
        "   - Motion: MaskReveal + `.mot-*` from presets.css; do not invent keyframes before reading motion bundle",
        "   - Icons: inline SVG or CSS only — never emoji",
        "4. `write_file` index.css — `ch-*` animation overrides only (layout + mot-* are global)",
        "5. `craft_auto_check` — fix emoji/slop before registry if flagged",
        "6. `update_registry` → `done` (reviewer runs craft checks)",
        "",
    ])


def parse_max_code_step(tsx_text: str) -> int | None:
    """Largest `step === N` in index.tsx, or None if no branches."""
    matches = re.findall(r"step\s*===\s*(\d+)", tsx_text)
    if not matches:
        return None
    return max(int(s) for s in matches)


def count_narration_lines(nar_text: str) -> int:
    return len([
        ln for ln in nar_text.splitlines()
        if ln.strip().startswith('"') or ln.strip().startswith("'")
    ])


def example_file_hints() -> tuple[tuple[str, str], ...]:
    """(filename, one-line hint) for 01-example bundle."""
    return (
        ("Example.tsx", "SceneChrome + lx-* layout shells per step"),
        ("Example.css", "Chapter-specific only (`ch-*` or accent overrides)"),
        ("narrations.ts", "narrations.length === screen count; narrations[i] ↔ step === i"),
    )
