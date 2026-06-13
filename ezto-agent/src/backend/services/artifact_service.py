"""Artifact management service."""

from __future__ import annotations

from pathlib import Path
from fastapi import HTTPException


class ArtifactService:
    """Reads and lists workflow output files."""

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root)

    def list_artifacts(self, thread_id: str) -> list[dict]:
        ws = self._root / thread_id
        if not ws.exists():
            return []
        artifacts = []
        for p in ws.rglob("*"):
            if p.is_file() and p.name != ".gitkeep":
                artifacts.append({
                    "path": str(p.relative_to(ws)),
                    "size": p.stat().st_size,
                })
        return artifacts

    def read_artifact(self, thread_id: str, path: str) -> str:
        full = (self._root / thread_id / path).resolve()
        if not str(full).startswith(str(self._root.resolve())):
            raise HTTPException(403, detail="Path traversal denied")
        if not full.exists():
            raise HTTPException(404, detail="File not found")
        return full.read_text(encoding="utf-8", errors="replace")
