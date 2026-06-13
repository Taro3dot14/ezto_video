"""Phase 2 — Web Development nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from configs import settings
from backend.core.logger import logger
from harness.core.state import VideoWorkflowState, ValidationResult
from harness.workflow.guards import (
    require_ref_loaded,
    guard_chapter_refs_loaded,
    guard_chapter_1_not_parallel,
    guard_not_skip_checkpoint,
    check_artifact_contract,
)
from harness.workflow.interruptions import (
    checkpoint_chapter_1,
    checkpoint_chapter_n,
    checkpoint_remaining_batch,
)
from harness.services.tools.shell import run_shell
from harness.services.tools.scaffold import run_scaffold
from harness.services.tools.npm import run_npm, run_dev_server
from harness.agent.loop import WebBuildAgent, AgentResult
from harness.workflow.artifacts import (
    think,
    parse_outline_chapters,
    update_chapter_registry,
    _PPT_DIR,
)


def wv_scaffold_presentation(state: VideoWorkflowState) -> dict:
    guard_not_skip_checkpoint(state, "checkpoint_plan")
    confirmations = state.get("user_confirmations", {}).get("checkpoint_plan", {})
    theme = (state.get("selected_theme")
             or (isinstance(confirmations, dict) and confirmations.get("selected_theme"))
             or "midnight-press")

    logger.info("Scaffolding presentation with theme=%s", theme)
    result = run_scaffold(state, _PPT_DIR, theme)

    updates: dict[str, Any] = {"current_node": "wv_scaffold_presentation"}
    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[:500]
        logger.error("Scaffold failed (rc=%d): %s", result.returncode, stderr_tail)
        updates["errors"] = [{"node": "wv_scaffold_presentation",
                              "error": f"Scaffold failed: {stderr_tail}"}]
    else:
        logger.info("Scaffold completed OK, starting dev server…")
        try:
            target = Path(state.get("workspace_root", ".")) / _PPT_DIR
            port = settings.presentation_port
            run_dev_server(state, cwd=target, port=port)
            updates["presentation_url"] = f"http://localhost:{port}"
        except Exception as e:
            logger.warning("Could not start dev server: %s", e)
            updates["presentation_url"] = None
    return updates


def _ensure_dev_server(state: VideoWorkflowState) -> None:
    """如果 dev server 挂了，重启。"""
    import urllib.request
    url = state.get("presentation_url")
    if not url:
        return
    try:
        urllib.request.urlopen(f"{url}/?chapter=0", timeout=3)
    except Exception:
        logger.warning("Dev server at %s is dead, restarting...", url)
        target = Path(state.get("workspace_root", ".")) / _PPT_DIR
        port = settings.presentation_port
        run_dev_server(state, cwd=target, port=port)


def wv_remove_example_chapter(state: VideoWorkflowState) -> dict:
    guard_not_skip_checkpoint(state, "checkpoint_plan")
    example = Path(state.get("workspace_root", "."), _PPT_DIR, "src", "chapters", "01-example")
    if example.exists():
        run_shell(state, f"rm -rf \"{example.as_posix()}\"")
    return {"current_chapter_index": 1, "current_node": "wv_remove_example_chapter"}


def wv_build_chapter_1(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    guard_chapter_refs_loaded(state)
    guard_chapter_1_not_parallel(state)
    chapters = parse_outline_chapters(state)
    ch1 = chapters[0]
    ch_dir = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch1["id"]
    ch_dir.mkdir(parents=True, exist_ok=True)

    # 清理旧文件，确保 agent 不会以为自己已经做完了
    for old in ch_dir.glob("*"):
        old.unlink()

    tlog = think(None, "step", f"WebBuildAgent 构建第 1 章 {ch1['title']}…")
    logger.info("WebBuildAgent building chapter 1: %s — %s", ch1["id"], ch1["title"])

    agent = WebBuildAgent(state)
    result = agent.run(
        chapter_id=ch1["id"],
        title=ch1["title"],
        chapter_index=1,
        total_chapters=len(chapters),
    )

    if not result.success:
        logger.error("WebBuildAgent failed chapter 1 after %d iterations", result.iterations)
        think(tlog, "validation", f"❌ WebBuildAgent 失败：{result.content[:300]}")
        return {"errors": [{"node": "wv_build_chapter_1", "error": result.content[:500]}],
                "thinking_log": tlog, "current_node": "wv_build_chapter_1"}

    # 确认章节文件确实存在后再更新 registry
    tsx_path = ch_dir / "index.tsx"
    nar_path = ch_dir / "narrations.ts"
    if not tsx_path.exists() or not nar_path.exists():
        logger.warning("Agent succeeded but files missing: tsx=%s nar=%s", tsx_path.exists(), nar_path.exists())
        think(tlog, "validation", "⚠️ Agent 声称完成但文件未找到")
        return {"errors": [{"node": "wv_build_chapter_1", "error": "Files missing after agent build"}],
                "thinking_log": tlog, "current_node": "wv_build_chapter_1"}

    update_chapter_registry(state, chapters)
    think(tlog, "step", f"✅ 第 1 章构建完成（{result.iterations} 次迭代，{result.tool_calls} 次工具调用）")
    logger.info("Chapter 1 build OK: %d iterations, %d tool calls", result.iterations, result.tool_calls)
    return {"current_node": "wv_build_chapter_1",
            "created_files": [],
            "thinking_log": tlog}


def wv_checkpoint_chapter_1_node(state: VideoWorkflowState) -> dict:
    _ensure_dev_server(state)
    return checkpoint_chapter_1(state)


def wv_build_chapter_n(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    guard_chapter_refs_loaded(state)

    chapter_index = state.get("current_chapter_index", 1) + 1
    chapters = parse_outline_chapters(state)
    if chapter_index > len(chapters):
        logger.error("No more chapters to build (index=%d, total=%d)", chapter_index, len(chapters))
        return {"errors": [{"node": "wv_build_chapter_n",
                            "error": f"Invalid index: {chapter_index}/{len(chapters)}"}],
                "current_node": "wv_build_chapter_n"}

    ch = chapters[chapter_index - 1]
    ch_dir = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch["id"]
    ch_dir.mkdir(parents=True, exist_ok=True)
    # 清理旧文件
    for old in ch_dir.glob("*"):
        old.unlink()

    tlog = think(None, "step", f"WebBuildAgent 构建第 {chapter_index} 章 {ch['title']}…")
    logger.info("WebBuildAgent building chapter %d/%d: %s — %s",
                chapter_index, len(chapters), ch["id"], ch["title"])

    # Read previous chapters for style reference
    prev = []
    for i in range(1, chapter_index):
        p = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / chapters[i - 1]["id"] / "index.tsx"
        if p.exists():
            prev.append(f"Chapter {i}:\n{p.read_text(encoding='utf-8')[:2000]}")

    agent = WebBuildAgent(state)
    result = agent.run(
        chapter_id=ch["id"],
        title=ch["title"],
        chapter_index=chapter_index,
        total_chapters=len(chapters),
        previous_chapters="\n---\n".join(prev),
    )

    if not result.success:
        logger.error("WebBuildAgent failed chapter %d after %d iterations", chapter_index, result.iterations)
        think(tlog, "validation", f"❌ 第 {chapter_index} 章 WebBuildAgent 失败")
        return {"errors": [{"node": "wv_build_chapter_n", "error": result.content[:500]}],
                "thinking_log": tlog, "current_node": "wv_build_chapter_n"}

    # 确认章节文件存在后再更新 registry
    tsx_path = ch_dir / "index.tsx"
    nar_path = ch_dir / "narrations.ts"
    if not tsx_path.exists() or not nar_path.exists():
        logger.warning("Agent succeeded but files missing for ch%d: tsx=%s nar=%s",
                       chapter_index, tsx_path.exists(), nar_path.exists())
        think(tlog, "validation", "⚠️ Agent 声称完成但文件未找到")
        return {"errors": [{"node": "wv_build_chapter_n", "error": "Files missing after agent build"}],
                "thinking_log": tlog, "current_node": "wv_build_chapter_n"}

    update_chapter_registry(state, chapters)
    think(tlog, "step", f"✅ 第 {chapter_index} 章构建完成（{result.iterations} iter, {result.tool_calls} tools）")
    logger.info("Chapter %d build OK: %d iterations, %d tool calls",
                chapter_index, result.iterations, result.tool_calls)
    return {"current_node": "wv_build_chapter_n",
            "current_chapter_index": chapter_index,
            "total_chapters": len(chapters),
            "created_files": [],
            "thinking_log": tlog}


def wv_checkpoint_chapter_n_node(state: VideoWorkflowState) -> dict:
    _ensure_dev_server(state)
    return checkpoint_chapter_n(state, state.get("current_chapter_index", 2))


def wv_checkpoint_remaining_batch_node(state: VideoWorkflowState) -> dict:
    idx = state.get("current_chapter_index", 2)
    total = state.get("total_chapters", 0)
    return checkpoint_remaining_batch(state, list(range(idx, total + 1)))


def wv_transition_to_phase3(state: VideoWorkflowState) -> dict:
    guard_not_skip_checkpoint(state, "checkpoint_chapter_1")
    missing = check_artifact_contract(state, phase=2)
    updates: dict[str, Any] = {"current_node": "wv_transition_to_phase3", "current_phase": "phase3"}
    if missing:
        updates["errors"] = [{"node": "wv_transition_to_phase3",
                              "error": f"Missing artifacts: {missing}"}]
    return updates
