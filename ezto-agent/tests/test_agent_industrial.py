"""Tests for agent industrial optimizations."""

from harness.agent.tools.observations import shape_tool_output
from harness.agent.stall import StallDetector
from harness.workflow.chapter_policies import check_tool_guard, auto_validate_chapter
from pathlib import Path
import tempfile


def test_shape_typecheck_errors_only():
    raw = "✅ ok\n" + "\n".join(f"line {i}" for i in range(100))
    assert "line 99" not in shape_tool_output("typecheck", raw)

    err = "ok\nsrc/foo.tsx(10,5): error TS1003: blah\nwarn: something"
    shaped = shape_tool_output("typecheck", err)
    assert "error" in shaped.lower()
    assert len(shaped) < len(err)


def test_shape_write_file_short():
    out = "Written 500 chars to presentation/src/chapters/chapter_1/index.tsx"
    assert shape_tool_output("write_file", out) == out


def test_shape_read_file_uses_settings(monkeypatch):
    from configs import settings

    monkeypatch.setattr(settings, "agent_read_max_lines", 10)
    monkeypatch.setattr(settings, "agent_read_head_lines", 3)
    monkeypatch.setattr(settings, "agent_read_tail_lines", 2)

    output = "\n".join(f"line {i}" for i in range(20))
    shaped = shape_tool_output("read_file", output)

    assert "line 0" in shaped
    assert "line 1" in shaped
    assert "line 2" in shaped
    assert "line 18" in shaped
    assert "line 19" in shaped
    assert "line 10" not in shaped
    assert "[15 lines omitted]" in shaped


def test_shape_read_file_no_limit_when_max_lines_zero(monkeypatch):
    from configs import settings

    monkeypatch.setattr(settings, "agent_read_max_lines", 0)
    output = "\n".join(f"line {i}" for i in range(200))
    assert shape_tool_output("read_file", output) == output


def test_stall_detector():
    sd = StallDetector(window=4, repeat_threshold=2)
    sd.record("run_shell", {"command": "ls"})
    assert sd.check() is None
    sd.record("run_shell", {"command": "ls"})
    msg = sd.check()
    assert msg is not None
    assert "STALL" in msg


def test_stall_detector_allows_batch_read_file():
    sd = StallDetector(window=4, repeat_threshold=2)
    sd.record("read_file", {"path": "a.ts"})
    sd.record("read_file", {"path": "b.ts"})
    assert sd.check() is None


def test_normalize_presentation_command():
    from harness.services.tools.core.shell import normalize_presentation_command

    cmd = "grep -n 'foo' presentation/src/styles/base.css"
    normalized, hint = normalize_presentation_command(cmd)
    assert normalized == "grep -n 'foo' src/styles/base.css"
    assert hint is not None
    assert "presentation/" not in normalized.split()[-1] or normalized.endswith("src/styles/base.css")


def test_tool_guard_typecheck_blocked(tmp_path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    ctx = {"typecheck_ok": False}
    msg = check_tool_guard("typecheck", {}, ppt=ppt, chapter_id="chapter_1", ctx=ctx)
    assert msg and "BLOCKED" in msg


def test_auto_validate_step_mismatch(tmp_path):
    ppt = tmp_path / "presentation"
    ch = ppt / "src" / "chapters" / "chapter_1"
    ch.mkdir(parents=True)
    (ch / "narrations.ts").write_text(
        'export const narrations = [\n  "a",\n  "b",\n];\n', encoding="utf-8",
    )
    (ch / "index.tsx").write_text(
        "export default function X({ step }) {\n"
        "  if (step === 0) return <div/>;\n"
        "  if (step === 1) return <div/>;\n"
        "  if (step === 2) return <div/>;\n"
        "}\n",
        encoding="utf-8",
    )
    hint = auto_validate_chapter(ppt, "chapter_1")
    assert hint and "3" in hint
