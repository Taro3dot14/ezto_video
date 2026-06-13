"""LLM 输出解析器 — 将 agent 的原始回复解析为结构化工具调用。

支持格式：
  ```json {"tool": "...", "arguments": {...}} ```
  ```tool {"name": "...", "arguments": {...}} ```
  <read_file><path>xxx</path></read_file>
"""

from __future__ import annotations

import json
import re
from typing import Any

_TOOL_FENCE_RE = re.compile(
    r"(?:```(?:tool|json))\s*\n?"
    r"(\{.*?\})"
    r"\n?\s*```",
    re.DOTALL,
)
_XML_TOOL_RE = re.compile(r"<(\w+)>\s*(.*?)\s*</\1>", re.DOTALL)
_XML_PARAM_RE = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)


def _code_blocks(raw: str) -> list[str]:
    blocks = []
    for m in _CODE_FENCE_RE.finditer(raw):
        b = m.group(1).strip()
        if b.startswith("{") and '"name"' in b[:80]:
            continue
        if b.startswith("{") and '"tool"' in b[:80]:
            continue
        blocks.append(b)
    return blocks


def extract_all(raw: str) -> list[tuple[str, dict[str, Any]]]:
    results: list[tuple[str, dict[str, Any]]] = []

    for m in _TOOL_FENCE_RE.finditer(raw):
        json_str = m.group(1).strip()
        if len(json_str) > 2000:
            continue
        # Must have "name" or "tool" top-level key
        if not re.search(r'"(?:name|tool)"\s*:', json_str):
            continue
        parsed = _parse_json(json_str, raw)
        if parsed and parsed[0] not in ("name", "_raw", ""):
            results.append(parsed)

    if not results:
        for m in _XML_TOOL_RE.finditer(raw):
            name, args = _parse_xml_block(m.group(1), m.group(2), raw)
            results.append((name, args))

    return results


def try_extract(raw: str) -> tuple[str, dict[str, Any]] | None:
    all_calls = extract_all(raw)
    return all_calls[0] if all_calls else None


def has_tool_call(raw: str) -> bool:
    return bool(_TOOL_FENCE_RE.search(raw)) or bool(_XML_TOOL_RE.search(raw))


def _parse_json(json_str: str, raw: str) -> tuple[str, dict[str, Any]] | None:
    fixed = _normalize(json_str)
    try:
        tc = json.loads(fixed)
        name = tc.get("name") or tc.get("tool") or ""
        args = tc.get("arguments", {})
        if name == "write_file" and "content" in args:
            args["content"] = _fix_content(args["content"], raw)
        return name, args
    except (json.JSONDecodeError, KeyError, TypeError):
        return _fallback(fixed, raw)


def _parse_xml_block(tool_name: str, body: str, raw: str) -> tuple[str, dict[str, Any]]:
    args: dict[str, Any] = {}
    for pm in _XML_PARAM_RE.finditer(body):
        args[pm.group(1)] = pm.group(2).strip()
    if tool_name == "write_file" and "content" in args:
        blocks = _code_blocks(raw)
        if blocks:
            args["content"] = blocks[-1].strip()
    return tool_name, args


def _normalize(s: str) -> str:
    s = s.replace("'", '"')
    s = s.replace("‘", '"').replace("’", '"')
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("{{", "{").replace("}}", "}")
    s = s.replace('"tool":', '"name":')
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(
        r'(?<=: ")(.*?)(?="\s*[,}\]])',
        lambda m: m.group(1).replace("\n", "\\n").replace("\r", ""),
        s, flags=re.DOTALL,
    )
    opens = s.count("{")
    closes = s.count("}")
    if opens > closes:
        s += "}" * (opens - closes)
    return s


def _fix_content(json_content: str, raw_response: str) -> str:
    blocks = _code_blocks(raw_response)
    if blocks:
        return blocks[-1].strip()
    return json_content


def _fallback(s: str, raw: str) -> tuple[str, dict[str, Any]] | None:
    tn = re.search(r'"(?:name|tool)"\s*:\s*"([^"]+)"', s)
    if not tn:
        return None
    tool_name = tn.group(1)
    arguments: dict[str, Any] = {}

    if tool_name == "run_shell":
        cm = re.search(r'"command":\s*"(.+)"\s*}', s)
        if cm:
            cmd = cm.group(1)
            while cmd.count('"') > 0 and cmd.endswith('"'):
                cmd = cmd[:-1]
            arguments["command"] = cmd
    elif tool_name == "write_file":
        pm = re.search(r'"path":\s*"([^"]+)"', s)
        if pm:
            arguments["path"] = pm.group(1)
        blocks = _code_blocks(raw)
        if blocks:
            arguments["content"] = blocks[-1].strip()
        else:
            arguments["content"] = s
    if not arguments:
        arguments = {"_raw": s}
    return tool_name, arguments
