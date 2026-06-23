"""Tests for dynamic build-step display labels."""

from harness.workflow.node_catalog import display_label_for_state, pending_build_chapter_index


def test_build_chapter_1_label():
    assert display_label_for_state("wv_build_chapter_1", {}) == "构建页面-第1章"


def test_build_chapter_n_label_advances():
    state = {"current_chapter_index": 2}
    assert pending_build_chapter_index(state) == 3
    assert display_label_for_state("wv_build_chapter_n", state) == "构建页面-第3章"


def test_build_chapter_n_label_rebuild_same_chapter():
    state = {
        "current_chapter_index": 2,
        "user_confirmations": {"checkpoint_chapter_n": {"approved": False}},
    }
    assert display_label_for_state("wv_build_chapter_n", state) == "构建页面-第2章"
