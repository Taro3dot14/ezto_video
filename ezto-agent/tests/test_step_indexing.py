"""Tests for unified step indexing contract."""

from harness.workflow.step_indexing import (
    agent_invariant_line,
    annotate_outline_dev_plan,
    code_step_range,
    format_brief_step_plan,
    narrations_mismatch_hint,
    outline_step_to_code,
)
from harness.workflow.chapter_brief import format_brief_for_prompt


def test_outline_to_code_conversion():
    assert outline_step_to_code(1) == 0
    assert outline_step_to_code(5) == 4
    assert list(code_step_range(5)) == [0, 1, 2, 3, 4]


def test_annotate_outline_dev_plan():
    section = """**开发计划**：
- step 1 (~15s) — hero
- step 2 (~15s) — cards
"""
    out = annotate_outline_dev_plan(section)
    assert "[code step 0]" in out
    assert "outline step 1" in out
    assert "[code step 1]" in out
    assert "outline step 2" in out


def test_narrations_mismatch_detects_off_by_one():
    msg = narrations_mismatch_hint(nar_count=5, max_code_step=5)
    assert msg is not None
    assert "step === 0" in msg
    assert "step === 4" in msg


def test_format_brief_uses_unified_wording():
    brief = {
        "chapter_id": "coldopen",
        "expected_steps": 3,
        "outline_section": "- step 1 (~15s) — hero\n- step 2 (~15s) — b\n- step 3 (~15s) — c",
        "script_excerpt": "",
        "article_excerpt": "",
    }
    prompt = format_brief_for_prompt(brief, "Test")
    assert format_brief_step_plan(3).split("**")[1].startswith("3 screens")
    assert agent_invariant_line() in prompt
    assert "[code step 0]" in prompt
    assert "outline step 1" in prompt
    assert "Steps: outline labels vs code" in prompt
