"""Tests for cumulative chapter registry and new-chapter markers."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from harness.workflow.artifacts import (
    apply_chapter_checkpoint_approval,
    built_chapter_step_counts,
    count_built_steps,
    sync_built_chapter_registry,
    update_chapter_meta,
)


def _state(ws: Path, **overrides) -> dict:
    base = {
        "thread_id": str(uuid.uuid4()),
        "workspace_root": str(ws),
        "artifact_paths": {"outline.md": str(ws / "outline.md")},
        "user_confirmations": {},
        "approved_chapter_ids": [],
    }
    base.update(overrides)
    return base


def _outline(ws: Path, *ids: str) -> None:
    lines = []
    for i, cid in enumerate(ids, 1):
        lines.append(f"## {i}. {cid} — Title {i}")
    ws.joinpath("outline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _chapter_files(ws: Path, chapter_id: str, *, steps: int = 1) -> None:
    ch = ws / "presentation" / "src" / "chapters" / chapter_id
    ch.mkdir(parents=True, exist_ok=True)
    ch.joinpath("index.tsx").write_text("export default function X() { return null; }\n", encoding="utf-8")
    lines = "\n".join(f'  "step {i}",  // step {i}' for i in range(steps))
    ch.joinpath("narrations.ts").write_text(
        'import type { Narration } from "../../registry/types";\n\n'
        "export const narrations: Narration[] = [\n"
        f"{lines}\n"
        "];\n",
        encoding="utf-8",
    )


def test_sync_registers_all_built_chapters_in_order(tmp_path: Path):
    _outline(tmp_path, "intro", "core")
    _chapter_files(tmp_path, "intro")
    _chapter_files(tmp_path, "core")

    state = _state(tmp_path)
    sync_built_chapter_registry(state, "core", "Title 2")

    reg = (tmp_path / "presentation" / "src" / "registry" / "chapters.ts").read_text(encoding="utf-8")
    assert "intro" in reg
    assert "core" in reg
    assert reg.index("intro") < reg.index("core")
    assert "export const narrations" in reg or "Narrations" in reg


def test_count_built_steps_sums_all_chapters(tmp_path: Path):
    _outline(tmp_path, "intro", "core")
    _chapter_files(tmp_path, "intro", steps=4)
    _chapter_files(tmp_path, "core", steps=5)

    state = _state(tmp_path)
    assert count_built_steps(state) == 9
    counts = built_chapter_step_counts(state)
    assert counts == [{"id": "intro", "steps": 4}, {"id": "core", "steps": 5}]


def test_sync_registry_uses_named_narrations_export(tmp_path: Path):
    _outline(tmp_path, "intro", "core")
    _chapter_files(tmp_path, "intro", steps=4)
    _chapter_files(tmp_path, "core", steps=5)

    state = _state(tmp_path)
    sync_built_chapter_registry(state, "core", "Title 2")

    reg = (tmp_path / "presentation" / "src" / "registry" / "chapters.ts").read_text(encoding="utf-8")
    assert "introNarrations" in reg
    assert "coreNarrations" in reg
    assert "narrations: introNarrations" in reg
    assert "narrations: coreNarrations" in reg


def test_new_chapter_meta_tracks_unapproved_only(tmp_path: Path):
    _outline(tmp_path, "intro", "core")
    _chapter_files(tmp_path, "intro")
    _chapter_files(tmp_path, "core")

    state = _state(tmp_path, approved_chapter_ids=["intro"])
    sync_built_chapter_registry(state, "core", "Title 2")

    meta = (tmp_path / "presentation" / "src" / "registry" / "chapter-meta.ts").read_text(encoding="utf-8")
    assert '"core"' in meta
    assert '"intro"' not in meta


def test_approval_clears_new_markers(tmp_path: Path):
    _outline(tmp_path, "intro")
    _chapter_files(tmp_path, "intro")
    state = _state(
        tmp_path,
        user_confirmations={"checkpoint_chapter_1": {"approved": True}},
    )
    update_chapter_meta(state, ["intro"])
    result = apply_chapter_checkpoint_approval(state, "checkpoint_chapter_1", ["intro"])

    assert result["approved_chapter_ids"] == ["intro"]
    meta = (tmp_path / "presentation" / "src" / "registry" / "chapter-meta.ts").read_text(encoding="utf-8")
    assert "[]" in meta
