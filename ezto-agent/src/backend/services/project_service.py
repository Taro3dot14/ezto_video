"""Project management service — workspace scan, metadata, artifacts."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from harness.core.state_snapshot import state_for_snapshot
from harness.workflow.guards import ARTIFACT_LAYOUT

PROJECT_META_FILE = "project.json"
STATE_SNAPSHOT_FILE = "workflow_state.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_name(project_id: str, user_request: str = "") -> str:
    preview = user_request.strip().splitlines()[0].strip() if user_request else ""
    preview = _strip_md_heading(preview)
    preview = re.sub(r"\s+", " ", preview)
    if preview:
        return preview[:48] + ("…" if len(preview) > 48 else "")
    return f"项目 {project_id[:8]}"


def _strip_md_heading(line: str) -> str:
    return re.sub(r"^#+\s*", "", line).strip()


class ProjectService:
    """Manages project metadata and disk artifacts under workspace_root."""

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root).resolve()

    def bootstrap_workspace(self) -> int:
        """Backfill project.json for legacy workspace folders."""
        self._root.mkdir(parents=True, exist_ok=True)
        created = 0
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir():
                continue
            if self._meta_path(entry.name).exists():
                continue
            user_request = self._read_user_request_from_dir(entry)
            mtime = entry.stat().st_mtime
            updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
            meta = {
                "id": entry.name,
                "name": self._infer_name_from_dir(entry),
                "user_request": user_request[:500],
                "input_type": None,
                "language": "zh-CN",
                "created_at": updated,
                "updated_at": updated,
            }
            self._write_json(self._meta_path(entry.name), meta)
            created += 1
        return created

    def project_dir(self, project_id: str) -> Path:
        self._validate_project_id(project_id)
        return self._root / project_id

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        if not project_id or len(project_id) > 64:
            raise ValueError(f"Invalid project id: {project_id}")
        if project_id in (".", "..") or "/" in project_id or "\\" in project_id:
            raise ValueError(f"Invalid project id: {project_id}")

    def _meta_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / PROJECT_META_FILE

    def _state_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / STATE_SNAPSHOT_FILE

    def ensure_meta(
        self,
        project_id: str,
        *,
        user_request: str = "",
        input_type: str | None = None,
        language: str = "zh-CN",
    ) -> dict[str, Any]:
        """Create or touch project.json when a workflow starts."""
        self.project_dir(project_id).mkdir(parents=True, exist_ok=True)
        path = self._meta_path(project_id)
        now = _now_iso()

        if path.exists():
            meta = self._read_json(path)
            meta["updated_at"] = now
            if user_request and not meta.get("user_request"):
                meta["user_request"] = user_request[:500]
            if input_type:
                meta["input_type"] = input_type
        else:
            meta = {
                "id": project_id,
                "name": _default_name(project_id, user_request),
                "user_request": user_request[:500],
                "input_type": input_type,
                "language": language,
                "created_at": now,
                "updated_at": now,
            }

        self._write_json(path, meta)
        return meta

    def list_projects(self, active_ids: set[str] | None = None) -> list[dict[str, Any]]:
        active_ids = active_ids or set()
        if not self._root.exists():
            return []

        projects: list[dict[str, Any]] = []
        for entry in self._root.iterdir():
            if not entry.is_dir():
                continue
            project_id = entry.name
            meta = self._load_or_infer_meta(project_id, entry)
            artifacts = self.scan_disk_artifacts(project_id)
            generated = sum(1 for a in artifacts if a["exists"])
            projects.append({
                **meta,
                "status": self._derive_status(entry, meta, generated),
                "artifact_count": generated,
                "is_active": project_id in active_ids,
            })

        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects

    def get_project(self, project_id: str, *, active: bool = False) -> dict[str, Any] | None:
        entry = self.project_dir(project_id)
        if not entry.is_dir():
            return None
        meta = self._load_or_infer_meta(project_id, entry)
        artifacts = self.scan_disk_artifacts(project_id)
        generated = sum(1 for a in artifacts if a["exists"])
        return {
            **meta,
            "status": self._derive_status(entry, meta, generated),
            "artifact_count": generated,
            "artifacts": artifacts,
            "is_active": active,
        }

    def rename_project(self, project_id: str, name: str) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("项目名称不能为空")
        if len(name) > 80:
            raise ValueError("项目名称不能超过 80 个字符")

        entry = self.project_dir(project_id)
        if not entry.is_dir():
            raise FileNotFoundError(f"Project {project_id} not found")

        path = self._meta_path(project_id)
        meta = self._load_or_infer_meta(project_id, entry)
        meta["name"] = name
        meta["updated_at"] = _now_iso()
        self._write_json(path, meta)
        return meta

    def delete_project(self, project_id: str) -> dict[str, Any]:
        """Delete project workspace directory and all artifacts."""
        entry = self.project_dir(project_id)
        if not entry.is_dir():
            raise FileNotFoundError(f"Project {project_id} not found")

        meta = self._load_or_infer_meta(project_id, entry)
        shutil.rmtree(entry)
        return meta

    def scan_disk_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        workspace = self.project_dir(project_id)
        if not workspace.is_dir():
            return []

        artifacts: list[dict[str, Any]] = []
        for logical, relative in ARTIFACT_LAYOUT.items():
            full = workspace / relative
            exists = full.exists()
            size = None
            if exists and full.is_file():
                size = full.stat().st_size
            elif exists and full.is_dir():
                size = sum(f.stat().st_size for f in full.rglob("*") if f.is_file())
            artifacts.append({
                "logical_name": logical,
                "path": str(full),
                "relative_path": relative,
                "exists": exists,
                "size": size,
            })
        return artifacts

    def read_artifact(self, project_id: str, logical_or_relative: str) -> tuple[str, str]:
        """Read artifact by logical name or relative path. Returns (content, resolved_path)."""
        workspace = self.project_dir(project_id)
        if not workspace.is_dir():
            raise FileNotFoundError(f"Project {project_id} not found")

        relative = ARTIFACT_LAYOUT.get(logical_or_relative, logical_or_relative)
        full = (workspace / relative).resolve()
        root = workspace.resolve()
        if not str(full).startswith(str(root)):
            raise PermissionError("Path traversal denied")
        if not full.exists() or not full.is_file():
            raise FileNotFoundError(f"Artifact not found: {logical_or_relative}")

        return full.read_text(encoding="utf-8", errors="replace"), relative

    def save_state_snapshot(self, project_id: str, state: dict[str, Any]) -> None:
        entry = self.project_dir(project_id)
        if not entry.is_dir():
            return

        snapshot = state_for_snapshot(state)
        self._write_json(self._state_path(project_id), snapshot)

        path = self._meta_path(project_id)
        meta = self._load_or_infer_meta(project_id, entry)
        meta["updated_at"] = _now_iso()
        if state.get("final_summary"):
            meta["status_hint"] = "completed"
        self._write_json(path, meta)

    def load_state_snapshot(self, project_id: str) -> dict[str, Any] | None:
        path = self._state_path(project_id)
        if not path.exists():
            return None
        try:
            return self._read_json(path)
        except (json.JSONDecodeError, OSError):
            return None

    def _load_or_infer_meta(self, project_id: str, entry: Path) -> dict[str, Any]:
        path = entry / PROJECT_META_FILE
        if path.exists():
            meta = self._read_json(path)
            meta.setdefault("id", project_id)
            meta.setdefault("name", _default_name(project_id))
            return meta

        user_request = self._read_user_request_from_dir(entry)
        mtime = entry.stat().st_mtime
        updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
        return {
            "id": project_id,
            "name": _default_name(project_id, user_request)
            if user_request
            else self._infer_name_from_dir(entry),
            "user_request": user_request[:500],
            "input_type": None,
            "language": "zh-CN",
            "created_at": updated,
            "updated_at": updated,
        }

    def _infer_name_from_dir(self, entry: Path) -> str:
        for fname in ("article.md", "script.md", "outline.md"):
            path = entry / fname
            if not path.is_file():
                continue
            try:
                first = path.read_text(encoding="utf-8", errors="replace").strip()
                if not first:
                    continue
                line = _strip_md_heading(first.splitlines()[0].strip())
                if line:
                    return _default_name(entry.name, line)
            except OSError:
                continue
        return _default_name(entry.name)

    def _read_user_request_from_dir(self, entry: Path) -> str:
        for fname in ("article.md", "script.md"):
            path = entry / fname
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace").strip()
                    if text:
                        return text[:500]
                except OSError:
                    continue
        return ""

    def _derive_status(
        self,
        entry: Path,
        meta: dict[str, Any],
        generated_count: int,
    ) -> str:
        if meta.get("status_hint") == "completed":
            return "completed"
        presentation = entry / "presentation"
        if presentation.is_dir() and any(presentation.iterdir()):
            return "completed"
        if generated_count > 0:
            return "in_progress"
        return "empty"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
