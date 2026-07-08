"""Apply presentation themes by swapping tokens.css."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from configs import settings

_THEME_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PPT_DIR = "presentation"


@dataclass(frozen=True)
class ThemeApplyResult:
    theme_id: str
    tokens_path: str
    theme_marker_path: str


def validate_theme_id(theme_id: str) -> None:
    tid = (theme_id or "").strip()
    if not tid or not _THEME_ID_RE.match(tid):
        raise ValueError(f"Invalid theme id: {theme_id!r}")


def resolve_theme_tokens(theme_id: str) -> Path:
    """Return path to tokens.css for a built-in theme."""
    validate_theme_id(theme_id)
    theme_dir = Path(settings.themes_dir) / theme_id
    tokens = theme_dir / "tokens.css"
    if not tokens.is_file():
        raise ValueError(f"Unknown theme: {theme_id}")
    return tokens


def presentation_ready(workspace_root: Path) -> Path:
    """Return presentation root or raise if not scaffolded."""
    ppt = workspace_root / _PPT_DIR
    styles = ppt / "src" / "styles"
    if not styles.is_dir():
        raise ValueError("Presentation not scaffolded — run workflow through scaffold first")
    return ppt


def apply_theme(workspace_root: Path, theme_id: str) -> ThemeApplyResult:
    """Copy theme tokens into the workspace presentation project."""
    tokens_src = resolve_theme_tokens(theme_id)
    ws = workspace_root.resolve()
    ppt = presentation_ready(ws)

    tokens_dst = ppt / "src" / "styles" / "tokens.css"
    tokens_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tokens_src, tokens_dst)

    marker = ppt / ".theme"
    marker.write_text(f"{theme_id}\n", encoding="utf-8")

    return ThemeApplyResult(
        theme_id=theme_id,
        tokens_path=str(tokens_dst),
        theme_marker_path=str(marker),
    )


def refresh_preview_after_theme_apply(workspace_root: str | Path) -> None:
    """Restart Vite so tokens.css edits are picked up (WSL /mnt/d watchers often miss copies)."""
    from configs import settings
    from harness.services.tools.build.npm import restart_dev_server

    ws = str(Path(workspace_root).resolve())
    ppt = Path(ws) / _PPT_DIR
    if not ppt.is_dir():
        return
    restart_dev_server({"workspace_root": ws}, cwd=ppt, port=settings.presentation_port)
