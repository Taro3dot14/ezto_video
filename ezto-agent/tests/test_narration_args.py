"""Tests for narration argument recovery and quote normalization."""

from harness.services.tools.narration_args import (
    normalize_narration_line,
    parse_write_narrations_arguments,
    parse_write_narrations_raw,
)
from harness.services.tools.narrations import build_narrations_content


def test_normalize_narration_line_corner_quotes():
    assert normalize_narration_line('典型的"自恋"翻车') == "典型的「自恋」翻车"
    assert normalize_narration_line("it's fine") == "it's fine"


def test_build_narrations_content_neutralizes_quotes():
    content = build_narrations_content(['典型的"自恋"翻车', "line two"])
    assert "「自恋」" in content


def test_parse_write_narrations_raw_valid_json():
    raw = '{"chapter_id": "intro", "lines": ["a", "b"]}'
    out = parse_write_narrations_raw(raw)
    assert out == {"chapter_id": "intro", "lines": ["a", "b"]}


def test_parse_write_narrations_raw_unescaped_internal_quotes():
    raw = (
        '{"chapter_id": "intro", "lines": ['
        '"Claude Code 新功能。", '
        '"典型的"自恋"翻车。", '
        '"第三段。"'
        "]}"
    )
    out = parse_write_narrations_raw(raw)
    assert out is not None
    assert out["chapter_id"] == "intro"
    assert len(out["lines"]) == 3
    assert "「自恋」" in out["lines"][1]


def test_parse_write_narrations_arguments_recovers_from_raw():
    broken = {
        "_raw": (
            '{"chapter_id": "intro", "lines": ['
            '"典型的"自恋"翻车"'
            "]}"
        ),
    }
    out = parse_write_narrations_arguments(broken)
    assert "_raw" not in out
    assert out["chapter_id"] == "intro"
    assert "「自恋」" in out["lines"][0]


def test_parse_write_narrations_arguments_normalizes_clean_args():
    out = parse_write_narrations_arguments({
        "chapter_id": "intro",
        "lines": ['典型的"自恋"翻车'],
    })
    assert out["lines"][0] == "典型的「自恋」翻车"
