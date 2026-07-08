"""Tests for harness/workflow/nodes/web.py — all Phase 2 nodes."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.workflow.nodes.web import (
    wv_scaffold_presentation,
    wv_build_chapter_1,
    wv_checkpoint_chapter_1_node,
    wv_build_chapter_n,
    wv_checkpoint_chapter_n_node,
    wv_checkpoint_remaining_batch_node,
    wv_transition_to_phase3,
)

_WS = "workspace_root"
_PPT = "presentation"


def _base_state(**overrides) -> dict:
    """Build a minimal valid state."""
    ws = str(Path(tempfile.mkdtemp()))
    return {
        "thread_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "user_request": "test article",
        "language": "zh-CN",
        "current_phase": "phase2",
        "current_node": "",
        "completed_nodes": [],
        "thinking_log": [],
        "current_chapter_index": 0,
        "total_chapters": 0,
        "pending_interrupt": None,
        "required_refs": [],
        "loaded_refs": ["CHAPTER-CRAFT.md"],
        "workspace_root": ws,
        "artifact_paths": {
            "script.md": f"{ws}/script.md",
            "outline.md": f"{ws}/outline.md",
            "presentation": f"{ws}/{_PPT}",
        },
        "created_files": [],
        "modified_files": [],
        "user_confirmations": {"checkpoint_plan": {"selected_theme": "dune", "development_mode": "A"}},
        "validation_results": [],
        "repair_history": [],
        "errors": [],
        "allowed_tools": [],
        "denied_tools": [],
        "tool_calls": [],
        "final_summary": None,
        **overrides,
    }


# ═══════════════════════════════════════════════════════════════
# wv_scaffold_presentation
# ═══════════════════════════════════════════════════════════════

class TestScaffoldPresentation:
    @patch("harness.workflow.nodes.web.run_scaffold")
    @patch("harness.workflow.nodes.web.run_dev_server")
    def test_scaffold_success(self, mock_dev, mock_scaffold):
        mock_scaffold.return_value = MagicMock(returncode=0, stderr="")
        state = _base_state()
        result = wv_scaffold_presentation(state)
        mock_scaffold.assert_called_once()
        assert result.get("presentation_url") is not None
        assert "http://localhost" in result["presentation_url"]

    @patch("harness.workflow.nodes.web.run_scaffold")
    def test_scaffold_failure(self, mock_scaffold):
        mock_scaffold.return_value = MagicMock(returncode=1, stderr="npm not found")
        state = _base_state()
        result = wv_scaffold_presentation(state)
        assert result.get("errors")
        assert "npm not found" in result["errors"][0]["error"]

    @patch("harness.workflow.nodes.web.run_scaffold")
    @patch("harness.workflow.nodes.web.run_dev_server")
    def test_scaffold_dev_server_fails_gracefully(self, mock_dev, mock_scaffold):
        mock_scaffold.return_value = MagicMock(returncode=0, stderr="")
        mock_dev.side_effect = RuntimeError("port in use")
        state = _base_state()
        result = wv_scaffold_presentation(state)
        assert result["presentation_url"] is None


# ═══════════════════════════════════════════════════════════════
# wv_build_chapter_1
# ═══════════════════════════════════════════════════════════════

class TestBuildChapter1:
    @patch("harness.workflow.nodes.web.run_chapter_pipeline")
    def test_agent_success(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(
            success=True, iterations=8, tool_calls=7,
            content="built chapter 1", files_created=[],
        )

        state = _base_state()
        ws = state[_WS]
        outline = Path(ws, "outline.md")
        outline.write_text("## Chapter 1 — Test Chapter\n## Chapter 2 — Another\n")
        Path(ws, "script.md").write_text("## Script\n\nTest script content")

        result = wv_build_chapter_1(state)
        mock_pipeline.assert_called_once()
        assert result["current_node"] == "wv_build_chapter_1"
        assert "thinking_log" in result

    @patch("harness.workflow.nodes.web.run_chapter_pipeline")
    def test_agent_failure(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(
            success=False, iterations=50, tool_calls=20,
            content="max iterations", files_created=[],
        )

        state = _base_state()
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — Test\n")
        Path(ws, "script.md").write_text("# Script\n")

        result = wv_build_chapter_1(state)
        assert result.get("errors")
        assert "max iterations" in result["errors"][0]["error"]

    @patch("harness.workflow.nodes.web.run_chapter_pipeline")
    def test_agent_success_but_files_missing(self, mock_pipeline):
        """Agent says success but didn't write files."""
        mock_pipeline.return_value = MagicMock(
            success=True, iterations=3, tool_calls=1,
            content="done", files_created=[],
        )

        state = _base_state()
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — Test\n")
        Path(ws, "script.md").write_text("# Script\n")

        result = wv_build_chapter_1(state)
        assert result.get("errors")
        assert "missing" in result["errors"][0]["error"].lower()

    @patch("harness.workflow.nodes.web.run_chapter_revision_pipeline")
    def test_checkpoint_rejection_uses_revision_not_full_build(self, mock_revision):
        mock_revision.return_value = MagicMock(
            success=True, iterations=3, tool_calls=2, content="revised",
        )
        state = _base_state(
            user_confirmations={
                "checkpoint_plan": {"selected_theme": "dune", "development_mode": "A"},
                "checkpoint_chapter_1": {
                    "approved": False,
                    "feedback": "标题字号太小，请加大",
                },
            },
        )
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — Test Chapter\n")
        Path(ws, "script.md").write_text("# Script\n")
        ch_dir = Path(ws, _PPT, "src", "chapters", "chapter_1")
        ch_dir.mkdir(parents=True, exist_ok=True)
        (ch_dir / "index.tsx").write_text("export default () => <div>old</div>;")
        (ch_dir / "narrations.ts").write_text("export const narrations = ['a'];")
        (ch_dir / "index.css").write_text(".ch-old {}")

        result = wv_build_chapter_1(state)

        mock_revision.assert_called_once()
        call_kw = mock_revision.call_args.kwargs
        assert call_kw["user_feedback"] == "标题字号太小，请加大"
        assert (ch_dir / "index.tsx").read_text() == "export default () => <div>old</div>;"
        assert result["current_node"] == "wv_build_chapter_1"
        assert not result.get("errors")


# ═══════════════════════════════════════════════════════════════
# wv_build_chapter_n
# ═══════════════════════════════════════════════════════════════

class TestBuildChapterN:
    @patch("harness.workflow.nodes.web.run_chapter_pipeline")
    def test_builds_chapter_2_files_present(self, mock_pipeline):
        """Agent succeeds AND writes files → happy path."""
        state = _base_state(current_chapter_index=1)
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — First\n## Chapter 2 — Second\n")
        Path(ws, "script.md").write_text("# Script content")

        def _pipeline_run(_state, **kw):
            ch_dir = Path(ws, _PPT, "src", "chapters", kw["chapter_id"])
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "index.tsx").write_text("export default () => null;")
            (ch_dir / "narrations.ts").write_text("export const narrations = [];")
            return MagicMock(success=True, iterations=6, tool_calls=5)

        mock_pipeline.side_effect = _pipeline_run

        with patch("harness.workflow.nodes.web.refresh_preview_after_registry") as mock_refresh:
            result = wv_build_chapter_n(state)
        mock_refresh.assert_called_once()
        assert result["current_chapter_index"] == 2
        assert result["total_chapters"] == 2

    @patch("harness.workflow.nodes.web.run_chapter_pipeline")
    def test_builds_chapter_2_files_missing(self, mock_pipeline):
        """Agent says success but no files → should return error."""
        mock_pipeline.return_value = MagicMock(
            success=True, iterations=3, tool_calls=1,
            content="done", files_created=[],
        )

        state = _base_state(current_chapter_index=1)
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — First\n## Chapter 2 — Second\n")
        Path(ws, "script.md").write_text("# Script")

        result = wv_build_chapter_n(state)
        assert result.get("errors")

    def test_invalid_index(self):
        state = _base_state(current_chapter_index=99)  # way past total
        ws = state[_WS]
        Path(ws, "outline.md").write_text("## Chapter 1 — Only\n")
        result = wv_build_chapter_n(state)
        assert result.get("errors")
        assert "Invalid index" in result["errors"][0]["error"]


# ═══════════════════════════════════════════════════════════════
# wv_transition_to_phase3
# ═══════════════════════════════════════════════════════════════

class TestTransitionToPhase3:
    def test_guard_without_checkpoint(self):
        """Needs checkpoint_chapter_1 before proceeding."""
        state = _base_state(
            user_confirmations={},
            artifact_paths={}
        )
        with pytest.raises(Exception):  # PolicyViolation
            wv_transition_to_phase3(state)

    def test_missing_artifacts(self):
        state = _base_state()
        state["user_confirmations"]["checkpoint_chapter_1"] = {"approved": True}
        result = wv_transition_to_phase3(state)
        # Phase 2 artifacts check — presentation dir may not exist
        missing = result.get("errors")
        assert result["current_phase"] == "phase3"


# ═══════════════════════════════════════════════════════════════
# Checkpoint nodes (raise GraphInterrupt)
# ═══════════════════════════════════════════════════════════════

class TestCheckpointNodes:
    def test_checkpoint_chapter_1(self):
        state = _base_state(presentation_url="http://localhost:5202")
        with pytest.raises(Exception):  # GraphInterrupt
            wv_checkpoint_chapter_1_node(state)

    def test_checkpoint_chapter_n(self):
        state = _base_state(current_chapter_index=2)
        with pytest.raises(Exception):
            wv_checkpoint_chapter_n_node(state)

    def test_checkpoint_remaining_batch(self):
        state = _base_state(current_chapter_index=3, total_chapters=5)
        with pytest.raises(Exception):
            wv_checkpoint_remaining_batch_node(state)
