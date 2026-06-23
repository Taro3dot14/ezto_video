"""Batch-read a chapter's page files plus registry files."""



from __future__ import annotations



import re

from pathlib import Path



from harness.core.state import VideoWorkflowState

from harness.services.tools.craft_review import (
    format_craft_checklist,
    init_craft_checklist,
    run_craft_auto_checks,
)
from harness.services.tools.file_ops import read_file_with_header
from harness.services.tools.shell import _record_tool_call
from harness.workflow.chapter_ids import resolve_chapter_id

from harness.workflow.chapter_policies import (

    auto_validate_chapter,

    validate_theme_contrast,

    validate_tsx_css_classes,

)



_CHAPTER_FILES = ("narrations.ts", "index.tsx", "index.css")

_REGISTRY_FILES = (

    "presentation/src/registry/chapters.ts",

    "presentation/src/registry/chapter-meta.ts",

)





def _chapter_paths(ws: Path, chapter_id: str) -> list[tuple[str, Path]]:

    ch = ws / "presentation" / "src" / "chapters" / chapter_id

    paths: list[tuple[str, Path]] = [(name, ch / name) for name in _CHAPTER_FILES]

    for rel in _REGISTRY_FILES:

        paths.append((rel, ws / rel))

    return paths





def validate_chapter_bundle(

    ppt: Path,

    chapter_id: str,

    *,

    chapters_ts: str = "",

) -> tuple[bool, list[str], list[str]]:

    """Return (ok, errors, warnings) for structural pre-review checks."""

    errors: list[str] = []

    warnings: list[str] = []

    ch_dir = ppt / "src" / "chapters" / chapter_id



    for fname in _CHAPTER_FILES:

        if not (ch_dir / fname).exists():

            errors.append(f"❌ Missing presentation/src/chapters/{chapter_id}/{fname}")



    if chapters_ts:

        if f"id: '{chapter_id}'" not in chapters_ts and f'id: "{chapter_id}"' not in chapters_ts:

            errors.append(

                f"❌ {chapter_id} not in chapters.ts — call update_registry first"

            )

        if f"from '../chapters/{chapter_id}'" not in chapters_ts:

            errors.append(f"❌ chapters.ts missing import for {chapter_id}")



        reg_ids = re.findall(r"id:\s*['\"]([^'\"]+)['\"]", chapters_ts)

        reg_ids = [i for i in reg_ids if not i.endswith("Narrations")]

        disk_ids = sorted(

            d.name

            for d in (ppt / "src" / "chapters").iterdir()

            if d.is_dir()

            and (d / "index.tsx").exists()

            and (d / "narrations.ts").exists()

            and d.name != "01-example"

        )

        missing_in_reg = sorted(set(disk_ids) - set(reg_ids))

        if missing_in_reg:

            errors.append(

                f"❌ Built on disk but not in registry: {', '.join(missing_in_reg)}"

            )



    if ch_dir.joinpath("index.tsx").exists() and ch_dir.joinpath("index.css").exists():

        if mismatch := validate_tsx_css_classes(ppt, chapter_id):

            errors.append(f"❌ {mismatch}")

        css_text = ch_dir.joinpath("index.css").read_text(encoding="utf-8")

        if contrast := validate_theme_contrast(css_text):

            errors.append(f"❌ {contrast}")



    if hint := auto_validate_chapter(ppt, chapter_id):

        for line in hint.splitlines():

            if line.startswith("⚠️"):

                warnings.append(line)

            else:

                errors.append(line if line.startswith("❌") else f"❌ {line}")



    return len(errors) == 0, errors, warnings





def _format_structural_review(

    *,

    ok: bool,

    errors: list[str],

    warnings: list[str],

) -> str:

    lines = ["--- Structural checks ---"]

    if ok and not warnings:

        lines.append("✅ Registry / TSX↔CSS / theme contrast OK")

    else:

        if errors:

            lines.append("Fix before craft review:")

            lines.extend(errors)

        if warnings:

            lines.append("Warnings:")

            lines.extend(warnings)

    return "\n".join(lines)





def review_chapter_bundle(

    state: VideoWorkflowState,

    *,

    workspace_root: Path,

    chapter_id: str,

    ctx: dict | None = None,

) -> tuple[str, bool]:

    """Read chapter + registry files; run CHAPTER-CRAFT checklist."""
    default_id = (ctx or {}).get("chapter_id", chapter_id)
    resolved, warn = resolve_chapter_id(state, chapter_id, default=default_id)
    chapter_id = resolved

    _record_tool_call(
        state,
        "review_chapter_bundle",
        {"chapter_id": chapter_id},
        allowed=True,
        reason="Batch read chapter files and registry for review",
    )
    ppt = workspace_root / "presentation"

    parts: list[str] = []
    if warn:
        parts.append(warn)

    chapters_ts = ""



    for label, path in _chapter_paths(workspace_root, chapter_id):

        if not path.exists():

            parts.append(f"--- {label} ---\nERROR: file not found at {path}")

            continue

        if label.endswith("chapters.ts"):

            chapters_ts = path.read_text(encoding="utf-8", errors="replace")

        parts.append(read_file_with_header(state, str(path)))



    struct_ok, errors, warnings = validate_chapter_bundle(

        ppt, chapter_id, chapters_ts=chapters_ts,

    )

    parts.append(_format_structural_review(ok=struct_ok, errors=errors, warnings=warnings))



    review_ctx = ctx if ctx is not None else {}

    if struct_ok:

        init_craft_checklist(review_ctx, workspace_root=workspace_root, chapter_id=chapter_id)
        run_craft_auto_checks(review_ctx, workspace_root=workspace_root, chapter_id=chapter_id)

        parts.append(format_craft_checklist(review_ctx))

        return "\n\n".join(parts), bool(review_ctx.get("review_ok"))

    review_ctx["review_ok"] = False

    parts.append("--- CHAPTER-CRAFT 完工自检 ---\n❌ 先修复上方 structural errors")

    return "\n\n".join(parts), False

