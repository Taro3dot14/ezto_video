"""Apply presentation themes — v1 tokens-only or v2 kit bundle."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from harness.services.theme_kit import (
    install_theme_kit,
    load_theme_meta,
    theme_dir,
    validate_theme_id,
    write_theme_manifest,
)

_PPT_DIR = "presentation"


@dataclass(frozen=True)
class ThemeApplyResult:
    theme_id: str
    tokens_path: str
    theme_marker_path: str
    schema: str = "v1"
    kit_files: tuple[str, ...] = ()


def resolve_theme_tokens(theme_id: str) -> Path:
    """Return path to tokens.css for a built-in theme."""
    validate_theme_id(theme_id)
    tokens = theme_dir(theme_id) / "tokens.css"
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
    """Copy theme tokens (+ v2 kit when applicable) into the workspace presentation."""
    validate_theme_id(theme_id)
    meta = load_theme_meta(theme_id)
    tokens_src = resolve_theme_tokens(theme_id)
    ws = workspace_root.resolve()
    ppt = presentation_ready(ws)

    tokens_dst = ppt / "src" / "styles" / "tokens.css"
    tokens_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tokens_src, tokens_dst)

    kit_files = tuple(install_theme_kit(ppt, theme_id))
    marker = write_theme_manifest(ppt, theme_id, meta)

    return ThemeApplyResult(
        theme_id=theme_id,
        tokens_path=str(tokens_dst),
        theme_marker_path=str(marker),
        schema=str(meta.get("schema") or "v1"),
        kit_files=kit_files,
    )


def refresh_preview_after_theme_apply(workspace_root: str | Path) -> None:
    """Restart Vite so theme file edits are picked up."""
    from configs import settings
    from harness.services.tools.build.npm import restart_dev_server

    ws = str(Path(workspace_root).resolve())
    ppt = Path(ws) / _PPT_DIR
    if not ppt.is_dir():
        return
    restart_dev_server({"workspace_root": ws}, cwd=ppt, port=settings.presentation_port)
