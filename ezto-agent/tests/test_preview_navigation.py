"""Preview deep-link and runtime file sync."""

from pathlib import Path

from harness.workflow.artifacts import sync_preview_runtime_files
from harness.workflow.interruptions import checkpoint_chapter_n


def test_checkpoint_chapter_n_preview_highlight_second_chapter(monkeypatch, tmp_path):
    outline = tmp_path / "outline.md"
    outline.write_text("## 1. a — A\n## 2. b — B\n", encoding="utf-8")

    ppt = tmp_path / "presentation"
    (ppt / "src" / "chapters" / "a").mkdir(parents=True)
    (ppt / "src" / "chapters" / "b").mkdir(parents=True)
    (ppt / "src" / "chapters" / "a" / "index.tsx").write_text("export default function A(){}", encoding="utf-8")
    (ppt / "src" / "chapters" / "a" / "narrations.ts").write_text(
        'import type { Narration } from "../../registry/types";\n'
        "export const narrations: Narration[] = [\n"
        '  "s0",\n  "s1",\n  "s2",\n  "s3",\n];\n',
        encoding="utf-8",
    )
    (ppt / "src" / "chapters" / "b" / "index.tsx").write_text("export default function B(){}", encoding="utf-8")
    (ppt / "src" / "chapters" / "b" / "narrations.ts").write_text(
        'import type { Narration } from "../../registry/types";\n'
        "export const narrations: Narration[] = [\n"
        '  "s0",\n  "s1",\n  "s2",\n  "s3",\n  "s4",\n];\n',
        encoding="utf-8",
    )

    captured: dict = {}

    def _capture(payload):
        captured.update(payload)
        return payload

    monkeypatch.setattr(
        "harness.workflow.interruptions._store_and_interrupt",
        _capture,
    )

    state = {
        "workspace_root": str(tmp_path),
        "thread_id": "test-thread",
        "presentation_url": "http://localhost:5202",
        "artifact_paths": {"outline.md": str(outline)},
    }
    checkpoint_chapter_n(state, 2)
    assert captured["highlight_chapter_index"] == 1
    assert captured["built_step_count"] == 9
    assert captured["chapter_step_counts"] == [
        {"id": "a", "steps": 4},
        {"id": "b", "steps": 5},
    ]
    assert "highlight=1" in captured["preview_url"]
    assert "wid=test-thread" in captured["preview_url"]


def test_sync_preview_runtime_files_copies_use_stepper(tmp_path):
    ws = tmp_path / "ws"
    ppt = ws / "presentation"
    (ppt / "src" / "hooks").mkdir(parents=True)
    (ppt / "src" / "hooks" / "useStepper.ts").write_text("// old\n", encoding="utf-8")

    sync_preview_runtime_files({"workspace_root": str(ws)})
    text = (ppt / "src" / "hooks" / "useStepper.ts").read_text(encoding="utf-8")
    assert "readHighlightChapterIndex" in text
