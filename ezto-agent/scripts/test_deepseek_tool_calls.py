"""Smoke test: DeepSeek native tool calling via chat_with_tools."""

from __future__ import annotations

import json
import sys

from backend.core import llm
from configs import settings


def main() -> int:
    if not settings.deepseek_api_key:
        print("FAIL: DEEPSEEK_API_KEY not set")
        return 1

    tools = [
        {
            "type": "function",
            "function": {
                "name": "echo_greeting",
                "description": "Echo a greeting for a given name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Person name"},
                        "lang": {"type": "string", "description": "zh or en"},
                    },
                    "required": ["name"],
                },
            },
        }
    ]

    messages = [
        {"role": "user", "content": "请用 echo_greeting 工具向 Alice 打个中文招呼。"},
    ]

    print(f"model={settings.deepseek_model} base={settings.deepseek_base_url}")
    print("calling chat_with_tools...")

    try:
        result = llm.chat_with_tools(messages=messages, tools=tools, temperature=0.0, max_tokens=1024)
    except Exception as e:
        print(f"FAIL: API error: {e}")
        return 1

    print(f"content={result.content!r}")
    print(f"tool_calls={len(result.tool_calls)}")

    if not result.tool_calls:
        print("FAIL: model returned no tool_calls (native tool calling not triggered)")
        return 1

    tc = result.tool_calls[0]
    print(f"tool_name={tc.name}")
    print(f"tool_id={tc.id}")
    print(f"arguments={json.dumps(tc.arguments, ensure_ascii=False)}")

    if tc.name != "echo_greeting":
        print(f"FAIL: unexpected tool name {tc.name}")
        return 1
    if "name" not in tc.arguments:
        print("FAIL: arguments missing 'name'")
        return 1

    # Round-trip: send tool result back
    messages.append({
        "role": "assistant",
        "content": result.content,
        "tool_calls": [{
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
            },
        }],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": f"Greeting sent to {tc.arguments['name']}",
    })

    print("round-trip follow-up...")
    result2 = llm.chat_with_tools(messages=messages, tools=tools, temperature=0.0, max_tokens=512)
    final = (result2.content or "").encode("unicode_escape").decode("ascii")[:200]
    print(f"final_content={final!r}")

    if not result2.content:
        print("WARN: follow-up returned empty content (tool loop may still be OK)")

    print("PASS: DeepSeek native tool calling works")
    return 0


if __name__ == "__main__":
    sys.exit(main())
