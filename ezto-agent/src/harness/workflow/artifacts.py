"""Helper functions shared across graph nodes."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from configs import settings
from backend.core.logger import logger

from ..core.state import VideoWorkflowState

MAX_REPAIR_RETRIES = 3
_PPT_DIR = "presentation"


def think(log: list | None, type_: str, content: str) -> list[dict]:
    """Append a thinking event to an in-progress list. Pass None to start fresh."""
    if log is None:
        log = []
    log.append({"type": type_, "content": content, "ts": time.time()})
    return log


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
    path = state.get("artifact_paths", {}).get("outline.md")
    if not path or not Path(path).exists():
        return [{"id": "chapter_1", "title": "Chapter 1"}]
    chapters, idx = [], 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+Chapter\s+(\d+)", line, re.IGNORECASE)
        if m:
            idx += 1
            chapters.append(
                {"id": f"chapter_{idx}", "title": re.sub(r"^##\s+", "", line).strip()}
            )
    return chapters or [{"id": "chapter_1", "title": "Chapter 1"}]


def get_repair_count(state: VideoWorkflowState, target: str) -> int:
    """Count how many times a target has been repaired."""
    return sum(1 for r in state.get("repair_history", []) if r.get("target") == target)


def update_chapter_registry(state: VideoWorkflowState, chapters: list[dict]) -> None:
    """Generate chapters.ts from the template file."""
    ws = state.get("workspace_root", ".")
    reg_file = Path(ws) / _PPT_DIR / "src" / "registry" / "chapters.ts"

    import_lines = "\n".join(
        f"import {ch['id']} from '@/chapters/{ch['id']}';" for ch in chapters
    ) + "\n" + "\n".join(
        f"import {{ narrations as {ch['id']}Narrations }} from '@/chapters/{ch['id']}/narrations';"
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
