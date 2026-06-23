"""Canonical workflow node metadata — labels, phases, validation groups."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness.core.state import VideoWorkflowState

NODE_META: dict[str, dict[str, str]] = {
    "wv_identify_input": {"label": "识别输入类型", "phase": "phase1"},
    "wv_prepare_source_files": {"label": "生成口播稿和大纲", "phase": "phase1"},
    "wv_validate_script": {"label": "核对口播稿", "phase": "phase1", "group": "script"},
    "wv_repair_script": {"label": "润色口播稿", "phase": "phase1", "group": "script"},
    "wv_validate_outline": {"label": "核对大纲", "phase": "phase1", "group": "outline"},
    "wv_repair_outline": {"label": "调整大纲", "phase": "phase1", "group": "outline"},
    "wv_checkpoint_plan": {"label": "确认计划", "phase": "phase1"},
    "wv_scaffold_presentation": {"label": "页面初始化", "phase": "phase2"},
    "wv_build_chapter_1": {"label": "构建页面-第1章", "phase": "phase2"},
    "wv_checkpoint_chapter_1": {"label": "验收第 1 章", "phase": "phase2"},
    "wv_build_chapter_n": {"label": "构建页面", "phase": "phase2"},
    "wv_checkpoint_chapter_n": {"label": "验收章节", "phase": "phase2"},
    "wv_checkpoint_remaining_batch": {"label": "批量验收", "phase": "phase2"},
    "wv_transition_to_phase3": {"label": "进入音频阶段", "phase": "phase2"},
    "wv_checkpoint_audio": {"label": "是否合成音频", "phase": "phase3"},
    "wv_extract_narrations": {"label": "提取旁白", "phase": "phase3"},
    "wv_checkpoint_audio_segments": {"label": "检查音频分段", "phase": "phase3"},
    "wv_synthesize_audio": {"label": "合成音频", "phase": "phase3"},
    "wv_report_audio_anomalies": {"label": "音频异常报告", "phase": "phase3"},
    "wv_recording_guidance": {"label": "录屏指引", "phase": "phase4"},
}

GROUP_LABELS: dict[str, str] = {
    "script": "口播稿优化",
    "outline": "大纲优化",
}

TOTAL_NODES = len(NODE_META)


def meta(node_id: str) -> dict[str, str]:
    return NODE_META.get(node_id, {"label": node_id, "phase": "phase1"})


def display_label(node_id: str) -> str:
    m = meta(node_id)
    group = m.get("group")
    if group:
        return GROUP_LABELS.get(group, m["label"])
    return m["label"]


def pending_build_chapter_index(state: VideoWorkflowState) -> int:
    """Chapter number about to be built by wv_build_chapter_n."""
    ch_n_conf = state.get("user_confirmations", {}).get("checkpoint_chapter_n", {})
    batch_conf = state.get("user_confirmations", {}).get("checkpoint_remaining_batch", {})
    current = state.get("current_chapter_index", 1)
    if isinstance(ch_n_conf, dict) and ch_n_conf.get("approved") is False:
        return max(current, 2)
    if isinstance(batch_conf, dict) and batch_conf.get("approved") is False:
        return max(current, 2)
    return current + 1


def display_label_for_state(node_id: str, state: VideoWorkflowState) -> str:
    if node_id == "wv_build_chapter_1":
        return "构建页面-第1章"
    if node_id == "wv_build_chapter_n":
        return f"构建页面-第{pending_build_chapter_index(state)}章"
    return display_label(node_id)
