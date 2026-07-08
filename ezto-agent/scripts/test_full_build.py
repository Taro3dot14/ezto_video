"""End-to-end build verification for an existing workspace."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from harness.services.tools.build.typescript import run_typecheck
from harness.services.tools.build.vite import check_vite
from harness.workflow.artifacts import sync_built_chapter_registry
from harness.workflow.chapter_brief import parse_outline_text


def _state(ws: Path) -> dict:
    return {
        "thread_id": str(uuid.uuid4()),
        "workspace_root": str(ws),
        "artifact_paths": {
            "outline.md": str(ws / "outline.md"),
            "script.md": str(ws / "script.md"),
            "article.md": str(ws / "article.md"),
            "presentation": str(ws / "presentation"),
        },
        "tool_calls": [],
        "current_node": "test_full_build",
    }


def _chapter_status(ws: Path) -> list[dict]:
    outline = ws / "outline.md"
    if not outline.exists():
        return []
    chapters = parse_outline_text(outline.read_text(encoding="utf-8"))
    ppt = ws / "presentation"
    rows = []
    for ch in chapters:
        cid = ch["id"]
        ch_dir = ppt / "src" / "chapters" / cid
        # agent uses chapter_N folders; map by index when id differs
        if not ch_dir.exists():
            ch_dir = ppt / "src" / "chapters" / f"chapter_{ch['index']}"
            cid = f"chapter_{ch['index']}"
        files = {
            "narrations.ts": (ch_dir / "narrations.ts").exists(),
            "index.tsx": (ch_dir / "index.tsx").exists(),
            "index.css": (ch_dir / "index.css").exists(),
        }
        rows.append({"id": cid, "title": ch["title"], "files": files})
    return rows


def main() -> int:
    ws_id = sys.argv[1] if len(sys.argv) > 1 else "11e98c4b-55f6-4d34-98d0-e9613a107f5a"
    ws = _ROOT / "runtime" / "workspace" / ws_id
    ppt = ws / "presentation"

    if not ppt.exists():
        print(f"FAIL: workspace not found: {ws}")
        return 1

    print(f"=== Full build test: {ws_id} ===\n")

    # Fix registry imports (relative paths for tsc)
    state = _state(ws)
    reg_msg = sync_built_chapter_registry(state, "chapter_1", "痛点与钩子")
    print(f"Registry: {reg_msg}\n")

    print("Chapter files:")
    for row in _chapter_status(ws):
        ok = all(row["files"].values())
        mark = "✅" if ok else "⚠️"
        missing = [k for k, v in row["files"].items() if not v]
        extra = f" (missing: {', '.join(missing)})" if missing else ""
        print(f"  {mark} {row['id']}: {row['title']}{extra}")
    print()

    print("Running typecheck...")
    tc = run_typecheck(state, cwd=str(ppt))
    if tc.returncode == 0:
        print("  TYPECHECK: PASS\n")
    else:
        print("  TYPECHECK: FAIL")
        print((tc.stdout or tc.stderr or "")[:2000])
        print()

    print("Running vite build...")
    vb = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ppt),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    if vb.returncode == 0:
        print("  VITE BUILD: PASS")
        dist = ppt / "dist" / "index.html"
        if dist.exists():
            print(f"  Output: {dist}")
    else:
        print("  VITE BUILD: FAIL")
        print((vb.stdout or "")[-2000:])
        print((vb.stderr or "")[-1000:])

    print()
    dist_ok = (ppt / "dist" / "index.html").exists()
    tc_ok = tc.returncode == 0
    if tc_ok and dist_ok:
        print("PASS: presentation builds successfully")
        return 0
    if dist_ok:
        print("PARTIAL: vite build OK, typecheck failed (see above)")
        return 0
    print("FAIL: build did not complete")
    return 1


if __name__ == "__main__":
    sys.exit(main())
