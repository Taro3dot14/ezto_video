"""Helper functions shared across graph nodes."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from configs import settings
from backend.core.logger import logger

from ..core.state import VideoWorkflowState
from .guards import ensure_artifact_parent

_PPT_DIR = "presentation"

_REPAIR_REFUSAL_MARKERS = (
    "请提供",
    "请粘贴",
    "没有需要",
    "current script:",
    "部分为空",
    "no script",
    "script was not provided",
    "script content is empty",
    "缺少脚本",
    "我已完整理解",
    "贴过来后",
)


def think(log: list | None, type_: str, content: str) -> list[dict]:
    """Append a thinking event to an in-progress list. Pass None to start fresh."""
    if log is None:
        log = []
    log.append({"type": type_, "content": content, "ts": time.time()})
    return log


def extract_repair_text(raw: str | None) -> str:
    """Strip fences / preamble from an LLM repair response."""
    if not raw:
        return ""
    text = raw.strip()
    fenced = re.search(r"```(?:markdown|md|text)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


def looks_like_repair_refusal(text: str) -> bool:
    """Detect meta replies ('please provide script') mistaken for repaired content."""
    if not text:
        return True
    lower = text.lower()
    if any(marker in lower for marker in _REPAIR_REFUSAL_MARKERS):
        return len(text) < 1200
    return False


def safe_repair_write(path: str | Path, original: str, repaired: str) -> tuple[str, bool]:
    """Write repaired artifact only if non-empty and plausibly complete."""
    cleaned = extract_repair_text(repaired)
    original = original.strip()
    if not cleaned or looks_like_repair_refusal(cleaned):
        return original, False
    orig_len = len(original)
    min_len = max(200, int(orig_len * 0.25)) if orig_len else 200
    if len(cleaned) < min_len:
        return original, False
    target = ensure_artifact_parent(path)
    target.write_text(cleaned, encoding="utf-8")
    return cleaned, True


def clean_tsx_content(raw: str) -> str:
    """Strip narrations / extra content from the start of an LLM-generated TSX file."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("/*"):
            continue
        if s.startswith("export const") and "narrat" in s.lower():
            continue
        if s.startswith("import ") or s.startswith("export "):
            start = i
            break
        if (
            s.startswith("function ")
            or s.startswith("const ")
            or s == "{"
            or s.startswith("<")
        ):
            start = i
            break
    return "\n".join(lines[start:]).strip()


def parse_outline_chapters(state: VideoWorkflowState) -> list[dict[str, str]]:
    """Parse chapter list from outline.md."""
    from harness.workflow.chapter_brief import parse_outline_chapters_from_state
    return parse_outline_chapters_from_state(state)


def get_max_repair_retries(target: str) -> int:
    """Max validate-repair loops for script.md or outline.md (from settings)."""
    from configs import settings
    if target == "outline.md":
        return settings.content_outline_max_repair_retries
    return settings.content_script_max_repair_retries


def get_repair_count(state: VideoWorkflowState, target: str) -> int:
    """Count how many times a target has been repaired."""
    return sum(1 for r in state.get("repair_history", []) if r.get("target") == target)


def update_chapter_meta(state: VideoWorkflowState, new_chapter_ids: list[str]) -> None:
    """Write chapter-meta.ts — marks chapters updated since last user approval."""
    ws = state.get("workspace_root", ".")
    meta_file = Path(ws) / _PPT_DIR / "src" / "registry" / "chapter-meta.ts"
    ids_json = json.dumps(new_chapter_ids, ensure_ascii=False)
    content = (
        "/** Auto-generated — do not edit. Chapters updated since last approval. */\n"
        f"export const NEW_CHAPTER_IDS: readonly string[] = {ids_json};\n"
    )
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(content, encoding="utf-8")


def list_built_chapters(state: VideoWorkflowState) -> list[dict[str, str]]:
    """Return outline chapters that have index.tsx + narrations.ts on disk."""
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / _PPT_DIR
    built: list[dict[str, str]] = []
    for ch in parse_outline_chapters(state):
        c_tsx = ppt / "src" / "chapters" / ch["id"] / "index.tsx"
        c_nar = ppt / "src" / "chapters" / ch["id"] / "narrations.ts"
        if c_tsx.exists() and c_nar.exists():
            built.append(dict(ch))
    return built


def count_built_chapters(state: VideoWorkflowState) -> int:
    return len(list_built_chapters(state))


def count_narrations_in_file(nar_path: Path) -> int:
    """Count per-step narration strings in narrations.ts."""
    if not nar_path.is_file():
        return 0
    text = nar_path.read_text(encoding="utf-8", errors="replace")
    return len([
        ln for ln in text.splitlines()
        if ln.strip().startswith('"') or ln.strip().startswith("'")
    ])


def built_chapter_step_counts(state: VideoWorkflowState) -> list[dict[str, int | str]]:
    """Per built chapter: {id, steps} from narrations.ts line count."""
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / _PPT_DIR
    rows: list[dict[str, int | str]] = []
    for ch in list_built_chapters(state):
        nar = ppt / "src" / "chapters" / ch["id"] / "narrations.ts"
        rows.append({"id": ch["id"], "steps": count_narrations_in_file(nar)})
    return rows


def count_built_steps(state: VideoWorkflowState) -> int:
    """Total presentation steps = sum of narrations.length across built chapters."""
    return sum(r["steps"] for r in built_chapter_step_counts(state))


def apply_chapter_checkpoint_approval(
    state: VideoWorkflowState,
    checkpoint_key: str,
    chapter_ids: list[str],
) -> dict[str, Any]:
    """After a chapter checkpoint resume: record approval and clear new markers."""
    conf = state.get("user_confirmations", {}).get(checkpoint_key, {})
    if not (isinstance(conf, dict) and conf.get("approved") is True):
        return {}
    approved = list(state.get("approved_chapter_ids") or [])
    for cid in chapter_ids:
        if cid not in approved:
            approved.append(cid)
    update_chapter_meta(state, [])
    return {"approved_chapter_ids": approved}


def update_chapter_registry(state: VideoWorkflowState, chapters: list[dict]) -> None:
    """Generate chapters.ts from the template file."""
    ws = state.get("workspace_root", ".")
    reg_file = Path(ws) / _PPT_DIR / "src" / "registry" / "chapters.ts"

    import_lines = "\n".join(
        f"import {ch['id']} from '../chapters/{ch['id']}';" for ch in chapters
    ) + "\n" + "\n".join(
        f"import {{ narrations as {ch['id']}Narrations }} from '../chapters/{ch['id']}/narrations';"
        for ch in chapters
    )
    entry_lines = "\n".join(
        f"  {{\n"
        f"    id: '{ch['id']}',\n"
        f"    title: '{ch['title']}',\n"
        f"    narrations: {ch['id']}Narrations,\n"
        f"    Component: {ch['id']},\n"
        f"  }},"
        for ch in chapters
    )

    template_path = Path(settings.templates_dir) / "registry" / "chapters.template.ts"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        content = content.replace("// __IMPORTS__", import_lines)
        content = content.replace("// __ENTRIES__", entry_lines)
    else:
        content = (
            "import type { ChapterDef } from './types';\n"
            f"{import_lines}\n"
            "\n"
            "export const CHAPTERS: ChapterDef[] = [\n"
            f"{entry_lines}\n"
            "];\n"
        )

    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(content, encoding="utf-8")


def sync_built_chapter_registry(
    state: VideoWorkflowState,
    chapter_id: str,
    title: str,
) -> str:
    """Register all built chapters (index.tsx + narrations.ts present) in chapters.ts."""
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / _PPT_DIR
    chapters = parse_outline_chapters(state)
    built: list[dict[str, str]] = []
    for ch in chapters:
        c_tsx = ppt / "src" / "chapters" / ch["id"] / "index.tsx"
        c_nar = ppt / "src" / "chapters" / ch["id"] / "narrations.ts"
        if c_tsx.exists() and c_nar.exists():
            entry = dict(ch)
            if entry["id"] == chapter_id:
                entry["title"] = title
            built.append(entry)

    if not any(c["id"] == chapter_id for c in built):
        built.append({"id": chapter_id, "title": title})

    update_chapter_registry(state, built)

    approved_ids = set(state.get("approved_chapter_ids") or [])
    new_ids = [c["id"] for c in built if c["id"] not in approved_ids]
    update_chapter_meta(state, new_ids)

    ids = ", ".join(c["id"] for c in built)
    new_hint = f" (new: {', '.join(new_ids)})" if new_ids else ""
    return f"✅ Registry updated ({len(built)} chapters): {ids}{new_hint}"


_PREVIEW_RUNTIME_REL_PATHS = (
    "hooks/useStepper.ts",
    "App.tsx",
)


def sync_preview_runtime_files(state: VideoWorkflowState) -> None:
    """Copy template client files that power ?highlight=&wid= review deep-links."""
    ws = Path(state.get("workspace_root", "."))
    ppt = ws / _PPT_DIR
    if not ppt.is_dir():
        return
    tpl_src = Path(settings.templates_dir) / "src"
    if not tpl_src.is_dir():
        return
    for rel in _PREVIEW_RUNTIME_REL_PATHS:
        src = tpl_src / rel
        dst = ppt / "src" / rel
        if not src.is_file():
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_file():
                if src.read_text(encoding="utf-8") == dst.read_text(encoding="utf-8", errors="replace"):
                    continue
            shutil.copy2(src, dst)
            logger.info("Synced preview runtime file: %s", rel)
        except OSError as e:
            logger.warning("Could not sync preview file %s: %s", rel, e)


def refresh_preview_after_registry(state: VideoWorkflowState) -> None:
    """Restart Vite after chapters.ts changes so the browser sees all built chapters.

    ``ensure_dev_server`` alone is insufficient: Vite HMR often misses registry
    rewrites (especially on WSL ``/mnt/d``), leaving the preview stuck on an old
    single-chapter ``CHAPTERS`` array.
    """
    from harness.services.tools.npm import restart_dev_server

    ws = Path(state.get("workspace_root", "."))
    ppt = ws / _PPT_DIR
    if not ppt.is_dir():
        return
    sync_preview_runtime_files(state)
    expected = [c["id"] for c in list_built_chapters(state)]
    logger.info(
        "Refreshing preview dev server (%d built chapter(s): %s)",
        len(expected),
        ", ".join(expected) or "(none)",
    )
    restart_dev_server(
        state,
        cwd=ppt,
        port=settings.presentation_port,
        expected_chapter_ids=expected,
    )
