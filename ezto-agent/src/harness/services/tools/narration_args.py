"""Parse and normalize write_narrations tool arguments (incl. broken LLM JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

# Double quotes that break tool-call JSON or narrations.ts if left raw
_INLINE_QUOTE_CHARS = frozenset('"\u201c\u201d')


def normalize_narration_line(text: str) -> str:
    """Neutralize inline quotes → Chinese corner quotes 「」 (safe for JSON + narrations.ts)."""
    text = str(text)
    out: list[str] = []
    open_corner = True
    for ch in text:
        if ch in _INLINE_QUOTE_CHARS:
            out.append("「" if open_corner else "」")
            open_corner = not open_corner
        else:
            out.append(ch)
    return "".join(out)


def normalize_narration_lines(lines: list[Any]) -> list[str]:
    return [normalize_narration_line(str(line)) for line in lines]


def _decode_json_string_fragment(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _extract_quoted_array_strings(fragment: str) -> list[str]:
    """Pull string elements from a JSON array fragment (tolerates unescaped internal quotes)."""
    strings: list[str] = []
    i = 0
    n = len(fragment)
    while i < n:
        if fragment[i] != '"':
            i += 1
            continue
        i += 1
        buf: list[str] = []
        while i < n:
            ch = fragment[i]
            if ch == "\\":
                if i + 1 < n:
                    buf.append(ch)
                    buf.append(fragment[i + 1])
                    i += 2
                    continue
            if ch == '"':
                j = i + 1
                while j < n and fragment[j] in " \t\n\r":
                    j += 1
                if j >= n or fragment[j] in ",]":
                    strings.append(_decode_json_string_fragment("".join(buf)))
                    i = j
                    break
                buf.append(ch)
                i += 1
                continue
            buf.append(ch)
            i += 1
    return strings


def parse_write_narrations_raw(raw: str) -> dict[str, Any] | None:
    """Recover {chapter_id, lines} from malformed native-tool JSON."""
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        return None

    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and obj.get("chapter_id") and isinstance(obj.get("lines"), list):
            return {
                "chapter_id": str(obj["chapter_id"]),
                "lines": normalize_narration_lines(obj["lines"]),
            }
    except json.JSONDecodeError:
        pass

    cm = re.search(r'"chapter_id"\s*:\s*"([^"\\]+(?:\\.[^"\\]*)*)"', text)
    if not cm:
        return None
    chapter_id = _decode_json_string_fragment(cm.group(1))

    lm = re.search(r'"lines"\s*:\s*\[', text)
    if not lm:
        return None
    start = lm.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
        i += 1
    body = text[start : i - 1] if depth == 0 else text[start:]
    lines = _extract_quoted_array_strings(body)
    if not lines:
        return None
    return {"chapter_id": chapter_id, "lines": normalize_narration_lines(lines)}


def parse_write_narrations_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Resolve write_narrations args; recover from _raw when native JSON parsing failed."""
    if "_raw" in arguments:
        recovered = parse_write_narrations_raw(str(arguments["_raw"]))
        if recovered:
            return recovered
        return arguments

    out = dict(arguments)
    if "lines" in out and isinstance(out["lines"], list):
        out["lines"] = normalize_narration_lines(out["lines"])
    return out


def resolve_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "write_narrations":
        return parse_write_narrations_arguments(arguments)
    return arguments
