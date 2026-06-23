"""Tests for presentation dev-server lifecycle (shared port 5202)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from harness.services.tools import npm as npm_mod


def _mock_proc(*, alive: bool = True) -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None if alive else 1
    proc.pid = 4242
    return proc


def test_ensure_dev_server_noop_when_same_workspace_up():
    npm_mod._DEV_SERVERS.clear()
    npm_mod._DEV_SERVERS["/ws/a"] = _mock_proc()

    state = {"workspace_root": "/ws/a"}
    with patch.object(npm_mod, "_port_responds", return_value=True):
        with patch.object(npm_mod, "run_dev_server") as mock_run:
            npm_mod.ensure_dev_server(state, cwd="/ws/a/presentation", port=5202)
    mock_run.assert_not_called()


def test_ensure_dev_server_switches_workspace_on_port_conflict():
    npm_mod._DEV_SERVERS.clear()
    npm_mod._DEV_SERVERS["/ws/old"] = _mock_proc()

    state = {"workspace_root": "/ws/new"}
    with patch.object(npm_mod, "_port_responds", return_value=True):
        with patch.object(npm_mod, "_kill_dev_server") as mock_kill:
            with patch.object(npm_mod, "run_dev_server") as mock_run:
                npm_mod.ensure_dev_server(state, cwd="/ws/new/presentation", port=5202)

    mock_kill.assert_called_once_with("/ws/old")
    mock_run.assert_called_once()


def test_restart_dev_server_kills_and_starts():
    npm_mod._DEV_SERVERS.clear()
    npm_mod._DEV_SERVERS["/ws/old"] = _mock_proc()

    state = {"workspace_root": "/ws/new"}
    with patch.object(npm_mod, "_free_port") as mock_free:
        with patch.object(npm_mod, "_vite_serves_chapter_ids", return_value=True):
            with patch.object(npm_mod, "_port_responds", side_effect=[False, False, True]):
                with patch.object(npm_mod, "_kill_dev_server") as mock_kill:
                    with patch.object(npm_mod, "run_dev_server") as mock_run:
                        with patch("time.sleep"):
                            npm_mod.restart_dev_server(
                                state,
                                cwd="/ws/new/presentation",
                                port=5202,
                                expected_chapter_ids=["coldopen", "why_we_need"],
                            )

    assert mock_kill.call_count >= 1
    mock_free.assert_called()
    mock_run.assert_called_once()


def test_ensure_dev_server_frees_untracked_port():
    npm_mod._DEV_SERVERS.clear()
    state = {"workspace_root": "/ws/a"}
    with patch.object(npm_mod, "_port_responds", side_effect=[True, False, True]):
        with patch.object(npm_mod, "_free_port") as mock_free:
            with patch.object(npm_mod, "run_dev_server") as mock_run:
                npm_mod.ensure_dev_server(state, cwd="/ws/a/presentation", port=5202)
    mock_free.assert_called_once_with(5202)
    mock_run.assert_called_once()


def test_vite_serves_chapter_ids_detects_registry():
    body = 'export const CHAPTERS = [{ id: "coldopen" }, { id: "why_we_need" }];'
    with patch("urllib.request.build_opener") as mock_opener:
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = body.encode()
        mock_resp.status = 200
        mock_opener.return_value.open.return_value = mock_resp
        assert npm_mod._vite_serves_chapter_ids(5202, ["coldopen", "why_we_need"])


def test_vite_serves_chapter_ids_rejects_stale_registry():
    body = 'export const CHAPTERS = [{ id: "coldopen" }];'
    with patch("urllib.request.build_opener") as mock_opener:
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = body.encode()
        mock_opener.return_value.open.return_value = mock_resp
        assert not npm_mod._vite_serves_chapter_ids(5202, ["coldopen", "why_we_need"])


def test_run_dev_server_kills_other_workspaces_first():
    npm_mod._DEV_SERVERS.clear()
    npm_mod._DEV_SERVERS["/ws/other"] = _mock_proc()

    state = {"workspace_root": "/ws/mine"}
    with patch.object(npm_mod, "_kill_dev_server") as mock_kill:
        with patch.object(npm_mod.subprocess, "Popen", return_value=_mock_proc()) as mock_popen:
            npm_mod.run_dev_server(state, cwd="/ws/mine/presentation", port=5202)

    mock_kill.assert_called_once_with("/ws/other")
    mock_popen.assert_called_once()
