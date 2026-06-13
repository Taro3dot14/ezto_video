"""StateGraph builder for the web-video-presentation workflow."""

from __future__ import annotations

import time

from langgraph.errors import GraphInterrupt
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.workflow.interruptions import set_interrupt_node
from harness.workflow.artifacts import think, parse_outline_chapters, get_repair_count, MAX_REPAIR_RETRIES

from .nodes.content import (
    wv_identify_input,
    wv_prepare_source_files,
    wv_validate_script,
    wv_repair_script,
    wv_validate_outline,
    wv_repair_outline,
    wv_checkpoint_plan_node,
)
from .nodes.web import (
    wv_scaffold_presentation,
    wv_remove_example_chapter,
    wv_build_chapter_1,
    wv_checkpoint_chapter_1_node,
    wv_build_chapter_n,
    wv_checkpoint_chapter_n_node,
    wv_checkpoint_remaining_batch_node,
    wv_transition_to_phase3,
)
from .nodes.audio import (
    wv_checkpoint_audio_node,
    wv_extract_narrations,
    wv_checkpoint_audio_segments_node,
    wv_synthesize_audio,
    wv_report_audio_anomalies,
)
from .nodes.recording import wv_recording_guidance


# ═══════════════════════════════════════════════════════════════════
# Route Functions
# ═══════════════════════════════════════════════════════════════════


def _last_validation_passed(state: VideoWorkflowState, node: str) -> bool:
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == node:
            return bool(v.get("passed", False))
    return True


def route_script_validation(state: VideoWorkflowState) -> str:
    if _last_validation_passed(state, "wv_validate_script"):
        return "wv_validate_outline"
    return "wv_repair_script" if get_repair_count(state, "script.md") < MAX_REPAIR_RETRIES else "wv_validate_outline"


def route_outline_validation(state: VideoWorkflowState) -> str:
    if _last_validation_passed(state, "wv_validate_outline"):
        return "wv_checkpoint_plan"
    return "wv_repair_outline" if get_repair_count(state, "outline.md") < MAX_REPAIR_RETRIES else "wv_checkpoint_plan"


def route_development_mode(state: VideoWorkflowState) -> str:
    chapters = parse_outline_chapters(state)
    return "wv_build_chapter_n" if len(chapters) >= 2 else "wv_transition_to_phase3"


def route_build_chapter_n(state: VideoWorkflowState) -> str:
    """路由：章节 N 构建完后 → 逐章 checkpoint 或批量 checkpoint 或结束"""
    ci = state.get("current_chapter_index", 2)
    total = state.get("total_chapters", 0)
    mode = state.get("selected_mode", "A")
    if mode == "A":
        return "wv_checkpoint_chapter_n"
    return "wv_checkpoint_remaining_batch" if ci >= total else "wv_build_chapter_n"


def route_mode_a_checkpoint(state: VideoWorkflowState) -> str:
    confirmations = state.get("user_confirmations", {}).get("checkpoint_chapter_n", {})
    should_continue = confirmations.get("continue", True) if isinstance(confirmations, dict) else True
    ci, total = state.get("current_chapter_index", 2), state.get("total_chapters", 0)
    return "wv_build_chapter_n" if (should_continue and ci < total) else "wv_transition_to_phase3"


def route_audio_decision(state: VideoWorkflowState) -> str:
    syn = state.get("synthesize_audio")
    if syn is True:
        return "wv_extract_narrations"
    if syn is False:
        return "wv_recording_guidance"
    c = state.get("user_confirmations", {}).get("checkpoint_audio", {})
    if isinstance(c, dict) and c.get("decision") == "yes":
        return "wv_extract_narrations"
    return "wv_recording_guidance"


# ═══════════════════════════════════════════════════════════════════
# Node Wrapper
# ═══════════════════════════════════════════════════════════════════


def _wrap_node(name: str, fn):
    """Wrap a node function to auto-track completed_nodes, push thinking events, and log."""

    def wrapped(state: VideoWorkflowState) -> dict:
        logger.info("▶ %s", name)
        t0 = time.perf_counter()

        tlog: list[dict] = []
        phase_labels = {"phase1": "内容编写", "phase2": "网页开发", "phase3": "音频合成", "phase4": "录屏"}
        phase = state.get("current_phase", "phase1")
        phase_cn = phase_labels.get(phase, phase)
        think(tlog, "node_start", f"[{phase_cn}] {name}")

        try:
            node_result = fn(state)
            elapsed = (time.perf_counter() - t0) * 1000

            node_thinking = node_result.pop("thinking_log", []) if isinstance(node_result, dict) else []
            result = dict(node_result) if isinstance(node_result, dict) else {"_raw": node_result}

            result["current_node"] = name

            completed = list(state.get("completed_nodes", []))
            if not completed or completed[-1] != name:
                completed.append(name)
            result["completed_nodes"] = completed

            if "current_phase" not in result:
                result["current_phase"] = state.get("current_phase", "phase1")

            # 保留 scaffold 设置的 presentation_url
            if "presentation_url" not in result and state.get("presentation_url"):
                result["presentation_url"] = state["presentation_url"]

            existing = state.get("thinking_log", [])
            think(tlog, "node_end", f"✓ {name} ({elapsed:.0f}ms)")
            result["thinking_log"] = existing + node_thinking + tlog

            logger.info("✓ %s done (%.0fms)", name, elapsed)
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            if isinstance(e, GraphInterrupt):
                logger.info("⏸ %s interrupted after %.0fms", name, elapsed)
                set_interrupt_node(name)
                raise
            think(tlog, "node_error", f"✗ {name}: {e}")
            existing = state.get("thinking_log", [])
            result = {"current_node": name, "thinking_log": existing + tlog}
            logger.error("✗ %s FAILED after %.0fms: %s", name, elapsed, e)
            raise

    return wrapped


# ═══════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════


def build_web_video_graph() -> StateGraph:
    builder = StateGraph(VideoWorkflowState)

    # Phase 1
    builder.add_node("wv_identify_input", _wrap_node("wv_identify_input", wv_identify_input))
    builder.add_node("wv_prepare_source_files", _wrap_node("wv_prepare_source_files", wv_prepare_source_files))
    builder.add_node("wv_validate_script", _wrap_node("wv_validate_script", wv_validate_script))
    builder.add_node("wv_repair_script", _wrap_node("wv_repair_script", wv_repair_script))
    builder.add_node("wv_validate_outline", _wrap_node("wv_validate_outline", wv_validate_outline))
    builder.add_node("wv_repair_outline", _wrap_node("wv_repair_outline", wv_repair_outline))
    builder.add_node("wv_checkpoint_plan", _wrap_node("wv_checkpoint_plan", wv_checkpoint_plan_node))

    # Phase 2
    builder.add_node("wv_scaffold_presentation", _wrap_node("wv_scaffold_presentation", wv_scaffold_presentation))
    builder.add_node("wv_remove_example_chapter", _wrap_node("wv_remove_example_chapter", wv_remove_example_chapter))
    builder.add_node("wv_build_chapter_1", _wrap_node("wv_build_chapter_1", wv_build_chapter_1))
    builder.add_node("wv_checkpoint_chapter_1", _wrap_node("wv_checkpoint_chapter_1", wv_checkpoint_chapter_1_node))
    builder.add_node("wv_build_chapter_n", _wrap_node("wv_build_chapter_n", wv_build_chapter_n))
    builder.add_node("wv_checkpoint_chapter_n", _wrap_node("wv_checkpoint_chapter_n", wv_checkpoint_chapter_n_node))
    builder.add_node("wv_checkpoint_remaining_batch", _wrap_node("wv_checkpoint_remaining_batch", wv_checkpoint_remaining_batch_node))
    builder.add_node("wv_transition_to_phase3", _wrap_node("wv_transition_to_phase3", wv_transition_to_phase3))

    # Phase 3
    builder.add_node("wv_checkpoint_audio", _wrap_node("wv_checkpoint_audio", wv_checkpoint_audio_node))
    builder.add_node("wv_extract_narrations", _wrap_node("wv_extract_narrations", wv_extract_narrations))
    builder.add_node("wv_checkpoint_audio_segments", _wrap_node("wv_checkpoint_audio_segments", wv_checkpoint_audio_segments_node))
    builder.add_node("wv_synthesize_audio", _wrap_node("wv_synthesize_audio", wv_synthesize_audio))
    builder.add_node("wv_report_audio_anomalies", _wrap_node("wv_report_audio_anomalies", wv_report_audio_anomalies))

    # Phase 4
    builder.add_node("wv_recording_guidance", _wrap_node("wv_recording_guidance", wv_recording_guidance))

    # ── Phase 1 edges ──
    builder.add_edge(START, "wv_identify_input")
    builder.add_edge("wv_identify_input", "wv_prepare_source_files")
    builder.add_edge("wv_prepare_source_files", "wv_validate_script")

    builder.add_conditional_edges("wv_validate_script", route_script_validation, {
        "wv_repair_script": "wv_repair_script",
        "wv_validate_outline": "wv_validate_outline",
    })
    builder.add_edge("wv_repair_script", "wv_validate_script")

    builder.add_conditional_edges("wv_validate_outline", route_outline_validation, {
        "wv_repair_outline": "wv_repair_outline",
        "wv_checkpoint_plan": "wv_checkpoint_plan",
    })
    builder.add_edge("wv_repair_outline", "wv_validate_outline")

    # ── Phase 2 edges ──
    builder.add_edge("wv_checkpoint_plan", "wv_scaffold_presentation")
    builder.add_edge("wv_scaffold_presentation", "wv_build_chapter_1")

    # Chapter 1: build → checkpoint (agent 内联自检，不再走 validate/repair 节点)
    builder.add_edge("wv_build_chapter_1", "wv_checkpoint_chapter_1")

    builder.add_edge("wv_checkpoint_chapter_1", "wv_remove_example_chapter")
    builder.add_conditional_edges("wv_remove_example_chapter", route_development_mode, {
        "wv_build_chapter_n": "wv_build_chapter_n",
        "wv_transition_to_phase3": "wv_transition_to_phase3",
    })

    # Chapter N loop: build → checkpoint (Mode A), or batch/continue (B/C)
    builder.add_conditional_edges("wv_build_chapter_n", route_build_chapter_n, {
        "wv_checkpoint_chapter_n": "wv_checkpoint_chapter_n",
        "wv_checkpoint_remaining_batch": "wv_checkpoint_remaining_batch",
        "wv_build_chapter_n": "wv_build_chapter_n",
    })

    builder.add_conditional_edges("wv_checkpoint_chapter_n", route_mode_a_checkpoint, {
        "wv_build_chapter_n": "wv_build_chapter_n",
        "wv_transition_to_phase3": "wv_transition_to_phase3",
    })
    builder.add_edge("wv_checkpoint_remaining_batch", "wv_transition_to_phase3")

    # ── Phase 3 edges ──
    builder.add_edge("wv_transition_to_phase3", "wv_checkpoint_audio")
    builder.add_conditional_edges("wv_checkpoint_audio", route_audio_decision, {
        "wv_extract_narrations": "wv_extract_narrations",
        "wv_recording_guidance": "wv_recording_guidance",
    })
    builder.add_edge("wv_extract_narrations", "wv_checkpoint_audio_segments")
    builder.add_edge("wv_checkpoint_audio_segments", "wv_synthesize_audio")
    builder.add_edge("wv_synthesize_audio", "wv_report_audio_anomalies")
    builder.add_edge("wv_report_audio_anomalies", "wv_recording_guidance")

    # ── Phase 4 end ──
    builder.add_edge("wv_recording_guidance", END)

    return builder.compile(checkpointer=MemorySaver())
