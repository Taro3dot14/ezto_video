"""Workspace lifecycle management."""

from __future__ import annotations

from pathlib import Path


class WorkspaceService:
    """Creates and cleans up thread workspaces."""

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root)

    def create(self, thread_id: str) -> str:
        ws = (self._root / thread_id).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        return str(ws)

    def remove(self, thread_id: str) -> None:
        ws = self._root / thread_id
        if ws.exists():
            import shutil
            shutil.rmtree(ws)
