"""Narration file generation for presentation chapters."""

from __future__ import annotations

from pathlib import Path

from harness.core.state import VideoWorkflowState
from harness.services.tools.fs.file_ops import write_file as svc_write_file
from harness.services.tools.chapter.narration_args import normalize_narration_lines


def build_narrations_content(lines: list[str]) -> str:
    """Build narrations.ts source from per-step strings."""
    if not lines:
        raise ValueError("lines must be a non-empty array of narration strings")
    normalized = normalize_narration_lines(lines)
    escaped = []
    for i, line in enumerate(normalized):
        text = str(line).replace("\\", "\\\\").replace('"', '\\"')
        escaped.append(f'  "{text}",  // step {i}')
    body = "\n".join(escaped)
    return (
        'import type { Narration } from "../../registry/types";\n\n'
        "export const narrations: Narration[] = [\n"
        f"{body}\n"
        "];\n"
    )


def write_narrations(
    state: VideoWorkflowState,
    *,
    workspace_root: Path,
    chapter_id: str,
    lines: list[str],
) -> str:
    """Write presentation/src/chapters/<id>/narrations.ts."""
    content = build_narrations_content(lines)
    rel = f"presentation/src/chapters/{chapter_id}/narrations.ts"
    full = workspace_root / rel if not Path(rel).is_absolute() else Path(rel)
    return svc_write_file(state, str(full), content)
