"""Tests for team_discuss round loop."""

from unittest.mock import MagicMock, patch

from harness.agent.chapter_build import _run_team_discuss_pipeline
from harness.agent.loop import AgentResult


def _ok_build():
    return AgentResult(content="built", success=True, history="write_narrations: ok")


def _ok_repair():
    return AgentResult(content="fixed", success=True, history="edit_file: ok")


def _ok_verify():
    return AgentResult(content="verified", success=True)


@patch("harness.agent.chapter_build._run_programmatic_verify")
@patch("harness.agent.chapter_build.WebBuildAgent")
@patch("harness.agent.chapter_build.ChapterReviewAgent")
@patch("harness.agent.chapter_build._run_team_meeting")
@patch("harness.agent.chapter_build.settings")
def test_team_discuss_passes_on_first_review(
    mock_settings, mock_meeting, mock_review_cls, mock_build_cls, mock_verify,
):
    mock_settings.chapter_review_max_rounds = 2

    mock_build = MagicMock()
    mock_build.run.return_value = _ok_build()
    mock_build_cls.return_value = mock_build

    mock_reviewer = MagicMock()
    mock_reviewer.review_ok = True
    mock_reviewer.craft_checklist_text.return_value = "✅ all pass"
    mock_reviewer.run.return_value = AgentResult(content="review ok", success=True)
    mock_review_cls.return_value = mock_reviewer

    mock_verify.return_value = _ok_verify()

    result = _run_team_discuss_pipeline(
        {"workspace_root": "/tmp"},
        chapter_id="chapter_1",
        title="T",
        chapter_index=1,
        total_chapters=1,
        previous_chapters="",
        revision_feedback=None,
    )
    assert result.success
    mock_meeting.assert_not_called()
    mock_build.run.assert_called()
    assert mock_reviewer.run.call_count == 1
    mock_verify.assert_called_once()


@patch("harness.agent.chapter_build._run_programmatic_verify")
@patch("harness.agent.chapter_build.failed_item_ids")
@patch("harness.agent.chapter_build.WebBuildAgent")
@patch("harness.agent.chapter_build.ChapterReviewAgent")
@patch("harness.agent.chapter_build._run_team_meeting")
@patch("harness.agent.chapter_build.settings")
def test_team_discuss_meeting_then_repair_then_pass(
    mock_settings, mock_meeting, mock_review_cls, mock_build_cls, mock_failed, mock_verify,
):
    mock_settings.chapter_review_max_rounds = 2
    mock_settings.chapter_repair_max_rounds = 2
    mock_meeting.return_value = "## Team Action Plan\nfix hero font"
    mock_failed.side_effect = [["NO_AI_SLOP"], []]

    build_agent = MagicMock()
    build_agent.run.side_effect = [_ok_build(), _ok_repair()]

    review_instances = []
    for ok in (False, True):
        r = MagicMock()
        r.review_ok = ok
        r.TODO_ITEMS = {"NO_AI_SLOP": "no slop"}
        r._todo_done = set() if not ok else {"NO_AI_SLOP"}
        r.craft_checklist_text.return_value = "☐ pending" if not ok else "✅ pass"
        r.run.return_value = AgentResult(content="review", success=True)
        review_instances.append(r)
    mock_review_cls.side_effect = review_instances
    mock_build_cls.return_value = build_agent
    mock_verify.return_value = _ok_verify()

    result = _run_team_discuss_pipeline(
        {"workspace_root": "/tmp"},
        chapter_id="chapter_1",
        title="T",
        chapter_index=1,
        total_chapters=1,
        previous_chapters="",
        revision_feedback=None,
    )
    assert result.success
    mock_meeting.assert_called_once()
    assert build_agent.run.call_count == 2  # build, repair
    assert mock_review_cls.call_count == 2
    mock_verify.assert_called_once()
