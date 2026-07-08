"""Detect repetitive tool calls and suggest recovery."""

from __future__ import annotations

import json
from collections import deque
from typing import Any


class StallDetector:
    def __init__(self, window: int = 4, repeat_threshold: int = 2):
        self._history: deque[tuple[str, str]] = deque(maxlen=window)
        self._repeat_threshold = repeat_threshold

    def record(self, tool_name: str, arguments: dict[str, Any]) -> None:
        sig = self._signature(tool_name, arguments)
        self._history.append((tool_name, sig))

    def check(self) -> str | None:
        if len(self._history) < self._repeat_threshold:
            return None
        recent = list(self._history)[-self._repeat_threshold:]
        names = [r[0] for r in recent]
        sigs = [r[1] for r in recent]
        if len(set(sigs)) == 1:
            return (
                f"STALL DETECTED: `{names[0]}` called {self._repeat_threshold} times "
                f"with identical arguments. Try a different approach — use `edit_file` "
                f"for targeted fixes instead of re-running the same command."
            )
        if len(set(names)) == 1 and names[0] in (
            "run_shell", "read_file", "typecheck", "todolist_status",
        ):
            # Distinct arguments in the same tool = batch exploration, not a stall.
            if len(set(sigs)) >= self._repeat_threshold:
                return None
            return (
                f"STALL DETECTED: `{names[0]}` repeated {self._repeat_threshold} times. "
                f"Inspect the last error, use `edit_file` to fix the source, then re-verify."
            )
        return None

    @staticmethod
    def _signature(tool_name: str, arguments: dict[str, Any]) -> str:
        safe = {
            k: (f"<{len(v)}>" if k in ("content", "lines") and isinstance(v, (str, list)) else v)
            for k, v in arguments.items()
        }
        return json.dumps(safe, sort_keys=True, ensure_ascii=False)
