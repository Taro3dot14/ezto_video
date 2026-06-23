"""Tests for script repair when script.md is missing on disk."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from harness.core.state import VideoWorkflowState
from harness.workflow.nodes.content import wv_repair_script


def _base_state(tmp_path: Path) -> VideoWorkflowState:
    workspace_root = str(tmp_path / "workspace")
    ws = tmp_path / "workspace" / "tid-1"
    return {
        "thread_id": "tid-1",
        "workspace_root": workspace_root,
        "artifact_paths": {
            "script.md": str(ws / "script.md"),
            "outline.md": str(ws / "outline.md"),
            "article.md": str(ws / "article.md"),
        },
        "user_request": "第一句口播。\n---\n第二句口播。",
        "input_type": "script",
        "language": "zh-CN",
        "required_refs": ["SCRIPT-STYLE.md"],
        "loaded_refs": ["SCRIPT-STYLE.md"],
        "validation_results": [{
            "node": "wv_validate_script",
            "target": "script.md",
            "passed": False,
            "failed_checks": ["短句原则"],
            "details": "句子过长",
        }],
        "repair_history": [],
    }


@patch("harness.workflow.nodes.content.llm.chat")
@patch("harness.workflow.nodes.content.require_ref_loaded", return_value="# style")
def test_repair_script_creates_missing_file(mock_ref, mock_chat, tmp_path: Path):
    state = _base_state(tmp_path)
    ws = tmp_path / "workspace" / "tid-1"
    repaired = ("优化后的口播。\n---\n" * 40)[:1200]
    mock_chat.return_value = repaired

    result = wv_repair_script(state)

    script = ws / "script.md"
    assert script.exists()
    assert Path(result["modified_files"][0]) == script
    assert len(result["repair_history"]) == 1
