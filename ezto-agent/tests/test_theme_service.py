"""Tests for theme_service.apply_theme."""

from __future__ import annotations

from pathlib import Path

from unittest.mock import patch

import pytest

from backend.services.theme_service import (
    apply_theme,
    presentation_ready,
    resolve_theme_tokens,
    validate_theme_id,
)
from configs import settings


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "proj"
    ws.mkdir()
    return ws


@patch("harness.services.tools.build.npm.restart_dev_server")
def test_refresh_preview_after_theme_apply(mock_restart, workspace: Path):
    from backend.services.theme_service import refresh_preview_after_theme_apply

    ppt = workspace / "presentation" / "src" / "styles"
    ppt.mkdir(parents=True)

    refresh_preview_after_theme_apply(workspace)

    mock_restart.assert_called_once()
    call_kw = mock_restart.call_args
    assert call_kw[1]["cwd"] == workspace / "presentation"


def test_validate_theme_id_rejects_traversal():
    with pytest.raises(ValueError, match="Invalid theme"):
        validate_theme_id("../evil")
    with pytest.raises(ValueError, match="Invalid theme"):
        validate_theme_id("")


def test_resolve_theme_tokens_unknown():
    with pytest.raises(ValueError, match="Unknown theme"):
        resolve_theme_tokens("not-a-real-theme-id-xyz")


def test_apply_theme_copies_tokens_and_marker(workspace: Path):
    themes_dir = Path(settings.themes_dir)
    theme_id = "midnight-press"
    if not (themes_dir / theme_id / "tokens.css").is_file():
        pytest.skip("midnight-press theme missing")

    ppt = workspace / "presentation" / "src" / "styles"
    ppt.mkdir(parents=True)

    result = apply_theme(workspace, theme_id)

    assert result.theme_id == theme_id
    assert result.schema == "v1"
    assert (workspace / "presentation" / "src" / "styles" / "tokens.css").is_file()
    marker_raw = (workspace / "presentation" / ".theme").read_text(encoding="utf-8").strip()
    if marker_raw.startswith("{"):
        import json
        assert json.loads(marker_raw)["id"] == theme_id
    else:
        assert marker_raw == theme_id
    src_head = (themes_dir / theme_id / "tokens.css").read_text(encoding="utf-8")[:80]
    dst_head = (workspace / "presentation" / "src" / "styles" / "tokens.css").read_text(
        encoding="utf-8",
    )[:80]
    assert src_head == dst_head


def test_presentation_not_scaffolded(workspace: Path):
    with pytest.raises(ValueError, match="not scaffolded"):
        presentation_ready(workspace)
