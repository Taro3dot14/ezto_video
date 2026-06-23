"""File read/write operations."""

from __future__ import annotations

from pathlib import Path

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.services.tools.shell import _record_tool_call


def read_file(
    state: VideoWorkflowState,
    path: str,
    *,
    max_bytes: int = 1_000_000,
    offset: int = 1,
    limit: int | None = None,
) -> str:
    _record_tool_call(
        state,
        "read_file",
        {"path": path, "max_bytes": max_bytes, "offset": offset, "limit": limit},
        allowed=True,
        reason="File read for content inspection",
    )
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    if offset == 1 and limit is None:
        return content
    lines = content.splitlines()
    start = max(offset - 1, 0)
    end = start + limit if limit else len(lines)
    sliced = lines[start:end]
    return "\n".join(sliced)


def read_file_with_header(
    state: VideoWorkflowState,
    path: str,
    *,
    offset: int = 1,
    limit: int | None = None,
) -> str:
    """Read a file and prefix with line-range header (for agent display)."""
    full = Path(path)
    content = read_file(state, str(full), offset=offset, limit=limit)
    total = len(full.read_text(encoding="utf-8", errors="replace").splitlines())
    sliced_lines = len(content.splitlines()) if content else 0
    start = max(offset - 1, 0)
    header = f"--- {path} (lines {start + 1}-{start + sliced_lines} of {total}) ---"
    return header + "\n" + content


def read_files(
    state: VideoWorkflowState,
    paths: list[str],
    *,
    offset: int = 1,
    limit: int | None = None,
) -> str:
    """Read multiple files with optional line range."""
    results = []
    for path in paths:
        try:
            results.append(read_file_with_header(state, path, offset=offset, limit=limit))
        except Exception as e:
            results.append(f"--- {path} ---\nERROR: {e}")
    return "\n\n".join(results)


def edit_file(
    state: VideoWorkflowState,
    path: str,
    old_string: str,
    new_string: str,
) -> str:
    """Replace exactly one occurrence of old_string in an existing file."""
    _record_tool_call(
        state,
        "edit_file",
        {"path": path},
        allowed=True,
        reason="Targeted file edit",
    )
    full = Path(path)
    content = full.read_text(encoding="utf-8")
    count = content.count(old_string)
    if count == 0:
        return f"❌ old_string not found in {path}. Read the file around the error line first."
    if count > 1:
        return f"❌ old_string matches {count} times in {path} — include more surrounding context."
    updated = content.replace(old_string, new_string, 1)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(updated, encoding="utf-8")
    logger.info("Edited %s (%d → %d chars)", path, len(old_string), len(new_string))
    return f"✅ Edited {path} (replaced {len(old_string)} chars with {len(new_string)} chars)"


def list_files(root: Path, pattern: str = "*", *, limit: int = 50) -> str:
    """List files under root matching a glob pattern."""
    matched = list(root.rglob(pattern))
    if not matched:
        return f"No files matching '{pattern}'"
    return "\n".join(str(p.relative_to(root)) for p in sorted(matched)[:limit])


def write_file(
    state: VideoWorkflowState,
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
) -> str:
    _record_tool_call(
        state, "write_file", {"path": path},
        allowed=True, reason="File write for artifact generation",
    )
    full = Path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding=encoding)
    logger.info("Written %d chars to %s", len(content), path)
    return f"Written {len(content)} chars to {path}"
