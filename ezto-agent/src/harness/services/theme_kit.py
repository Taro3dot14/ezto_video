"""Theme v2 kit — load metadata, install kit assets, read manifests."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from configs import settings

_THEME_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_TEMPLATES_DIR = Path(settings.themes_dir).parent / "templates"
_STUB_FILES = {
    "components": _TEMPLATES_DIR / "src" / "styles" / "theme-kit.css",
    "presets": _TEMPLATES_DIR / "src" / "motion" / "theme-presets.css",
    "fonts": _TEMPLATES_DIR / "src" / "styles" / "theme-fonts.css",
}
_KIT_INSTALL = {
    "components": ("kit/components.css", "src/styles/theme-kit.css"),
    "presets": ("kit/presets.css", "src/motion/theme-presets.css"),
    "fonts": ("kit/fonts.css", "src/styles/theme-fonts.css"),
    "guide": ("kit/COMPONENT-KIT.md", "src/theme/COMPONENT-KIT.md"),
}


def validate_theme_id(theme_id: str) -> None:
    tid = (theme_id or "").strip()
    if not tid or not _THEME_ID_RE.match(tid):
        raise ValueError(f"Invalid theme id: {theme_id!r}")


def theme_dir(theme_id: str) -> Path:
    validate_theme_id(theme_id)
    return Path(settings.themes_dir) / theme_id


def load_theme_meta(theme_id: str) -> dict[str, Any]:
    """Load theme.json; missing file yields minimal v1 meta."""
    td = theme_dir(theme_id)
    meta_path = td / "theme.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"id": theme_id, "schema": "v1"}


def theme_schema(meta: dict[str, Any]) -> str:
    return str(meta.get("schema") or "v1")


def is_v2_theme(meta: dict[str, Any]) -> bool:
    return theme_schema(meta) == "v2"


def resolve_kit_path(theme_id: str, kit_key: str) -> Path | None:
    """Resolve a kit file from theme.json kit map or default layout."""
    meta = load_theme_meta(theme_id)
    kit_map = meta.get("kit") or {}
    rel = kit_map.get(kit_key)
    if rel:
        path = theme_dir(theme_id) / str(rel)
        return path if path.is_file() else None
    default_rel, _ = _KIT_INSTALL.get(kit_key, (None, None))
    if not default_rel:
        return None
    path = theme_dir(theme_id) / default_rel
    return path if path.is_file() else None


def write_theme_manifest(ppt: Path, theme_id: str, meta: dict[str, Any] | None = None) -> Path:
    marker = ppt / ".theme"
    data = meta or load_theme_meta(theme_id)
    payload = {
        "id": data.get("id", theme_id),
        "schema": theme_schema(data),
    }
    if data.get("family"):
        payload["family"] = data["family"]
    if data.get("capabilities"):
        payload["capabilities"] = data["capabilities"]
    marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


def read_theme_manifest(ppt: Path) -> dict[str, Any] | None:
    marker = ppt / ".theme"
    if not marker.is_file():
        return None
    raw = marker.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"id": raw, "schema": "v1"}
    return {"id": raw, "schema": "v1"}


def install_kit_stubs(ppt: Path) -> None:
    """Install empty v1 stubs so App.tsx imports always resolve."""
    for key, stub in _STUB_FILES.items():
        if not stub.is_file():
            continue
        _, dst_rel = _KIT_INSTALL[key]
        dst = ppt / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stub, dst)
    guide_dst = ppt / "src" / "theme" / "COMPONENT-KIT.md"
    if guide_dst.is_file():
        guide_dst.unlink()


def install_theme_kit(ppt: Path, theme_id: str) -> list[str]:
    """Copy v2 kit assets into presentation; return installed relative paths."""
    meta = load_theme_meta(theme_id)
    if not is_v2_theme(meta):
        install_kit_stubs(ppt)
        return []

    td = theme_dir(theme_id)
    installed: list[str] = []
    kit_map = meta.get("kit") or {}

    for key, (default_src, dst_rel) in _KIT_INSTALL.items():
        rel = kit_map.get(key, default_src)
        src = td / str(rel)
        if not src.is_file():
            if key in _STUB_FILES and _STUB_FILES[key].is_file():
                dst = ppt / dst_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_STUB_FILES[key], dst)
            continue
        dst = ppt / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        installed.append(dst_rel.replace("\\", "/"))

    return installed


def theme_kit_brief_block(workspace_root: Path) -> str | None:
    """Short v2 kit hint for chapter brief / build prompt (no full COMPONENT-KIT)."""
    ppt = workspace_root / "presentation"
    manifest = read_theme_manifest(ppt)
    if not manifest or theme_schema(manifest) != "v2":
        return None
    caps = manifest.get("capabilities") or []
    family = manifest.get("family") or manifest.get("id", "v2")
    lines = [
        "## Theme Kit (v2 — active)",
        f"Family: **{family}**. Use **`tk-*`** components from COMPONENT-KIT.md (included in read_chapter_context).",
        "Combine layout + material: `className=\"lx-split-panel tk-card\"`.",
        "Do **not** hand-roll card border-radius / box-shadow — use `tk-card`, `tk-badge`, `tk-chip`, etc.",
    ]
    if caps:
        lines.append(f"Available: {', '.join(f'`{c}`' for c in caps[:12])}"
                      + (f" (+{len(caps) - 12} more)" if len(caps) > 12 else ""))
    lines.append("Motion: `mot-tk-*` presets in theme-presets.css + one `mot-*` dominant per step.")
    return "\n".join(lines)


def load_component_kit_guide(workspace_root: Path, *, max_chars: int = 14000) -> str | None:
    """Return COMPONENT-KIT.md content when presentation uses a v2 theme."""
    ppt = workspace_root / "presentation"
    manifest = read_theme_manifest(ppt)
    if manifest and theme_schema(manifest) != "v2":
        return None
    guide = ppt / "src" / "theme" / "COMPONENT-KIT.md"
    if not guide.is_file():
        return None
    text = guide.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n…(truncated — full guide in src/theme/COMPONENT-KIT.md)"
    return text


def theme_list_entry(
    theme_dir_path: Path,
    *,
    include_hidden: bool = False,
) -> dict[str, Any] | None:
    meta_file = theme_dir_path / "theme.json"
    if not meta_file.is_file():
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if meta.get("hidden") and not include_hidden:
        return None
    return {
        "id": meta.get("id", theme_dir_path.name),
        "name": meta.get("name", ""),
        "nameZh": meta.get("nameZh", ""),
        "description": meta.get("description", ""),
        "descriptionZh": meta.get("descriptionZh", ""),
        "mood": meta.get("mood", []),
        "bestFor": meta.get("bestFor", []),
        "preview": meta.get("preview"),
        "schema": theme_schema(meta),
        "family": meta.get("family"),
        "capabilities": meta.get("capabilities", []),
    }
