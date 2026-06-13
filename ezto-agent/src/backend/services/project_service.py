"""Project management service."""

from __future__ import annotations

from pathlib import Path


class ProjectService:
    """Manages project creation and listing."""

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root)

    def list_projects(self) -> list[dict]:
        if not self._root.exists():
            return []
        return [
            {"id": d.name, "path": str(d)}
            for d in sorted(self._root.iterdir())
            if d.is_dir()
        ]
