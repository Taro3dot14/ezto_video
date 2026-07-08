"""Legacy LLM text parser — extract tool calls from markdown JSON fences.

Used only when ``agent_use_native_tools=False``. Prefer native function calling.
"""

from __future__ import annotations

import json
import re
from typing import Any

from configs.settings import settings as _st
from harness.agent.tools.profiles import ALL_TOOL_NAMES

MAX_TOOL_JSON_LEN = _st.agent_tool_json_max_length

_TOOL_FENCE_RE = re.compile(
    r"```(?:tool|json)\s*\n?(.*?)```",
    re.DOTALL,
)
_CODE_FENCE_RE = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)

_KNOWN_TOOLS = ALL_TOOL_NAMES


def _extract_braced_json(text: str) -> str | None:
    """Extract a balanced {...} object, respecting quoted strings."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _is_tool_json_block(block: str) -> bool:
    return bool(re.search(r'"(?:name|tool)"\s*:', block[:200]))


def extract_all(raw: str) -> list[tuple[str, dict[str, Any]]]:
    results: list[tuple[str, dict[str, Any]]] = []

    for m in _TOOL_FENCE_RE.finditer(raw):
        block = m.group(1).strip()
        json_str = _extract_braced_json(block)
        if not json_str:
            continue
        if MAX_TOOL_JSON_LEN != -1 and len(json_str) > MAX_TOOL_JSON_LEN:
            continue
        if not _is_tool_json_block(json_str):
            continue
        parsed = _parse_json(json_str, raw)
        if parsed and parsed[0] in _KNOWN_TOOLS:
            results.append(parsed)

    if results:
        return results

    for m in _CODE_FENCE_RE.finditer(raw):
        block = m.group(1)
        if _is_tool_json_block(block):
            continue
        lines = block.split("\n")
        for i, line in enumerate(lines):
            for j in range(i + 1, len(lines)):
                pm = re.match(r"//\s*(.+)", lines[j].strip())
                if pm:
                    fp = pm.group(1).strip()
                    content = "\n".join(lines[j + 1 :]).strip()
                    if fp and content:
                        results.append(("write_file", {"path": fp, "content": content}))
                    break
            break

    return results


def try_extract(raw: str) -> tuple[str, dict[str, Any]] | None:
    all_calls = extract_all(raw)
    return all_calls[0] if all_calls else None


def has_tool_call(raw: str) -> bool:
    for m in _TOOL_FENCE_RE.finditer(raw):
        block = m.group(1).strip()
        json_str = _extract_braced_json(block)
        if json_str and _is_tool_json_block(json_str):
            return True
    for m in _CODE_FENCE_RE.finditer(raw):
        block = m.group(1)
        if _is_tool_json_block(block):
            continue
        for line in block.split("\n")[:10]:
            if re.match(r"//\s*.+", line.strip()):
                return True
    return False


def _parse_json(json_str: str, raw: str) -> tuple[str, dict[str, Any]] | None:
    for candidate in (json_str, _normalize(json_str)):
        try:
            tc = json.loads(candidate)
            name = tc.get("name") or tc.get("tool") or ""
            args = tc.get("arguments", {})
            if not isinstance(args, dict):
                args = {}
            if name == "write_file" and "content" in args:
                args["content"] = _fix_content(str(args["content"]), raw)
            if name in _KNOWN_TOOLS:
                return name, args
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return _fallback(_normalize(json_str), raw)


def _normalize(s: str) -> str:
    s = s.replace("{{", "{").replace("}}", "}")
    s = s.replace('"tool":', '"name":')
    s = re.sub(r",\s*([}\]])", r"\1", s)
    opens = s.count("{")
    closes = s.count("}")
    if opens > closes:
        s += "}" * (opens - closes)
    return s


def _get_real_code_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    for m in _CODE_FENCE_RE.finditer(raw):
        b = m.group(1).strip()
        if _is_tool_json_block(b):
            continue
        blocks.append(b)
    return blocks


def _fix_content(json_content: str, raw_response: str) -> str:
    if len(json_content) > 200 and (
        "export " in json_content or "import " in json_content
    ):
        return json_content
    blocks = _get_real_code_blocks(raw_response)
    if blocks:
        return blocks[-1].strip()
    return json_content


def _fallback(s: str, raw: str) -> tuple[str, dict[str, Any]] | None:
    tn = re.search(r'"(?:name|tool)"\s*:\s*"([^"]+)"', s)
    if not tn:
        return None
    tool_name = tn.group(1)
    if tool_name not in _KNOWN_TOOLS:
        return None
    arguments: dict[str, Any] = {}

    if tool_name == "run_shell":
        cm = re.search(r'"command":\s*"(.+)"\s*}', s, re.DOTALL)
        if cm:
            cmd = cm.group(1)
            while cmd.count('"') % 2 == 1 and cmd.endswith('"'):
                cmd = cmd[:-1]
            arguments["command"] = cmd.replace("\\n", "\n").replace('\\"', '"')
    elif tool_name == "write_file":
        pm = re.search(r'"path":\s*"([^"]+)"', s)
        if pm:
            arguments["path"] = pm.group(1)
        blocks = _get_real_code_blocks(raw)
        if blocks:
            arguments["content"] = blocks[-1].strip()
        elif '"content"' in s:
            cm = re.search(r'"content":\s*"(.*)"\s*}', s, re.DOTALL)
            if cm:
                arguments["content"] = (
                    cm.group(1)
                    .replace("\\n", "\n")
                    .replace('\\"', '"')
                    .replace("\\\\", "\\")
                )
    elif tool_name == "done":
        sm = re.search(r'"summary":\s*"(.*)"\s*}', s, re.DOTALL)
        if sm:
            arguments["summary"] = sm.group(1).replace("\\n", "\n")

    if not arguments:
        return None
    return tool_name, arguments
