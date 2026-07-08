"""Central session state for chapter build / review / verify agents."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Iterator


class ChapterSessionState(MutableMapping[str, Any]):
    """Mutable session bag with typed accessors for build-progress flags.

    Backward-compatible with dict-based ``ctx`` used by craft_review and policies.
    All progress mutations should go through ``record_tool_success`` so loop and
    registry do not double-write flags.
    """

    __slots__ = ("_data",)

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})

    # --- MutableMapping ---

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def data(self) -> dict[str, Any]:
        """Raw dict view for callers that still expect a plain mapping."""
        return self._data

    # --- Typed accessors ---

    @property
    def chapter_id(self) -> str:
        return str(self._data.get("chapter_id", "chapter_1"))

    @property
    def tool_profile(self) -> str:
        return str(self._data.get("tool_profile", "builder"))

    @property
    def chapter_context_read(self) -> bool:
        return bool(self._data.get("chapter_context_read"))

    @property
    def narrations_written(self) -> bool:
        return bool(self._data.get("narrations_written"))

    @property
    def index_tsx_written(self) -> bool:
        return bool(self._data.get("index_tsx_written"))

    @property
    def preflight_done(self) -> bool:
        return bool(self._data.get("preflight_done"))

    @property
    def review_ok(self) -> bool:
        return bool(self._data.get("review_ok"))

    @property
    def typecheck_ok(self) -> bool:
        return bool(self._data.get("typecheck_ok"))

    @property
    def vite_ok(self) -> bool:
        return bool(self._data.get("vite_ok"))

    def mark_chapter_context_read(self) -> None:
        self._data["chapter_context_read"] = True

    def mark_bundle_reviewed(self, *, review_ok: bool) -> None:
        self._data["bundle_reviewed"] = True
        self._data["review_ok"] = review_ok

    def mark_typecheck(self, *, ok: bool) -> None:
        self._data["typecheck_ok"] = ok

    def mark_vite(self, *, ok: bool) -> None:
        self._data["vite_ok"] = ok

    def record_tool_success(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Update progress flags after a successful (non-blocked) tool call."""
        if tool_name == "read_chapter_context":
            self.mark_chapter_context_read()
        elif tool_name == "write_narrations":
            self._data["narrations_written"] = True
        elif tool_name == "write_file":
            path = str(arguments.get("path", "")).replace("\\", "/")
            if path.endswith("index.tsx"):
                self._data["index_tsx_written"] = True
        elif tool_name == "craft_auto_check":
            self._data["preflight_done"] = True

    def apply_tool_outcome(
        self,
        result: Any,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Apply session side-effects from a structured tool result."""
        from .result import ToolResult

        if not isinstance(result, ToolResult):
            return
        if result.done or not result.ok or result.failed:
            return
        self.record_tool_success(tool_name, arguments)

    @classmethod
    def for_chapter(
        cls,
        *,
        chapter_id: str,
        chapter_index: int,
        tool_profile: str,
        workflow_state: Any,
        preset_review_ok: bool = False,
    ) -> ChapterSessionState:
        return cls({
            "chapter_id": chapter_id,
            "chapter_index": chapter_index,
            "tool_profile": tool_profile,
            "workflow_state": workflow_state,
            "review_ok": preset_review_ok,
            "typecheck_ok": False,
            "vite_ok": False,
        })
