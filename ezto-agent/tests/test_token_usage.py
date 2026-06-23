"""Tests for token usage tracking."""

from harness.core.token_usage import empty_usage, merge_usage


def test_merge_usage_accumulates_by_model():
    usage = merge_usage(None, "deepseek-v4-flash", prompt_tokens=100, completion_tokens=50)
    usage = merge_usage(usage, "deepseek-v4-flash", prompt_tokens=200, completion_tokens=80)
    usage = merge_usage(usage, "deepseek-v4-pro", prompt_tokens=1000, completion_tokens=400)

    assert usage["by_model"]["deepseek-v4-flash"]["prompt_tokens"] == 300
    assert usage["by_model"]["deepseek-v4-flash"]["completion_tokens"] == 130
    assert usage["by_model"]["deepseek-v4-flash"]["calls"] == 2
    assert usage["by_model"]["deepseek-v4-pro"]["calls"] == 1
    assert usage["total"]["prompt_tokens"] == 1300
    assert usage["total"]["completion_tokens"] == 530
    assert usage["revision"] == 3


def test_empty_usage_shape():
    usage = empty_usage()
    assert usage["by_model"] == {}
    assert usage["total"]["calls"] == 0
