#!/usr/bin/env bash
# Repair chapters.ts to only include built chapters (index.tsx + narrations.ts exist).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS="${1:-$ROOT/runtime/workspace/d4a544b4-6a05-4cd5-84f4-2a553c2401de}"
cd "$ROOT"
python3 - "$WS" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "src")
from harness.workflow.artifacts import sync_built_chapter_registry
from harness.workflow.chapter_brief import parse_outline_chapters_from_state

ws = Path(sys.argv[1])
state = {"workspace_root": str(ws)}
chapters = parse_outline_chapters_from_state(state)
ppt = ws / "presentation"
built = [ch for ch in chapters if (ppt / "src/chapters" / ch["id"] / "index.tsx").exists()
         and (ppt / "src/chapters" / ch["id"] / "narrations.ts").exists()]
if not built:
    raise SystemExit("No built chapters found")
last = built[-1]
sync_built_chapter_registry(state, last["id"], last["title"])
print("Registry fixed:", [c["id"] for c in built])

from harness.workflow.artifacts import refresh_preview_after_registry
refresh_preview_after_registry(state)
print("Preview dev server restarted")
PY
