"""Tests for agent parser."""

from harness.agent.tools.legacy_parser import extract_all, has_tool_call


def test_write_file_nested_json():
    raw = (
        "Some text\n"
        "```json\n"
        '{"tool": "write_file", "arguments": {"path": "presentation/src/chapters/chapter_1/index.tsx", '
        '"content": "import X\\nexport default function Foo() {}"}}\n'
        "```"
    )
    calls = extract_all(raw)
    assert len(calls) == 1
    assert calls[0][0] == "write_file"
    assert "import X" in calls[0][1]["content"]


def test_run_shell():
    raw = '```json\n{"tool": "run_shell", "arguments": {"command": "ls src/chapters/"}}\n```'
    calls = extract_all(raw)
    assert calls[0][1]["command"] == "ls src/chapters/"


def test_content_with_braces():
    raw = '```json\n{"tool": "write_file", "arguments": {"path": "a.tsx", "content": "const x = { a: 1 };"}}\n```'
    calls = extract_all(raw)
    assert "{ a: 1 }" in calls[0][1]["content"]


def test_write_narrations_tool():
    raw = '```json\n{"tool": "write_narrations", "arguments": {"chapter_id": "chapter_1", "lines": ["a", "b"]}}\n```'
    calls = extract_all(raw)
    assert calls[0][0] == "write_narrations"
    assert calls[0][1]["lines"] == ["a", "b"]
