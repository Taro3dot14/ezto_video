"""Tests for repair write guards."""

from pathlib import Path

from harness.workflow.artifacts import extract_repair_text, looks_like_repair_refusal, safe_repair_write


def test_extract_repair_text_strips_fence():
    raw = "```markdown\nhello\n---\nworld\n```"
    assert extract_repair_text(raw) == "hello\n---\nworld"


def test_looks_like_repair_refusal():
    assert looks_like_repair_refusal("请提供原始文章，我才能改写口播稿。")
    assert not looks_like_repair_refusal("第一句口播。\n---\n第二句口播。" * 20)


def test_safe_repair_write_rejects_empty(tmp_path: Path):
    path = tmp_path / "script.md"
    path.write_text("original script " * 50, encoding="utf-8")
    original = path.read_text(encoding="utf-8")
    text, wrote = safe_repair_write(path, original, "")
    assert wrote is False
    assert path.read_text(encoding="utf-8") == original


def test_safe_repair_write_rejects_refusal(tmp_path: Path):
    path = tmp_path / "script.md"
    original = "x" * 2000
    path.write_text(original, encoding="utf-8")
    text, wrote = safe_repair_write(path, original, "请提供脚本内容，Current script: 为空")
    assert wrote is False


def test_safe_repair_write_accepts_valid(tmp_path: Path):
    path = tmp_path / "script.md"
    original = "x" * 2000
    path.write_text(original, encoding="utf-8")
    repaired = ("短句口播。\n---\n" * 80)[:1500]
    text, wrote = safe_repair_write(path, original, repaired)
    assert wrote is True
    assert len(path.read_text(encoding="utf-8")) >= 500
