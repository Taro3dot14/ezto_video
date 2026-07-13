"""CHAPTER-CRAFT Part「完工自检」checklist — auto checks + agent attestation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal
from collections.abc import MutableMapping

from harness.workflow.chapter_validation import auto_validate_chapter
from harness.workflow.css_projection_checks import (
    collect_font_size_violations,
    find_invalid_css_var_refs,
    format_invalid_var_message,
    format_theme_token_catalog,
    hex_colors_for_theme_check,
    index_css_declares_font_size,
    load_theme_css_vars,
    strip_decorative_hex_for_theme_check,
)
from harness.services.tools.craft.craft_precheck import (
    MANUAL_PRECHECK_IDS,
    format_manual_precheck_report,
    run_manual_prechecks,
)

# Minimum px from presentation base.css projection tokens (fallback if file missing)
_DEFAULT_TOKEN_MIN_PX: dict[str, int] = {
    "--t-projection-hero": 84,
    "--t-projection-title": 64,
    "--t-projection-body": 32,
    "--t-display-1": 84,
    "--t-display-2": 64,
    "--t-h1": 72,
    "--t-h2": 48,
    "--t-h3": 36,
    "--t-body": 28,
    "--t-cue": 28,
}

CheckState = Literal["pass", "fail", "pending", "deferred"]

_CTX_KEY = "craft_review"


@dataclass(frozen=True)
class CraftReviewItem:
    id: str
    label: str
    mode: Literal["auto", "manual", "deferred"]


# Mirrors CHAPTER-CRAFT.md lines 247–273
CRAFT_REVIEW_ITEMS: tuple[CraftReviewItem, ...] = (
    CraftReviewItem("VISUAL_DEMOS", "每章至少 1~2 处 CSS / SVG / Canvas / JS 视觉演示", "auto"),
    CraftReviewItem("VARIED_ANIMATIONS", "不同 step 的主导动作不一样", "manual"),
    CraftReviewItem(
        "PROJECTION_TYPE",
        "index.css 投影可读性：hero ≥84px/800；正文 ≥32px/500；辅助 ≥24px（projection token 或显式 px）",
        "manual",
    ),
    CraftReviewItem("PANEL_WIDTH", "主卡片/面板宽 ≥ 舞台 55%（~1056px）或全宽留边", "manual"),
    CraftReviewItem("NO_MUTED_TEXT", "主文案未使用 --text-mute / --text-faint", "auto"),
    CraftReviewItem("ZOOM_READABLE", "50% 缩放仍能读出主标题 + 每张卡片核心信息", "manual"),
    CraftReviewItem("WHITESPACE_COLOR", "留白舒服、配色舒服", "manual"),
    CraftReviewItem("LIST_ONE_PER_STEP", "清单/列表逐个揭示，1 项 = 1 step", "manual"),
    CraftReviewItem("RICHER_THAN_SCRIPT", "画面信息比口播稿多（回了原文章抽细节）", "manual"),
    CraftReviewItem("NO_AI_SLOP", "无紫粉渐变 / 装饰性细边框小卡片 / emoji / 斜体 / 假数据 / 假 logo", "auto"),
    CraftReviewItem("PLACEHOLDER_NOT_FAKE", "缺的素材用 placeholder，不是 fake", "manual"),
    CraftReviewItem("THEME_TOKENS", "颜色与字体走 token；primitive class 接入主题", "auto"),
    CraftReviewItem("MISSING_ASSETS_NOTE", "交付时主动说明本章还缺哪些素材", "manual"),
    CraftReviewItem("NO_TINY_TEXT_WALL", "禁止小号字体、大量纯文字（正文 < 32px）", "auto"),
    CraftReviewItem("NO_HEADER_FOOTER", "禁止页眉页脚，仅展示关键内容", "auto"),
    CraftReviewItem("TSC_PASS", "npx tsc --noEmit 通过", "deferred"),
    CraftReviewItem("CODE_ISOLATION", "独立 CSS 类前缀；未跨章 import；未改共享文件", "auto"),
    CraftReviewItem("NARRATIONS_SYNC", "narrations.length === screen count (code steps 0..N-1)", "auto"),
    CraftReviewItem("NARRATION_SCRIPT_MATCH", "narration 与 script.md 对应段落语义一致", "manual"),
    CraftReviewItem("ANIMATION_DURATION", "每 step 动画时长 ≤ 口播时长（字数÷4≈秒）", "manual"),
)

_ITEM_BY_ID = {i.id: i for i in CRAFT_REVIEW_ITEMS}

REVIEW_BUNDLE_TODO = "REVIEW_BUNDLE"
CRAFT_TODO_IDS = frozenset(i.id for i in CRAFT_REVIEW_ITEMS if i.mode != "deferred")
REVIEWER_ONLY_TODO_IDS = CRAFT_TODO_IDS | {REVIEW_BUNDLE_TODO}

_TODO_ID_ALIASES: dict[str, str] = {
    "REVIEW_CHAPTER_BUNDLE": REVIEW_BUNDLE_TODO,
    "REVIEW_CHAPTER_BUNDLE — 读章节文件并初始化清单": REVIEW_BUNDLE_TODO,
    "REVIEW_CHAPTER_BUNDLE — 读修复后章节文件": REVIEW_BUNDLE_TODO,
    "REPAIR": "REPAIR",
    "FIX ALL REVIEWER-REPORTED FAILURES": "REPAIR",
}


def resolve_todo_item_id(raw: str, todo_items: dict[str, str]) -> str | None:
    """Map agent-facing label / alias → canonical todo id."""
    text = raw.strip()
    if not text:
        return None
    key = text.upper()
    if key in todo_items:
        return key
    alias = _TODO_ID_ALIASES.get(key) or _TODO_ID_ALIASES.get(text)
    if alias and alias in todo_items:
        return alias
    low = text.lower()
    if "review_chapter_bundle" in low or low.startswith("review_chapter_bundle"):
        if REVIEW_BUNDLE_TODO in todo_items:
            return REVIEW_BUNDLE_TODO
    if key == "REPAIR" or "reviewer-reported" in low or low == "fix all reviewer-reported failures":
        if "REPAIR" in todo_items:
            return "REPAIR"
    for tid, label in todo_items.items():
        if text == label or text == f"[复审] {label}":
            return tid
        if label in text and len(text) < len(label) + 40:
            return tid
    return None


def reviewer_todo_items(*, recheck_ids: list[str] | None = None) -> dict[str, str]:
    """Reviewer todolist — full checklist or recheck-only after Repair."""
    if recheck_ids:
        items: dict[str, str] = {
            REVIEW_BUNDLE_TODO: "review_chapter_bundle — 读修复后章节文件",
        }
        for item_id in recheck_ids:
            craft = _ITEM_BY_ID.get(item_id)
            if craft and craft.mode != "deferred":
                items[item_id] = f"[复审] {craft.label}"
        return items

    items = {
        REVIEW_BUNDLE_TODO: "review_chapter_bundle — 读章节文件并初始化清单",
    }
    for craft in CRAFT_REVIEW_ITEMS:
        if craft.mode != "deferred":
            items[craft.id] = craft.label
    return items


def craft_checklist_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    """Structured CHAPTER-CRAFT checklist for frontend display."""
    store = ctx.get(_CTX_KEY, {}).get("items", {})
    items: list[dict[str, Any]] = []
    done = 0
    required = 0
    for idx, craft in enumerate(CRAFT_REVIEW_ITEMS, 1):
        entry = store.get(craft.id, {})
        state = entry.get("state", "pending")
        if craft.mode != "deferred":
            required += 1
            if state == "pass":
                done += 1
        items.append({
            "index": idx,
            "id": craft.id,
            "label": craft.label,
            "state": state,
            "evidence": entry.get("evidence", ""),
            "fail_reason": entry.get("fail_reason", ""),
            "fix": entry.get("fix", ""),
            "mode": craft.mode,
        })
    return {
        "kind": "craft_checklist",
        "done": done,
        "total": required,
        "review_ok": bool(ctx.get("review_ok")),
        "items": items,
    }


def push_craft_checklist_event(state: Any, ctx: MutableMapping[str, Any]) -> None:
    """Push structured craft checklist to execution_trace (shared by review + repair)."""
    if not ctx.get(_CTX_KEY, {}).get("items"):
        return
    from harness.core.execution import push_event

    payload = craft_checklist_snapshot(ctx)
    push_event(state, "craft_checklist", json.dumps(payload, ensure_ascii=False))


def try_check_craft_todo_item(
    ctx: dict[str, Any],
    item_id: str,
    *,
    result: str = "pass",
    reason: str = "",
    fix: str = "",
) -> str:
    """Validate reviewer attestation. Empty string = OK to mark todo done."""
    key = item_id.upper().strip()

    if key == REVIEW_BUNDLE_TODO:
        if not _get_store(ctx).get("items"):
            return "❌ 先调用 review_chapter_bundle"
        return ""

    if key not in _ITEM_BY_ID:
        return f"❌ Unknown craft item: {item_id}"

    item = _ITEM_BY_ID[key]
    if item.mode == "deferred":
        return f"❌ {key} 在 typecheck 后自动勾选"

    entry = _get_store(ctx).get("items", {}).get(key, {})
    if not entry:
        return "❌ 先调用 review_chapter_bundle"

    verdict = result.lower().strip()
    if verdict not in ("pass", "fail"):
        return f'❌ result 必须是 "pass" 或 "fail"，收到: {result!r}'

    if key == "MISSING_ASSETS_NOTE" and verdict == "pass":
        wf = ctx.get("workflow_state")
        cid = ctx.get("chapter_id", "")
        if not isinstance(wf, dict):
            return "❌ 先调用 report_missing_assets 登记缺失素材"
        reported = (wf.get("chapter_missing_assets") or {}).get(cid)
        if not isinstance(reported, dict):
            return "❌ 先调用 report_missing_assets（无缺失则 items=[]）"

    err = attest_craft_review_item(ctx, key, result=verdict, reason=reason, fix=fix)
    return err or ""


def _get_store(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    store = ctx.setdefault(_CTX_KEY, {})
    store.setdefault("items", {})
    return store


def _set_item(
    ctx: dict[str, Any],
    item_id: str,
    *,
    state: CheckState,
    evidence: str = "",
    fail_reason: str = "",
    fix: str = "",
) -> None:
    store = _get_store(ctx)
    entry: dict[str, Any] = {
        "state": state,
        "evidence": evidence,
        "mode": _ITEM_BY_ID[item_id].mode,
    }
    if fail_reason:
        entry["fail_reason"] = fail_reason
    if fix:
        entry["fix"] = fix
    store["items"][item_id] = entry


_CRAFT_PERSIST_KEY = "chapter_craft_review"


def persist_craft_review(workflow_state: dict[str, Any], chapter_id: str, ctx: dict[str, Any]) -> None:
    """Save checklist across Reviewer rounds (keyed by chapter_id)."""
    if _CTX_KEY not in ctx:
        return
    import copy
    workflow_state.setdefault(_CRAFT_PERSIST_KEY, {})[chapter_id] = copy.deepcopy(ctx[_CTX_KEY])


def load_craft_review_into_ctx(ctx: dict[str, Any], workflow_state: dict[str, Any], chapter_id: str) -> bool:
    """Restore persisted checklist into ctx. Returns True if loaded."""
    saved = (workflow_state.get(_CRAFT_PERSIST_KEY) or {}).get(chapter_id)
    if not isinstance(saved, dict):
        return False
    import copy
    ctx[_CTX_KEY] = copy.deepcopy(saved)
    return True


def prepare_recheck_round(ctx: dict[str, Any]) -> list[str]:
    """After Repair: reset prior fail items to pending; return ids for recheck-only todo."""
    store = _get_store(ctx)
    recheck: list[str] = []
    for craft in CRAFT_REVIEW_ITEMS:
        if craft.mode == "deferred":
            continue
        entry = store.get("items", {}).get(craft.id, {})
        if entry.get("state") == "fail":
            _set_item(
                ctx,
                craft.id,
                state="pending",
                evidence="Repair 后复审",
            )
            recheck.append(craft.id)
    store["recheck_ids"] = recheck
    sync_review_ok(ctx)
    return recheck


def passed_item_ids(ctx: dict[str, Any]) -> list[str]:
    """Item ids already reviewer-pass (skipped on recheck rounds)."""
    store = _get_store(ctx).get("items", {})
    return [
        craft.id for craft in CRAFT_REVIEW_ITEMS
        if craft.mode != "deferred" and store.get(craft.id, {}).get("state") == "pass"
    ]


def failed_item_ids(ctx: dict[str, Any]) -> list[str]:
    """Craft item ids reviewer-marked fail (triggers Repair)."""
    store = _get_store(ctx).get("items", {})
    return [
        craft.id for craft in CRAFT_REVIEW_ITEMS
        if craft.mode != "deferred" and store.get(craft.id, {}).get("state") == "fail"
    ]


_AUTO_FAIL_DEFAULT_FIX: dict[str, str] = {
    "NO_AI_SLOP": "Remove emoji / italic / purple-gradient / thin-border slop from index.tsx and index.css",
    "NO_TINY_TEXT_WALL": "Raise primary body copy to ≥32px or move small text to auxiliary classes only",
    "THEME_TOKENS": "Replace hardcoded colors with theme CSS variables in index.css",
    "NARRATIONS_SYNC": "Align narrations.ts length with screen count (code steps 0..N-1)",
    "NO_HEADER_FOOTER": "Remove header/footer chrome; keep stage content only",
}


def reconcile_auto_failures(ctx: dict[str, Any]) -> list[str]:
    """Flip reviewer pass → fail when auto-check clearly failed (blocks pass-to-unblock done)."""
    store = _get_store(ctx)
    hints = store.get("auto_hints", {})
    flipped: list[str] = []
    for craft in CRAFT_REVIEW_ITEMS:
        if craft.mode != "auto":
            continue
        hint = hints.get(craft.id)
        if not hint or hint.get("pass"):
            continue
        entry = store.get("items", {}).get(craft.id, {})
        if entry.get("state") != "pass":
            continue
        evidence = str(entry.get("evidence", ""))
        if evidence and evidence != "reviewer pass" and "auto warned" not in evidence:
            continue
        auto_ev = str(hint.get("evidence", ""))
        _set_item(
            ctx,
            craft.id,
            state="fail",
            evidence=f"问题: [auto] {auto_ev}",
            fail_reason=f"[auto] {auto_ev}",
            fix=_AUTO_FAIL_DEFAULT_FIX.get(
                craft.id,
                f"Fix {craft.id} per CHAPTER-CRAFT and re-run review",
            ),
        )
        flipped.append(craft.id)
    if flipped:
        sync_review_ok(ctx)
    return flipped


def _hex_colors(text: str) -> list[str]:
    return hex_colors_for_theme_check(text)


def _index_css_declares_font_size(css: str) -> bool:
    return index_css_declares_font_size(css)


def _step_blocks(tsx: str) -> list[str]:
    parts = re.split(r"if\s*\(\s*step\s*===\s*\d+\s*\)", tsx)
    return [p for p in parts[1:] if p.strip()]


def _check_visual_demos(tsx: str, css: str) -> tuple[bool, str]:
    signals = [
        ("@keyframes", css),
        ("<svg", tsx),
        ("<canvas", tsx),
        ("MaskReveal", tsx),
        ("animation:", css + tsx),
        ("transition:", css),
    ]
    hits = [name for name, blob in signals if name.lower() in blob.lower()]
    if len(hits) >= 1:
        return True, f"found: {', '.join(hits[:4])}"
    return False, "no @keyframes / SVG / Canvas / MaskReveal / animation found"




def _check_no_muted_text(tsx: str, css: str = "", **_k: Any) -> tuple[bool, str]:
    """Flag muted tokens on primary copy — not SVG stroke/fill decorations."""
    issues: list[str] = []

    tsx_no_svg = re.sub(r"<svg[\s\S]*?</svg>", "", tsx, flags=re.I)
    tsx_no_svg = re.sub(
        r'\b(stroke|fill)\s*=\s*["\'][^"\']*(?:--text-mute|--text-faint)[^"\']*["\']',
        "",
        tsx_no_svg,
        flags=re.I,
    )
    if re.search(r"--text-mute|--text-faint", tsx_no_svg):
        issues.append("index.tsx uses --text-mute or --text-faint on copy")

    for match in re.finditer(
        r"([^{]+)\{[^}]*(?:color|fill)\s*:\s*[^;]*(?:--text-mute|--text-faint)[^}]*\}",
        css,
        flags=re.I,
    ):
        sel = match.group(1)
        if re.search(r"svg|path|circle|line|rect|decor|icon|dot|rule|stroke|grid|slot-num", sel, re.I):
            continue
        issues.append(f"muted token on copy selector {sel.strip()[:60]}")
        break

    if issues:
        return False, "; ".join(issues)
    return True, "no muted text tokens on primary copy"


# Supplementary-plane emoji only — exclude dingbats (▌ · ✓ ⚠) used in terminal/UI copy.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U0001F1E0-\U0001F1FF"
    "]",
    flags=re.UNICODE,
)


def _check_no_ai_slop(tsx: str, css: str) -> tuple[bool, str]:
    blob = tsx + css
    issues: list[str] = []
    if _EMOJI_RE.search(blob):
        issues.append("emoji detected")
    if re.search(
        r"linear-gradient\([^)]*(?:#a855f7|#ec4899|#d946ef|purple|violet|fuchsia)",
        blob,
        re.I,
    ):
        issues.append("purple/pink gradient")
    if re.search(r"border:\s*1px\s+solid[^;]{0,40}px", css) and "min-height" not in css:
        issues.append("thin decorative border card pattern")
    if re.search(r"font-style\s*:\s*italic", blob, re.I):
        issues.append("italic font-style")
    if re.search(r"""fontStyle\s*:\s*['"]italic['"]""", tsx):
        issues.append("italic fontStyle")
    if re.search(r"serif-it", blob):
        issues.append("serif-it class (italic banned)")
    if issues:
        return False, "; ".join(issues)
    return True, "no emoji / italic / purple gradient / thin-border slop"


def _css_without_terminal_hex(css: str) -> str:
    return strip_decorative_hex_for_theme_check(css)


def _check_theme_tokens(tsx: str, css: str, *, ppt: Path | None = None) -> tuple[bool, str]:
    blob = tsx + _css_without_terminal_hex(css)
    hexes = _hex_colors(blob)
    if hexes:
        return False, f"hardcoded colors: {', '.join(hexes[:6])}"
    if ppt is not None:
        known = load_theme_css_vars(ppt)
        if known:
            invalid = find_invalid_css_var_refs(css, known)
            if invalid:
                return False, f"unknown CSS variables: {format_invalid_var_message(invalid)}"
    if re.search(r"font-family:\s*[^v]", css) and "font-family: var(" not in css:
        raw = re.findall(r"font-family:\s*([^;]+)", css)
        non_var = [f for f in raw if "var(" not in f]
        if non_var:
            return False, f"hardcoded font-family: {non_var[0].strip()}"
    return True, "no hardcoded hex / font-family"


def _check_no_tiny_text(css: str, *, ppt: Path | None = None) -> tuple[bool, str]:
    violations = collect_font_size_violations(css, ppt=ppt)
    if violations:
        return False, f"font-size below floor: {'; '.join(violations[:4])}"
    if not _index_css_declares_font_size(css):
        return True, "no font-size in index.css — base.css primitives"
    return True, "body ≥32px / auxiliary ≥24px (SVG/code/window exempt)"


def _check_no_header_footer(tsx: str) -> tuple[bool, str]:
    issues: list[str] = []
    if re.search(r"page-number|页眉|页脚", tsx):
        issues.append("页眉/页脚/page-number copy on stage")

    for tag in re.findall(r"<footer\b[^>]*>", tsx, re.I):
        if re.search(r"split-foot|cover-foot|terminal-foot|lx-split-foot|lx-cover-foot", tag, re.I):
            continue
        issues.append("page-level <footer> — panel lx-split-foot inside content only")
        break

    if re.search(r"<header\b", tsx, re.I):
        issues.append("no <header> — SceneChrome is content-only (masthead removed)")

    if re.search(r"SceneChrome[^>]*(brand|issue)\s*=", tsx):
        issues.append("SceneChrome brand/issue masthead props banned")

    if re.search(
        r"className=\"[^\"]*(?:topbar|navbar|page-header|chapter-header|site-header|page-title-bar|masthead)",
        tsx,
        re.I,
    ):
        issues.append("header-like top chrome class on stage")

    if re.search(r"<nav\b", tsx, re.I):
        issues.append("nav chrome not allowed on stage")

    if issues:
        return False, "; ".join(issues)
    return True, "content-only stage — no page header/footer"


def _check_code_isolation(tsx: str, css: str, chapter_id: str) -> tuple[bool, str]:
    issues: list[str] = []
    cross = re.findall(r"from\s+['\"]\.\./chapters/([^/'\"]+)", tsx)
    cross = [c for c in cross if c != chapter_id and c != "01-example"]
    if cross:
        issues.append(f"cross-chapter import: {', '.join(cross)}")
    prefixes = set(re.findall(r"\.([a-z]{2,})-", css))
    if not prefixes:
        issues.append("no chapter-scoped CSS prefix (e.g. .cd-title)")
    if issues:
        return False, "; ".join(issues)
    return True, f"scoped prefix: {', '.join(sorted(prefixes)[:3])}"


def _check_narrations_sync(ppt: Path, chapter_id: str) -> tuple[bool, str]:
    hint = auto_validate_chapter(ppt, chapter_id)
    if hint and "narrations has" in hint:
        return False, hint.replace("⚠️ auto_validate: ", "")
    ch = ppt / "src" / "chapters" / chapter_id
    nar = ch / "narrations.ts"
    tsx = ch / "index.tsx"
    if not nar.exists() or not tsx.exists():
        return False, "narrations.ts or index.tsx missing"
    nar_count = len([ln for ln in nar.read_text(encoding="utf-8").splitlines() if ln.strip().startswith('"')])
    steps = re.findall(r"step\s*===\s*(\d+)", tsx.read_text(encoding="utf-8"))
    if not steps:
        return False, "no step === N branches in index.tsx"
    expected = max(int(s) for s in steps) + 1
    if nar_count != expected:
        return False, f"narrations={nar_count}, steps 0..{expected - 1} expected {expected} lines"
    return True, f"narrations={nar_count}, steps=0..{expected - 1}"


_AUTO_CHECKS: dict[str, Callable[..., tuple[bool, str]]] = {}


def _register_auto_checks() -> None:
    def visual(tsx: str, css: str, **_k: Any) -> tuple[bool, str]:
        return _check_visual_demos(tsx, css)

    def no_muted(tsx: str, css: str = "", **_k: Any) -> tuple[bool, str]:
        return _check_no_muted_text(tsx, css)

    def slop(tsx: str, css: str, **_k: Any) -> tuple[bool, str]:
        return _check_no_ai_slop(tsx, css)

    def tokens(tsx: str, css: str, **_k: Any) -> tuple[bool, str]:
        return _check_theme_tokens(tsx, css, ppt=_k.get("ppt"))

    def tiny(css: str, **_k: Any) -> tuple[bool, str]:
        return _check_no_tiny_text(css, ppt=_k.get("ppt"))

    def header(tsx: str, **_k: Any) -> tuple[bool, str]:
        return _check_no_header_footer(tsx)

    def isolation(tsx: str, css: str, chapter_id: str, **_k: Any) -> tuple[bool, str]:
        return _check_code_isolation(tsx, css, chapter_id)

    def narrations(ppt: Path, chapter_id: str, **_k: Any) -> tuple[bool, str]:
        return _check_narrations_sync(ppt, chapter_id)

    _AUTO_CHECKS.update({
        "VISUAL_DEMOS": visual,
        "NO_MUTED_TEXT": no_muted,
        "NO_AI_SLOP": slop,
        "THEME_TOKENS": tokens,
        "NO_TINY_TEXT_WALL": tiny,
        "NO_HEADER_FOOTER": header,
        "CODE_ISOLATION": isolation,
        "NARRATIONS_SYNC": narrations,
    })


_register_auto_checks()


def _apply_auto_passes(ctx: dict[str, Any]) -> None:
    """Pre-mark auto checklist items that passed programmatic checks."""
    store = _get_store(ctx)
    hints = store.get("auto_hints", {})
    for item in CRAFT_REVIEW_ITEMS:
        if item.mode != "auto":
            continue
        h = hints.get(item.id)
        if not h or not h.get("pass"):
            continue
        cur = store.get("items", {}).get(item.id, {})
        if cur.get("state") == "pass":
            continue
        _set_item(ctx, item.id, state="pass", evidence=f"auto: {h.get('evidence', '')}")
    sync_review_ok(ctx)


def format_reviewer_item_id_checklist(
    ctx: dict[str, Any] | None = None,
    *,
    recheck_ids: list[str] | None = None,
) -> str:
    """ITEM_ID keys for reviewer todolist_check — injected after review_chapter_bundle."""
    todos = reviewer_todo_items(recheck_ids=recheck_ids)
    store = (ctx or {}).get(_CTX_KEY, {})
    items = store.get("items", {})
    hints = store.get("auto_hints", {})
    lines = [
        "--- Reviewer ITEM_ID checklist (todolist_check keys — not Chinese labels) ---",
    ]
    for tid, label in todos.items():
        entry = items.get(tid, {})
        state = entry.get("state", "pending")
        craft = _ITEM_BY_ID.get(tid)
        if tid == REVIEW_BUNDLE_TODO:
            lines.append(f"- `{tid}` — {label}")
            continue
        if craft and craft.mode == "auto":
            if state == "pass" and str(entry.get("evidence", "")).startswith("auto:"):
                lines.append(f"- `{tid}` — {label} [auto ✅ pre-marked — fail only if disagree]")
                continue
            h = hints.get(tid)
            if h:
                mark = "✅" if h.get("pass") else "⚠️"
                lines.append(f"- `{tid}` — {label} [auto {mark}: {h.get('evidence', '')}]")
                continue
        if craft and craft.mode == "manual":
            manual_hints = store.get("manual_hints", {})
            mh = manual_hints.get(tid)
            if state == "pass" and str(entry.get("evidence", "")).startswith("precheck:"):
                lines.append(f"- `{tid}` — {label} [precheck ✅ — confirm or fail]")
                continue
            if mh and mh.get("pass") is not None:
                mark = "✅" if mh.get("pass") else "⚠️"
                lines.append(f"- `{tid}` — {label} [precheck {mark}: {mh.get('evidence', '')}]")
                continue
            if mh and mh.get("pass") is None:
                lines.append(f"- `{tid}` — {label} [hint: {mh.get('evidence', '')}]")
                continue
        mode_tag = f" [{craft.mode}]" if craft else ""
        lines.append(f"- `{tid}` — {label}{mode_tag}")
    lines.append(
        "Auto/precheck ✅ items are pre-marked — only todolist_check **remaining manual** items "
        "(VARIED_ANIMATIONS, ZOOM_READABLE, WHITESPACE_COLOR, RICHER_THAN_SCRIPT, …) "
        "or fail if you disagree with a precheck."
    )
    return "\n".join(lines)


def _apply_manual_passes(ctx: dict[str, Any]) -> None:
    """Pre-mark high-confidence manual pre-check passes."""
    store = _get_store(ctx)
    hints = store.get("manual_hints", {})
    for item_id in MANUAL_PRECHECK_IDS:
        h = hints.get(item_id)
        if not h or not h.get("pass"):
            continue
        conf = h.get("confidence", "")
        if item_id == "ANIMATION_DURATION":
            if conf not in ("high", "medium"):
                continue
        elif conf != "high":
            continue
        cur = store.get("items", {}).get(item_id, {})
        if cur.get("state") == "pass":
            continue
        _set_item(ctx, item_id, state="pass", evidence=f"precheck: {h.get('evidence', '')}")
    sync_review_ok(ctx)


def init_craft_checklist(
    ctx: MutableMapping[str, Any],
    *,
    workspace_root: Path,
    chapter_id: str,
) -> None:
    """Initialize checklist item states (pending) without running programmatic auto checks."""
    ppt = workspace_root / "presentation"
    ch = ppt / "src" / "chapters" / chapter_id
    css = (
        ch.joinpath("index.css").read_text(encoding="utf-8", errors="replace")
        if ch.joinpath("index.css").exists()
        else ""
    )
    store = _get_store(ctx)
    prev = store.get("items", {})

    for item in CRAFT_REVIEW_ITEMS:
        if item.mode == "deferred":
            if ctx.get("typecheck_ok"):
                _set_item(ctx, item.id, state="pass", evidence="typecheck passed")
            else:
                _set_item(ctx, item.id, state="deferred", evidence="勾选于 TYPECHECK 步骤")
            continue

        old = prev.get(item.id, {})
        if old.get("state") == "pass":
            _set_item(ctx, item.id, state="pass", evidence=old.get("evidence", "agent verified"))
            continue

        if item.id == "PROJECTION_TYPE" and not _index_css_declares_font_size(css):
            _set_item(
                ctx,
                item.id,
                state="pass",
                evidence="index.css 无 font-size；字号由 base.css primitive class 承担",
            )
            continue

        _set_item(ctx, item.id, state="pending", evidence="核查后 todolist_check")

    sync_review_ok(ctx)


def run_craft_auto_checks(
    ctx: dict[str, Any],
    *,
    workspace_root: Path,
    chapter_id: str,
    script_excerpt: str = "",
) -> dict[str, dict[str, Any]]:
    """Run programmatic auto + manual pre-checks; pre-mark high-confidence passes."""
    if not _get_store(ctx).get("items"):
        init_craft_checklist(ctx, workspace_root=workspace_root, chapter_id=chapter_id)

    ppt = workspace_root / "presentation"
    ch = ppt / "src" / "chapters" / chapter_id
    tsx = (
        ch.joinpath("index.tsx").read_text(encoding="utf-8", errors="replace")
        if ch.joinpath("index.tsx").exists()
        else ""
    )
    css = (
        ch.joinpath("index.css").read_text(encoding="utf-8", errors="replace")
        if ch.joinpath("index.css").exists()
        else ""
    )
    narrations_text = (
        ch.joinpath("narrations.ts").read_text(encoding="utf-8", errors="replace")
        if ch.joinpath("narrations.ts").exists()
        else ""
    )
    hints: dict[str, dict[str, Any]] = {}

    for item in CRAFT_REVIEW_ITEMS:
        if item.mode != "auto":
            continue
        checker = _AUTO_CHECKS.get(item.id)
        if not checker:
            hints[item.id] = {"pass": False, "evidence": "no auto checker"}
            continue
        ok, evidence = checker(tsx=tsx, css=css, ppt=ppt, chapter_id=chapter_id)
        hints[item.id] = {"pass": ok, "evidence": evidence}

    store = _get_store(ctx)
    store["auto_hints"] = hints
    store["manual_hints"] = run_manual_prechecks(
        tsx=tsx,
        css=css,
        narrations_text=narrations_text,
        script_excerpt=script_excerpt,
    )
    _apply_auto_passes(ctx)
    _apply_manual_passes(ctx)
    return hints


def format_craft_auto_check_report(ctx: dict[str, Any]) -> str:
    """Format advisory auto-check results (non-blocking)."""
    hints = _get_store(ctx).get("auto_hints", {})
    lines = ["--- Craft auto-check（仅供参考，不阻塞 todolist_check）---"]
    if not hints:
        lines.append("尚未运行 — 调用 craft_auto_check")
        return "\n".join(lines)

    for item in CRAFT_REVIEW_ITEMS:
        if item.mode != "auto":
            continue
        h = hints.get(item.id)
        if not h:
            lines.append(f"☐ {item.id}: 未检测")
            continue
        mark = "✅" if h.get("pass") else "⚠️"
        ev = h.get("evidence", "")
        lines.append(f"{mark} {item.id}: {item.label}" + (f" — {ev}" if ev else ""))
    return "\n".join(lines)


def craft_auto_check(
    ctx: dict[str, Any],
    *,
    workspace_root: Path,
    chapter_id: str,
) -> str:
    """Tool entry: run programmatic checks and return advisory report."""
    run_craft_auto_checks(ctx, workspace_root=workspace_root, chapter_id=chapter_id)
    return format_craft_auto_check_report(ctx) + "\n\n" + format_craft_checklist(ctx)


def sync_review_ok(ctx: dict[str, Any]) -> None:
    """Set ctx['review_ok'] when all non-deferred craft items are reviewer-pass."""
    store = _get_store(ctx)
    items = store.get("items", {})
    for item in CRAFT_REVIEW_ITEMS:
        if item.mode == "deferred":
            continue
        entry = items.get(item.id, {})
        if entry.get("state") != "pass":
            ctx["review_ok"] = False
            return
    ctx["review_ok"] = True


def format_attest_ok_message(ctx: dict[str, Any], item_id: str) -> str:
    """Short confirmation after a successful reviewer attestation."""
    key = item_id.upper().strip()
    item = _ITEM_BY_ID[key]
    entry = _get_store(ctx).get("items", {}).get(key, {})
    state = entry.get("state", "pending")
    if state == "pass":
        return f"✅ {key}: 已记为通过 — {item.label}"
    if state == "fail":
        return f"❌ {key}: 已记为未通过 → Repair 将按 fix 修复"
    return f"✅ {key}: {item.label}"


def attest_craft_review_item(
    ctx: dict[str, Any],
    item_id: str,
    *,
    result: Literal["pass", "fail"],
    reason: str = "",
    fix: str = "",
) -> str | None:
    """Reviewer attests pass or fail. Returns None on success, error message on validation failure."""
    key = item_id.upper().strip()
    if key not in _ITEM_BY_ID:
        valid = ", ".join(i.id for i in CRAFT_REVIEW_ITEMS)
        return f"❌ Unknown item: {item_id}. Valid: {valid}"

    item = _ITEM_BY_ID[key]
    if item.mode == "deferred":
        return f"❌ {key} is checked automatically after typecheck — run typecheck first"

    if result == "fail":
        if not reason.strip():
            return f"❌ {key}: result=fail 时必须提供 reason（问题描述 + 文件/step）"
        if not fix.strip():
            return f"❌ {key}: result=fail 时必须提供 fix（具体修复方案，供 Repair 执行）"

    store = _get_store(ctx)
    if key == "MISSING_ASSETS_NOTE" and result == "pass":
        wf = ctx.get("workflow_state")
        cid = ctx.get("chapter_id", "")
        if not isinstance(wf, dict):
            return "❌ 先调用 report_missing_assets 登记缺失素材"
        reported = (wf.get("chapter_missing_assets") or {}).get(cid)
        if not isinstance(reported, dict):
            return "❌ 先调用 report_missing_assets（无缺失则 items=[]）"

    if result == "pass":
        hint = store.get("auto_hints", {}).get(key)
        if hint and not hint.get("pass") and not reason.strip():
            return (
                f"❌ {key}: auto-check 未通过（{hint.get('evidence', '')}）。"
                "请 result=\"fail\" 并填写 reason+fix；若坚持通过，须在 reason 中说明误报依据"
            )
        if reason.strip():
            evidence = reason.strip()
        elif hint and not hint.get("pass"):
            evidence = f"reviewer pass (auto warned: {hint.get('evidence', '')})"
        else:
            evidence = "reviewer pass"
        _set_item(ctx, key, state="pass", evidence=evidence)
    else:
        reason = reason.strip()
        fix = fix.strip()
        evidence = f"问题: {reason}\n建议: {fix}"
        _set_item(ctx, key, state="fail", evidence=evidence, fail_reason=reason, fix=fix)

    sync_review_ok(ctx)
    return None


def mark_craft_review_check(ctx: dict[str, Any], item_id: str) -> str:
    """Backward-compatible: attest pass."""
    err = attest_craft_review_item(ctx, item_id, result="pass")
    if err:
        return err
    return format_attest_ok_message(ctx, item_id)


def mark_craft_review_checks(ctx: dict[str, Any], items: str | list[str]) -> str:
    names = [items] if isinstance(items, str) else list(items)
    return "\n".join(mark_craft_review_check(ctx, n) for n in names)


def on_typecheck_pass(ctx: dict[str, Any]) -> None:
    _set_item(ctx, "TSC_PASS", state="pass", evidence="npx tsc --noEmit passed")


def format_craft_checklist(ctx: dict[str, Any]) -> str:
    store = _get_store(ctx)
    items = store.get("items", {})
    lines = ["--- CHAPTER-CRAFT 完工自检 ---"]
    done = 0
    required = sum(1 for i in CRAFT_REVIEW_ITEMS if i.mode != "deferred")

    for idx, item in enumerate(CRAFT_REVIEW_ITEMS, 1):
        entry = items.get(item.id, {})
        state = entry.get("state", "pending")
        evidence = entry.get("evidence", "")

        if state == "pass":
            mark = "✅"
            done += 1 if item.mode != "deferred" else 0
        elif state == "fail":
            mark = "❌"
        elif state == "deferred":
            mark = "⏳"
        else:
            mark = "☐"

        suffix = f" — {evidence}" if evidence and state not in ("pending",) else ""
        if state == "pending":
            suffix = " — 核查后 todolist_check(result=pass|fail)"
            if item.mode == "auto":
                h = store.get("auto_hints", {}).get(item.id)
                if h:
                    hint_mark = "✅" if h.get("pass") else "⚠️"
                    suffix += f" [auto: {hint_mark} {h.get('evidence', '')}]"
        lines.append(f"{mark} {idx:02d}. {item.label}{suffix}")

    failed = sum(
        1 for i in CRAFT_REVIEW_ITEMS
        if i.mode != "deferred" and items.get(i.id, {}).get("state") == "fail"
    )
    lines.append(f"进度: {done}/{required} 通过" + (f"，{failed} 项 ❌ 待 Repair" if failed else ""))
    if ctx.get("review_ok"):
        lines.append("✅ 自检全部通过 — 全部 todolist_check 后可 done()")
    elif failed:
        lines.append("❌ 有打叉项 — 全部核查完后 done()，Repair 将修复打叉项")
    else:
        lines.append("☐ 尚有未核查项 — 逐项 todolist_check(result=pass|fail)")
    return "\n".join(lines)


def format_review_failure_report(
    ctx: dict[str, Any],
    *,
    chapter_id: str,
    agent_summary: str = "",
    workspace_root: Path | None = None,
) -> str:
    """Structured failure report for Repair agent."""
    snap = craft_checklist_snapshot(ctx)
    lines = [
        "## Reviewer failure report (MUST fix all)",
        "",
        f"**Chapter folder id:** `{chapter_id}`",
        "**禁止**使用 `chapter_1` — 所有路径必须是 "
        f"`presentation/src/chapters/{chapter_id}/`",
        "",
    ]
    if workspace_root is not None:
        catalog = format_theme_token_catalog(workspace_root / "presentation")
        if catalog:
            lines += [catalog, ""]
    hints = _get_store(ctx).get("auto_hints", {})
    failed_items = [i for i in snap["items"] if i["state"] == "fail"]
    pending = [
        i for i in snap["items"]
        if i["state"] == "pending" and i["mode"] != "deferred"
    ]
    if failed_items:
        lines.append("### Reviewer failures (MUST fix)")
        for item in failed_items:
            lines.append(f"- **{item['id']}**: {item['label']}")
            fr = item.get("fail_reason") or item.get("evidence") or ""
            fx = item.get("fix") or ""
            if fr:
                lines.append(f"  - 问题: {fr}")
            if fx:
                lines.append(f"  - 建议: {fx}")
        lines.append("")
    warned = [
        (item_id, h)
        for item_id, h in hints.items()
        if not h.get("pass")
        and _get_store(ctx).get("items", {}).get(item_id, {}).get("state") != "fail"
    ]
    if warned:
        lines.append("### Auto-check warnings (advisory, not yet reviewer-failed)")
        for item_id, h in warned:
            craft = _ITEM_BY_ID.get(item_id)
            label = craft.label if craft else item_id
            lines.append(f"- **{item_id}**: {label}")
            if h.get("evidence"):
                lines.append(f"  - evidence: {h['evidence']}")
        lines.append("")
    if pending:
        lines.append("### Unchecked manual items")
        for item in pending[:8]:
            lines.append(f"- {item['id']}: {item['label']}")
        lines.append("")
    lines.append(format_craft_checklist(ctx))
    if agent_summary.strip():
        lines += ["", "### Reviewer notes", agent_summary.strip()[:4000]]
    lines += [
        "",
        "### Repair instructions",
        "1. Use **only** theme tokens listed above (read `presentation/src/styles/tokens.css` if unsure)",
        "2. Fix every failure in ### Reviewer failures — follow 建议 exactly",
        "3. Call `done()` when REPAIR todo complete",
    ]
    return "\n".join(lines)
