"""Deterministic pre-checks for CHAPTER-CRAFT manual reviewer items."""

from __future__ import annotations

import re
from typing import Any

STAGE_WIDTH_PX = 1920
PANEL_MIN_PX = int(STAGE_WIDTH_PX * 0.55)  # ~1056px

# Manual items safe to pre-mark pass when checks succeed with high confidence.
MANUAL_PRECHECK_IDS = frozenset({
    "LIST_ONE_PER_STEP",
    "PANEL_WIDTH",
    "ANIMATION_DURATION",
})


def _step_blocks(tsx: str) -> list[tuple[int, str]]:
    parts = re.split(r"if\s*\(\s*step\s*===\s*(\d+)\s*\)", tsx)
    blocks: list[tuple[int, str]] = []
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        try:
            step_n = int(parts[i])
        except ValueError:
            continue
        blocks.append((step_n, parts[i + 1]))
    return blocks


def _parse_narration_lines(narrations_text: str) -> list[str]:
    lines: list[str] = []
    for raw in narrations_text.splitlines():
        s = raw.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r'^["\'](.*)["\'],?\s*$', s)
        if m:
            lines.append(m.group(1))
    return lines


def _narration_seconds(text: str) -> float:
    """Rough TTS duration: ~4 chars/sec for CJK-heavy copy."""
    stripped = re.sub(r"\s+", "", text)
    if not stripped:
        return 0.5
    return max(0.5, len(stripped) / 4.0)


def _parse_duration_seconds(value: str) -> float | None:
    value = value.strip().lower()
    m = re.match(r"([\d.]+)\s*(ms|s)?", value)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2) or "s"
    return num / 1000.0 if unit == "ms" else num


def _max_animation_seconds(blob: str) -> float:
    best = 0.0
    for m in re.finditer(
        r"(?:animation(?:-duration)?|transition-duration)\s*:\s*([^;}{]+)",
        blob,
        re.I,
    ):
        chunk = m.group(1)
        for part in chunk.split(","):
            part = part.strip().split()[-1] if part.strip() else ""
            sec = _parse_duration_seconds(part)
            if sec is not None:
                best = max(best, sec)
    for m in re.finditer(r"duration\s*=\s*\{?\s*(\d+)", blob):
        best = max(best, int(m.group(1)) / 1000.0)
    return best


def _panel_width_ok(css: str) -> tuple[bool, str]:
    if not css.strip():
        return True, "no chapter CSS — lx-* shells provide default panel widths"

    widths: list[tuple[str, float]] = []
    for m in re.finditer(
        r"([^{]+)\{([^}]+)\}",
        css,
        re.I,
    ):
        sel = m.group(1).strip()
        body = m.group(2)
        if re.search(r"kicker|caption|dot|num|rule|svg|icon|terminal-dot", sel, re.I):
            continue
        if not re.search(r"panel|card|solo|slot|hero|body|scene|module|grid|split|ch-", sel, re.I):
            continue
        for wm in re.finditer(r"(?:width|min-width)\s*:\s*([^;]+)", body, re.I):
            raw = wm.group(1).strip()
            if raw.endswith("%"):
                pct = float(raw[:-1])
                widths.append((sel[:40], STAGE_WIDTH_PX * pct / 100.0))
            else:
                px_m = re.search(r"([\d.]+)\s*px", raw)
                if px_m:
                    widths.append((sel[:40], float(px_m.group(1))))

    if not widths:
        return True, "no explicit panel widths — layout shells (lx-*) carry ≥55% defaults"

    max_px = max(w for _, w in widths)
    if max_px >= PANEL_MIN_PX:
        return True, f"max panel width ≈{int(max_px)}px (≥{PANEL_MIN_PX}px floor)"
    best_sel, best = max(widths, key=lambda x: x[1])
    return False, (
        f"widest panel `{best_sel}` ≈{int(best)}px — need ≥{PANEL_MIN_PX}px (~55% stage) "
        "or full-width shell with side padding"
    )


def _list_one_per_step_ok(tsx: str) -> tuple[bool, str]:
    uses_grid = "GridSlot" in tsx or "ListGrid" in tsx
    if not uses_grid:
        return True, "no ListGrid/GridSlot — list-reveal rule N/A"

    violations: list[str] = []
    for step_n, block in _step_blocks(tsx):
        active = len(re.findall(r'state\s*=\s*["\']active["\']', block))
        active += block.count("lx-slot-active")
        if active > 1:
            violations.append(f"step {step_n}: {active} active list slots")

    if violations:
        return False, "; ".join(violations[:4])
    return True, "GridSlot/list steps expose ≤1 active item each"


def _animation_duration_ok(tsx: str, css: str, narrations_text: str) -> tuple[bool, str]:
    narrations = _parse_narration_lines(narrations_text)
    if not narrations:
        return True, "no narrations to compare"

    blocks = _step_blocks(tsx)
    if not blocks:
        return True, "no step branches — skip duration compare"

    issues: list[str] = []
    for step_n, block in blocks:
        if step_n >= len(narrations):
            continue
        narr_sec = _narration_seconds(narrations[step_n])
        anim_sec = _max_animation_seconds(block + css)
        if anim_sec <= 0:
            continue
        if anim_sec > narr_sec * 1.35 + 0.3:
            issues.append(
                f"step {step_n}: anim≈{anim_sec:.1f}s > narr≈{narr_sec:.1f}s"
            )

    if issues:
        return False, "; ".join(issues[:4])
    return True, "step animations within narration duration budget"


def _script_match_hint(narrations_text: str, script_excerpt: str) -> dict[str, Any]:
    """Advisory only — never auto-pass."""
    narrations = _parse_narration_lines(narrations_text)
    if not script_excerpt.strip() or not narrations:
        return {"pass": None, "evidence": "no script excerpt — verify manually", "confidence": "none"}

    script_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", script_excerpt))
    if not script_words:
        return {"pass": None, "evidence": "script excerpt empty — verify manually", "confidence": "none"}

    hits = 0
    for line in narrations:
        line_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", line))
        if line_words & script_words:
            hits += 1
    ratio = hits / len(narrations) if narrations else 0
    if ratio >= 0.6:
        return {
            "pass": None,
            "evidence": f"{hits}/{len(narrations)} narrations share script vocabulary — likely aligned",
            "confidence": "low",
        }
    return {
        "pass": None,
        "evidence": f"only {hits}/{len(narrations)} narrations overlap script — check semantic match",
        "confidence": "low",
    }


def run_manual_prechecks(
    *,
    tsx: str,
    css: str,
    narrations_text: str,
    script_excerpt: str = "",
) -> dict[str, dict[str, Any]]:
    """Return manual item hints: pass/fail + confidence (high → auto pre-mark pass)."""
    hints: dict[str, dict[str, Any]] = {}

    ok, ev = _list_one_per_step_ok(tsx)
    hints["LIST_ONE_PER_STEP"] = {"pass": ok, "evidence": ev, "confidence": "high"}

    ok, ev = _panel_width_ok(css)
    hints["PANEL_WIDTH"] = {"pass": ok, "evidence": ev, "confidence": "high"}

    ok, ev = _animation_duration_ok(tsx, css, narrations_text)
    hints["ANIMATION_DURATION"] = {
        "pass": ok,
        "evidence": ev,
        "confidence": "medium" if ok else "high",
    }

    hints["NARRATION_SCRIPT_MATCH"] = _script_match_hint(narrations_text, script_excerpt)
    return hints


def format_manual_precheck_report(hints: dict[str, dict[str, Any]]) -> str:
    lines = ["--- Manual pre-checks (deterministic) ---"]
    if not hints:
        lines.append("(not run)")
        return "\n".join(lines)

    for item_id in (
        "LIST_ONE_PER_STEP",
        "PANEL_WIDTH",
        "ANIMATION_DURATION",
        "NARRATION_SCRIPT_MATCH",
    ):
        h = hints.get(item_id)
        if not h:
            continue
        passed = h.get("pass")
        if passed is None:
            mark = "ℹ️"
        else:
            mark = "✅" if passed else "⚠️"
        conf = h.get("confidence", "")
        conf_tag = f" [{conf}]" if conf else ""
        lines.append(f"{mark} {item_id}{conf_tag}: {h.get('evidence', '')}")
    lines.append(
        "High-confidence ✅ pre-marked — Reviewer confirms manual-only items "
        "(VARIED_ANIMATIONS, ZOOM_READABLE, WHITESPACE_COLOR, …)."
    )
    return "\n".join(lines)
