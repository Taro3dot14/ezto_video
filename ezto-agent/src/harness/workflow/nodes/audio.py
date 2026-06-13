"""Phase 3 — Audio Synthesis nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.logger import logger
from harness.core.state import VideoWorkflowState
from harness.workflow.interruptions import checkpoint_audio, checkpoint_audio_segments
from harness.services.tools.npm import run_npm


def wv_checkpoint_audio_node(state: VideoWorkflowState) -> dict:
    logger.info("Checkpoint Audio interrupt — asking user about audio synthesis")
    result = checkpoint_audio(state)
    response = result.get("user_confirmations", {}).get("checkpoint_audio", {})
    if isinstance(response, dict):
        choice = response.get("choice")
        result["synthesize_audio"] = choice == "yes"
        logger.info("Checkpoint Audio → choice=%s", choice)
    return result


def wv_extract_narrations(state: VideoWorkflowState) -> dict:
    cwd = Path(state.get("workspace_root", "."), "presentation")
    result = run_npm(state, "extract-narrations", cwd=cwd)
    updates: dict[str, Any] = {"current_node": "wv_extract_narrations"}
    if result.returncode != 0:
        updates["errors"] = [{"node": "wv_extract_narrations",
                              "error": f"extract-narrations failed: {result.stderr[:500]}"}]
    return updates


def wv_checkpoint_audio_segments_node(state: VideoWorkflowState) -> dict:
    return checkpoint_audio_segments(state)


def wv_synthesize_audio(state: VideoWorkflowState) -> dict:
    cwd = Path(state.get("workspace_root", "."), "presentation")
    result = run_npm(state, "synthesize-audio", cwd=cwd)
    updates: dict[str, Any] = {"current_node": "wv_synthesize_audio"}
    if result.returncode != 0:
        updates["errors"] = [{"node": "wv_synthesize_audio",
                              "error": f"synthesize-audio failed: {result.stderr[:500]}"}]
    return updates


def wv_report_audio_anomalies(state: VideoWorkflowState) -> dict:
    segments_path = state.get("artifact_paths", {}).get("audio-segments.json")
    anomalies = []
    if segments_path and Path(segments_path).exists():
        try:
            data = json.loads(Path(segments_path).read_text(encoding="utf-8"))
            segments = data if isinstance(data, list) else data.get("segments", [])
            for seg in segments:
                dur, txt = seg.get("estimated_duration_seconds", 0), len(seg.get("text", ""))
                if dur == 0 and txt > 0:
                    anomalies.append(f"Segment {seg.get('id', '?')}: zero duration")
        except (json.JSONDecodeError, KeyError) as e:
            anomalies.append(f"Parse error: {e}")
    updates: dict[str, Any] = {"current_node": "wv_report_audio_anomalies", "current_phase": "phase4"}
    if anomalies:
        updates["errors"] = [{"node": "wv_report_audio_anomalies",
                              "error": "Audio anomalies: " + "; ".join(anomalies[:5])}]
    return updates
