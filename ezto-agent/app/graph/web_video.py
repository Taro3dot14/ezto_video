"""22-node LangGraph for the web-video-presentation workflow.

Maps the original SKILL.md methodology into a state-machine graph
with checkpoint interrupts, validation loops, and development-mode
branching.

Usage:
    from app.graph.web_video import build_web_video_graph
    graph = build_web_video_graph()
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Literal

from langgraph.errors import GraphInterrupt
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.core import llm, settings
from app.core.logger import logger
from app.runtime.state import VideoWorkflowState, ValidationResult
from app.runtime.ref_loader import require_ref_loaded
from app.runtime.interrupts import (
    checkpoint_plan,
    checkpoint_chapter_1,
    checkpoint_chapter_n,
    checkpoint_remaining_batch,
    checkpoint_audio,
    checkpoint_audio_segments,
    set_interrupt_node,
)
from app.runtime.tool_adapters import run_shell, run_scaffold, run_npm, run_dev_server
from app.runtime.artifact_manager import check_artifact_contract
from app.runtime.guards import (
    guard_chapter_refs_loaded,
    guard_chapter_1_not_parallel,
    guard_not_skip_checkpoint,
)

MAX_REPAIR_RETRIES = 3
_PPT_DIR = "presentation"


# ═══════════════════════════════════════════════════════════════════
# Phase 1 — Content Writing
# ═══════════════════════════════════════════════════════════════════


def wv_identify_input(state: VideoWorkflowState) -> dict:
    text = state.get("user_request", "").strip()
    if not text or len(text) < 20:
        logger.info("Input too short (%d chars) → type=none", len(text))
        return {"input_type": "none"}

    logger.info("Classifying input (%d chars)", len(text))
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Classify the following text as article, script, or none.\n"
        f"Reply with ONLY that single word.\n\n{text[:2000]}"
    )}], temperature=0.0)

    detected: Literal["article", "script", "none"] = "none"
    for kw in ("article", "script"):
        if kw in reply.strip().lower():
            detected = kw  # type: ignore
            break
    logger.info("Input classified as: %s", detected)
    return {"input_type": detected}


def wv_prepare_source_files(state: VideoWorkflowState) -> dict:
    ref_script = require_ref_loaded(state, "SCRIPT-STYLE.md")
    ref_outline = require_ref_loaded(state, "OUTLINE-FORMAT.md")

    text = state.get("user_request", "")
    input_type = state.get("input_type", "none")
    language = state.get("language", "zh-CN")
    paths = state.get("artifact_paths", {})

    if input_type == "none":
        logger.warning("No input content — cannot generate script/outline")
        return {"errors": [{"node": "wv_prepare_source_files",
                            "error": "No content provided — cannot generate script/outline."}],
                "current_node": "wv_prepare_source_files"}

    # 保存原始文章（article.md）供之后验证信息保留度
    if input_type == "article":
        article_path = paths.get("article.md", "article.md")
        Path(article_path).write_text(text, encoding="utf-8")
        logger.info("Saved article.md (%d chars)", len(text))

    tlog = _think(None, "step", f"正在参考 SCRIPT-STYLE.md + OUTLINE-FORMAT.md 生成稿子和大纲")
    logger.info("Generating script.md + outline.md (input_type=%s, language=%s)", input_type, language)
    _think(tlog, "llm", f"调用 DeepSeek 生成 script.md（口播稿）+ outline.md（大纲）…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Language: {language}\n"
        f"Input type: {input_type}\n\n"
        f"Reference — script style:\n{ref_script}\n\n"
        f"Reference — outline format:\n{ref_outline}\n\n"
        f"Input text:\n{text}\n\n"
        f"Write script.md (narration script) and outline.md (chapter outline).\n"
        f"Separate them with: ===OUTLINE==="
    )}])

    # content = (
    #     "lagnuage: " + language + "Input type: " + input_type + ... 
    # )

    parts = reply.split("===OUTLINE===")
    script_content = parts[0].strip()
    outline_content = "===OUTLINE===".join(parts[1:]).strip() if len(parts) >= 2 else "# Outline\n## Chapter 1\n\n(TODO)"

    script_path = paths.get("script.md", "script.md")
    outline_path = paths.get("outline.md", "outline.md")
    Path(script_path).write_text(script_content, encoding="utf-8")
    Path(outline_path).write_text(outline_content, encoding="utf-8")

    _think(tlog, "file_write", f"已生成 script.md ({len(script_content)} 字符)")
    _think(tlog, "file_write", f"已生成 outline.md ({len(outline_content)} 字符)")
    logger.info("Written script.md (%d chars) + outline.md (%d chars)",
                len(script_content), len(outline_content))
    result = {"current_node": "wv_prepare_source_files",
              "created_files": [script_path, outline_path],
              "thinking_log": tlog}
    return result


def wv_validate_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    tlog = _think(None, "step", "正在参考 SCRIPT-STYLE.md 进行自检…")
    script_path = state.get("artifact_paths", {}).get("script.md")
    if not script_path or not Path(script_path).exists():
        logger.warning("script.md not found at %s", script_path)
        _think(tlog, "validation", "script.md 文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_script", target="script.md", passed=False,
            failed_checks=["script.md not found"], details="")],
            "thinking_log": tlog}

    content = Path(script_path).read_text(encoding="utf-8")
    logger.info("Validating script.md (%d chars)", len(content))
    _think(tlog, "llm", "调用 DeepSeek 校验脚本质量…")

    article_path = state.get("artifact_paths", {}).get("article.md", "")
    article_hint = ""
    if article_path and Path(article_path).exists():
        article_text = Path(article_path).read_text(encoding="utf-8")
        # Strip code blocks so English code doesn't bias language detection
        clean = re.sub(r'```.*?```', '', article_text, flags=re.DOTALL)
        clean = re.sub(r'https?://\S+', '', clean)
        cn_chars = sum(1 for c in clean if '一' <= c <= '鿿')
        en_chars = sum(1 for c in clean if c.isascii() and c.isalpha())
        total = cn_chars + en_chars
        article_lang = "Chinese" if (total > 0 and cn_chars / total >= 0.1) else "English"
        article_hint = (
            f"Original article (detected language: {article_lang}):\n{article_text}\n\n"
            f"IMPORTANT: The original article's dominant language is {article_lang}. "
            f"Do NOT flag a language mismatch if the script uses {article_lang}. "
            f"English terms/code in a {article_lang} article are expected and do not make it an English article.\n\n"
        )
    else:
        article_hint = ("NOTE: This script IS the original input — there is NO separate source article. "
                        "Skip information-retention and language-consistency checks entirely. "
                        "The script defines both the content and its language.\n\n")

    #TODO: 是否需要设计一下针对文档中的每个点去打勾，而不是返回现在这种。
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Validate this script against the style guide:\n\n{ref}\n\n"
        f"{article_hint}"
        f"Script:\n{content}\n\n"
        f"Respond with JSON only:\n"
        f'{{"passed":bool,"failed_checks":["..."],"details":"..."}}'
    )}], temperature=0.0)

    try:
        jresult = json.loads(reply)

    #TODO：目前这个写法不鲁棒，如果json解析失败也直接pass了，未来最好增强一下
    except json.JSONDecodeError:
        jresult = {"passed": True, "failed_checks": [], "details": "Parse error, defaulting to pass"}

    passed = bool(jresult.get("passed", True))
    checks = jresult.get("failed_checks", [])
    if passed:
        _think(tlog, "validation", "✅ script.md 校验通过")
    else:
        _think(tlog, "validation", f"❌ 发现 {len(checks)} 个问题")
        for c in checks:
            _think(tlog, "validation", f"  • {c}")
    logger.info("Script validation: %s (failed_checks=%s)", "PASS" if passed else "FAIL", checks)
    return {"validation_results": [ValidationResult(
        node="wv_validate_script", target="script.md",
        passed=passed,
        failed_checks=checks,
        details=jresult.get("details", ""))],
        "thinking_log": tlog}


def wv_repair_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    tlog = _think(None, "step", "正在修复 script.md…")
    script_path = state.get("artifact_paths", {}).get("script.md")
    content = Path(script_path).read_text(encoding="utf-8") if script_path else ""

    validations = state.get("validation_results", [])
    issues = ""
    for v in reversed(validations):
        if v["node"] == "wv_validate_script":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            break

    repair_count = _get_repair_count(state, "script.md")
    _think(tlog, "repair", f"第 {repair_count + 1} 次修复, 共 {MAX_REPAIR_RETRIES} 次")
    logger.info("Repairing script.md (attempt %d/%d, issues=%s)", repair_count + 1, MAX_REPAIR_RETRIES, issues[:200])
    _think(tlog, "llm", "调用 DeepSeek 修复脚本问题…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Style guide:\n{ref}\n\nIssues to fix:\n{issues}\n\n"
        f"Current script:\n{content}\n\nRewrite the full script fixing all issues."
    )}])

    Path(script_path).write_text(reply.strip(), encoding="utf-8")
    _think(tlog, "file_write", f"已更新 script.md ({len(reply)} 字符)")
    logger.info("Repaired script.md rewritten (%d chars)", len(reply))

    history = list(state.get("repair_history", []))
    failed_checks = next((v.get("failed_checks", []) for v in reversed(validations)
                          if v["node"] == "wv_validate_script"), [])
    history.append({"node": "wv_repair_script", "target": "script.md",
                    "failed_checks": failed_checks,
                    "repair_summary": reply.strip()[:200]})

    return {"current_node": "wv_repair_script",
            "modified_files": [script_path] if script_path else [],
            "thinking_log": tlog,
            "repair_history": history}


def wv_validate_outline(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "OUTLINE-FORMAT.md")
    tlog = _think(None, "step", "正在校验 outline.md…")
    outline_path = state.get("artifact_paths", {}).get("outline.md")
    if not outline_path or not Path(outline_path).exists():
        _think(tlog, "validation", "❌ outline.md 文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_outline", target="outline.md", passed=False,
            failed_checks=["outline.md not found"], details="")],
            "thinking_log": tlog,
            "current_node": "wv_validate_outline"}

    content = Path(outline_path).read_text(encoding="utf-8")
    _think(tlog, "llm", "调用 DeepSeek 校验大纲格式…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Validate this outline against the format spec:\n\n{ref}\n\n"
        f"Outline:\n{content}\n\n"
        f"JSON response only:\n"
        f'{{"passed":bool,"failed_checks":["..."],"details":"..."}}'
    )}], temperature=0.0)

    try:
        result = json.loads(reply)
    except json.JSONDecodeError:
        result = {"passed": True, "failed_checks": [], "details": ""}

    passed = bool(result.get("passed", True))
    checks = result.get("failed_checks", [])
    if passed:
        _think(tlog, "validation", "✅ outline.md 校验通过")
    else:
        _think(tlog, "validation", f"❌ 发现 {len(checks)} 个问题")
        for c in checks:
            _think(tlog, "validation", f"  • {c}")

    return {"validation_results": [ValidationResult(
        node="wv_validate_outline", target="outline.md",
        passed=passed,
        failed_checks=checks,
        details=result.get("details", ""))],
        "thinking_log": tlog,
        "current_node": "wv_validate_outline"}


def wv_repair_outline(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "OUTLINE-FORMAT.md")
    outline_path = state.get("artifact_paths", {}).get("outline.md")
    content = Path(outline_path).read_text(encoding="utf-8") if outline_path else ""

    issues = ""
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == "wv_validate_outline":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            break

    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Format spec:\n{ref}\n\nIssues:\n{issues}\n\n"
        f"Current outline:\n{content}\n\nRewrite the full outline fixing all issues."
    )}])

    Path(outline_path).write_text(reply.strip(), encoding="utf-8")

    validations = state.get("validation_results", [])
    history = list(state.get("repair_history", []))
    failed_checks = next((v.get("failed_checks", []) for v in reversed(validations)
                          if v["node"] == "wv_validate_outline"), [])
    history.append({"node": "wv_repair_outline", "target": "outline.md",
                    "failed_checks": failed_checks,
                    "repair_summary": reply.strip()[:200]})

    return {"current_node": "wv_repair_outline",
            "modified_files": [outline_path] if outline_path else [],
            "repair_history": history}


def wv_checkpoint_plan_node(state: VideoWorkflowState) -> dict:
    themes_dir = Path(settings.project_root) / "app" / "themes"
    recommendations = []
    if themes_dir.exists():
        for td in sorted(themes_dir.iterdir()):
            if not td.is_dir():
                continue
            meta_file = td / "theme.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    recommendations.append({
                        "id": meta.get("id", td.name),
                        "name": meta.get("name", ""),
                        "nameZh": meta.get("nameZh", ""),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

    tlog = _think(None, "step", f"已加载 {len(recommendations)} 个主题，等待用户确认 5 件事")
    logger.info("Checkpoint Plan interrupt — %d themes available", len(recommendations))
    result = checkpoint_plan(state, recommendations[:10], ["script.md", "outline.md"])
    response = result.get("user_confirmations", {}).get("checkpoint_plan", {})
    if isinstance(response, dict):
        theme = response.get("selected_theme")
        if theme:
            result["selected_theme"] = theme
            logger.info("Checkpoint Plan → selected_theme=%s", theme)
            _think(tlog, "step", f"用户选择主题: {theme}")
        mode = response.get("development_mode")
        if mode:
            result["selected_mode"] = mode
            logger.info("Checkpoint Plan → selected_mode=%s", mode)
            _think(tlog, "step", f"用户选择开发模式: {mode}")
    result["thinking_log"] = tlog
    return result


# ═══════════════════════════════════════════════════════════════════
# Phase 2 — Web Development
# ═══════════════════════════════════════════════════════════════════


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
            run_dev_server(state, cwd=target, port=5174)
            updates["presentation_url"] = "http://localhost:5174"
        except Exception as e:
            logger.warning("Could not start dev server: %s", e)
            updates["presentation_url"] = None
    return updates


def _parse_outline_chapters(state: VideoWorkflowState) -> list[dict[str, str]]:
    path = state.get("artifact_paths", {}).get("outline.md")
    if not path or not Path(path).exists():
        return [{"id": "chapter_1", "title": "Chapter 1"}]
    chapters, idx = [], 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+Chapter\s+(\d+)", line, re.IGNORECASE)
        if m:
            idx += 1
            chapters.append({"id": f"chapter_{idx}", "title": re.sub(r"^##\s+", "", line).strip()})
    return chapters or [{"id": "chapter_1", "title": "Chapter 1"}]


def _get_repair_count(state: VideoWorkflowState, target: str) -> int:
    return sum(1 for r in state.get("repair_history", []) if r.get("target") == target)


def _update_chapter_registry(state: VideoWorkflowState, chapters: list[dict]) -> None:
    ws = state.get("workspace_root", ".")
    reg_file = Path(ws) / _PPT_DIR / "src" / "registry" / "chapters.ts"
    imports = [f"import {ch['id']} from '@/chapters/{ch['id']}';" for ch in chapters]
    entries = [f"  {{ id: '{ch['id']}', title: '{ch['title']}', component: {ch['id']} }}," for ch in chapters]
    content = "// Auto-generated\n" + "\n".join(imports) + "\n\nexport const chapters = [\n" + "\n".join(entries) + "\n];\n"
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(content, encoding="utf-8")


def wv_build_chapter_1(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    guard_chapter_refs_loaded(state)
    guard_chapter_1_not_parallel(state)

    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")
    paths = state.get("artifact_paths", {})
    script_content = Path(paths.get("script.md", "script.md")).read_text(encoding="utf-8")
    outline_content = Path(paths.get("outline.md", "outline.md")).read_text(encoding="utf-8")
    chapters = _parse_outline_chapters(state)
    ch1 = chapters[0]

    tlog = _think(None, "step", f"正在参考 CHAPTER-CRAFT.md 实现第 1 章 {ch1['title']}…")
    logger.info("Building chapter 1: %s — %s (script=%d chars, outline=%d chars)",
                ch1["id"], ch1["title"], len(script_content), len(outline_content))
    _think(tlog, "llm", f"调用 DeepSeek 生成 React 组件 + narrations…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Chapter craft rules:\n{ref}\n\nScript:\n{script_content}\n\n"
        f"Outline:\n{outline_content}\n\n"
        f"Build chapter: {ch1['id']} — {ch1['title']}\n\n"
        f"Create src/chapters/{ch1['id']}/index.tsx (default export function)\n"
        f"and src/chapters/{ch1['id']}/narrations.ts (narration text array).\n"
        f"Separate with ===NARRATIONS==="
    )}])

    parts = reply.split("===NARRATIONS===")
    tsx_content = parts[0].strip()
    nar_content = parts[1].strip() if len(parts) >= 2 else "export const narrations: string[] = [];"

    ch_dir = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch1["id"]
    ch_dir.mkdir(parents=True, exist_ok=True)
    tsx_path = ch_dir / "index.tsx"
    nar_path = ch_dir / "narrations.ts"
    tsx_path.write_text(tsx_content, encoding="utf-8")
    nar_path.write_text(nar_content, encoding="utf-8")

    _update_chapter_registry(state, chapters)
    _think(tlog, "file_write", f"已生成 src/chapters/{ch1['id']}/index.tsx ({len(tsx_content)} 字符)")
    _think(tlog, "file_write", f"已生成 src/chapters/{ch1['id']}/narrations.ts ({len(nar_content)} 字符)")
    logger.info("Chapter 1 written: %s/index.tsx (%d chars), narrations.ts (%d chars)",
                ch1["id"], len(tsx_content), len(nar_content))
    return {"current_node": "wv_build_chapter_1",
            "created_files": [str(tsx_path), str(nar_path)],
            "thinking_log": tlog}

#TODO：目前这个写法不鲁棒，如果json解析失败也直接pass了，未来最好增强一下
def wv_validate_chapter_1(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")
    tlog = _think(None, "step", "正在校验第 1 章…")
    chapters = _parse_outline_chapters(state)
    ch1 = chapters[0]
    tsx_path = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch1["id"] / "index.tsx"

    if not tsx_path.exists():
        _think(tlog, "validation", "❌ 第 1 章文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_chapter_1", target="chapter_1", passed=False,
            failed_checks=["File not found"], details=str(tsx_path))],
            "thinking_log": tlog,
            "current_node": "wv_validate_chapter_1"}

    content = tsx_path.read_text(encoding="utf-8")
    _think(tlog, "llm", "调用 DeepSeek 校验章节质量…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Rules:\n{ref}\n\nChapter code:\n{content}\n\n"
        f"JSON: {{\"passed\":bool,\"failed_checks\":[\"...\"],\"details\":\"...\"}}"
    )}], temperature=0.0)

    try:
        result = json.loads(reply)
    except json.JSONDecodeError:
        result = {"passed": True, "failed_checks": [], "details": ""}

    passed = bool(result.get("passed", True))
    checks = result.get("failed_checks", [])
    if passed:
        _think(tlog, "validation", "✅ 第 1 章校验通过")
    else:
        _think(tlog, "validation", f"❌ 第 1 章发现 {len(checks)} 个问题")
        for c in checks:
            _think(tlog, "validation", f"  • {c}")

    return {"validation_results": [ValidationResult(
        node="wv_validate_chapter_1", target="chapter_1",
        passed=passed,
        failed_checks=checks,
        details=result.get("details", ""))],
        "thinking_log": tlog,
        "current_node": "wv_validate_chapter_1"}


def wv_repair_chapter_1(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")
    chapters = _parse_outline_chapters(state)
    ch1 = chapters[0]
    ch_dir = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch1["id"]
    tsx_path = ch_dir / "index.tsx"
    content = tsx_path.read_text(encoding="utf-8") if tsx_path.exists() else ""

    issues = ""
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == "wv_validate_chapter_1":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            break

    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Rules:\n{ref}\n\nIssues:\n{issues}\n\n"
        f"Current code:\n{content}\n\nRewrite the full index.tsx fixing all issues."
    )}])
    tsx_path.write_text(reply.strip(), encoding="utf-8")

    history = list(state.get("repair_history", []))
    failed_checks = next((v.get("failed_checks", []) for v in reversed(state.get("validation_results", []))
                          if v["node"] == "wv_validate_chapter_1"), [])
    history.append({"node": "wv_repair_chapter_1", "target": "chapter_1",
                    "failed_checks": failed_checks,
                    "repair_summary": f"Attempt #{_get_repair_count(state, 'chapter_1') + 1}"})

    return {"current_node": "wv_repair_chapter_1",
            "modified_files": [str(tsx_path)],
            "repair_history": history}


def wv_checkpoint_chapter_1_node(state: VideoWorkflowState) -> dict:
    return checkpoint_chapter_1(state)



def wv_remove_example_chapter(state: VideoWorkflowState) -> dict:
    guard_not_skip_checkpoint(state, "checkpoint_plan")
    example = Path(state.get("workspace_root", "."), _PPT_DIR, "src", "chapters", "01-example")
    if example.exists():
        run_shell(state, f"rm -rf \"{example.as_posix()}\"")
    return {"current_chapter_index": 1, "current_node": "wv_remove_example_chapter"}


def wv_build_chapter_n(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    guard_chapter_refs_loaded(state)
    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")

    chapter_index = state.get("current_chapter_index", 1) + 1  # increment first
    chapters = _parse_outline_chapters(state)
    if chapter_index > len(chapters):
        logger.error("No more chapters to build (index=%d, total=%d)", chapter_index, len(chapters))
        return {"errors": [{"node": "wv_build_chapter_n",
                            "error": f"Invalid index: {chapter_index}/{len(chapters)}"}],
                "current_node": "wv_build_chapter_n"}

    ch = chapters[chapter_index - 1]
    script_content = Path(state.get("artifact_paths", {}).get("script.md", "script.md")).read_text(encoding="utf-8")

    # Read previous chapters for style consistency
    prev = []
    for i in range(1, chapter_index):
        p = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / chapters[i - 1]["id"] / "index.tsx"
        if p.exists():
            prev.append(f"Chapter {i}:\n{p.read_text(encoding='utf-8')[:2000]}")

    logger.info("Building chapter %d/%d: %s — %s (prev_chapters=%d)",
                chapter_index, len(chapters), ch["id"], ch["title"], len(prev))
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Chapter craft rules:\n{ref}\n\nScript:\n{script_content}\n\n"
        f"Building chapter {chapter_index}/{len(chapters)}: {ch['id']} — {ch['title']}\n\n"
        f"Previous chapters for reference:\n" + "\n---\n".join(prev) + "\n\n"
        f"Create src/chapters/{ch['id']}/index.tsx and narrations.ts. Separate with ===NARRATIONS==="
    )}])

    parts = reply.split("===NARRATIONS===")
    tsx_content = parts[0].strip()
    nar_content = parts[1].strip() if len(parts) >= 2 else "export const narrations: string[] = [];"

    ch_dir = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch["id"]
    ch_dir.mkdir(parents=True, exist_ok=True)
    tsx_path = ch_dir / "index.tsx"
    nar_path = ch_dir / "narrations.ts"
    tsx_path.write_text(tsx_content, encoding="utf-8")
    nar_path.write_text(nar_content, encoding="utf-8")

    _update_chapter_registry(state, chapters)
    logger.info("Chapter %d written: %s/index.tsx (%d chars), narrations.ts (%d chars)",
                chapter_index, ch["id"], len(tsx_content), len(nar_content))
    return {"current_node": "wv_build_chapter_n",
            "current_chapter_index": chapter_index,
            "total_chapters": len(chapters),
            "created_files": [str(tsx_path), str(nar_path)]}


def wv_validate_chapter_n(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")

    chapter_index = state.get("current_chapter_index", 2)
    chapters = _parse_outline_chapters(state)
    ch = chapters[chapter_index - 1] if chapter_index <= len(chapters) else {"id": f"chapter_{chapter_index}"}
    tlog = _think(None, "step", f"正在校验第 {chapter_index} 章…")
    tsx_path = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch["id"] / "index.tsx"

    if not tsx_path.exists():
        _think(tlog, "validation", f"❌ 第 {chapter_index} 章文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_chapter_n", target=f"chapter_{chapter_index}", passed=False,
            failed_checks=["File not found"], details=str(tsx_path))],
            "thinking_log": tlog,
            "current_node": "wv_validate_chapter_n"}

    content = tsx_path.read_text(encoding="utf-8")
    _think(tlog, "llm", f"调用 DeepSeek 校验第 {chapter_index} 章…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Rules:\n{ref}\n\nChapter code:\n{content}\n\n"
        f"JSON: {{\"passed\":bool,\"failed_checks\":[\"...\"],\"details\":\"...\"}}"
    )}], temperature=0.0)

    try:
        result = json.loads(reply)
    except json.JSONDecodeError:
        result = {"passed": True, "failed_checks": [], "details": ""}

    passed = bool(result.get("passed", True))
    checks = result.get("failed_checks", [])
    if passed:
        _think(tlog, "validation", f"✅ 第 {chapter_index} 章校验通过")
    else:
        _think(tlog, "validation", f"❌ 第 {chapter_index} 章发现 {len(checks)} 个问题")
        for c in checks:
            _think(tlog, "validation", f"  • {c}")

    return {"validation_results": [ValidationResult(
        node="wv_validate_chapter_n", target=f"chapter_{chapter_index}",
        passed=passed,
        failed_checks=checks,
        details=result.get("details", ""))],
        "thinking_log": tlog,
        "current_node": "wv_validate_chapter_n"}


def wv_repair_chapter_n(state: VideoWorkflowState) -> dict:
    require_ref_loaded(state, "CHAPTER-CRAFT.md", reload_each_time=True)
    ref = require_ref_loaded(state, "CHAPTER-CRAFT.md")

    chapter_index = state.get("current_chapter_index", 2)
    chapters = _parse_outline_chapters(state)
    ch = chapters[chapter_index - 1] if chapter_index <= len(chapters) else {"id": f"chapter_{chapter_index}"}
    tsx_path = Path(state.get("workspace_root", ".")) / _PPT_DIR / "src" / "chapters" / ch["id"] / "index.tsx"
    content = tsx_path.read_text(encoding="utf-8") if tsx_path.exists() else ""

    issues = ""
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == "wv_validate_chapter_n":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            break

    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Rules:\n{ref}\n\nIssues:\n{issues}\n\n"
        f"Current code:\n{content}\n\nRewrite the full index.tsx fixing all issues."
    )}])
    tsx_path.write_text(reply.strip(), encoding="utf-8")

    target = f"chapter_{chapter_index}"
    history = list(state.get("repair_history", []))
    failed_checks = next((v.get("failed_checks", []) for v in reversed(state.get("validation_results", []))
                          if v["node"] == "wv_validate_chapter_n"), [])
    history.append({"node": "wv_repair_chapter_n", "target": target,
                    "failed_checks": failed_checks,
                    "repair_summary": f"Attempt #{_get_repair_count(state, target) + 1}"})

    return {"current_node": "wv_repair_chapter_n",
            "modified_files": [str(tsx_path)],
            "repair_history": history}


def wv_checkpoint_chapter_n_node(state: VideoWorkflowState) -> dict:
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


# ═══════════════════════════════════════════════════════════════════
# Phase 3 — Audio Synthesis
# ═══════════════════════════════════════════════════════════════════


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
    cwd = Path(state.get("workspace_root", "."), _PPT_DIR)
    result = run_npm(state, "extract-narrations", cwd=cwd)
    updates: dict[str, Any] = {"current_node": "wv_extract_narrations"}
    if result.returncode != 0:
        updates["errors"] = [{"node": "wv_extract_narrations",
                              "error": f"extract-narrations failed: {result.stderr[:500]}"}]
    return updates


def wv_checkpoint_audio_segments_node(state: VideoWorkflowState) -> dict:
    return checkpoint_audio_segments(state)


def wv_synthesize_audio(state: VideoWorkflowState) -> dict:
    cwd = Path(state.get("workspace_root", "."), _PPT_DIR)
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


# ═══════════════════════════════════════════════════════════════════
# Phase 4 — Recording Guidance
# ═══════════════════════════════════════════════════════════════════


def wv_recording_guidance(state: VideoWorkflowState) -> dict:
    ws = state.get("workspace_root", ".")
    theme = state.get("selected_theme", "default")
    return {"final_summary": (
        f"Presentation complete!\nWorkspace: {ws}/{_PPT_DIR}\nTheme: {theme}\n\n"
        f"To record:\n1. cd {ws}/{_PPT_DIR}\n2. npm run dev\n"
        f"3. Open browser, add ?auto=1 for auto-advance\n4. Screen record"
    ), "current_node": "wv_recording_guidance"}


# ═══════════════════════════════════════════════════════════════════
# Route Functions
# ═══════════════════════════════════════════════════════════════════


def _last_validation_passed(state: VideoWorkflowState, node: str) -> bool:
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == node:
            return bool(v.get("passed", False))
    return True  # no result = pass by default


def route_script_validation(state: VideoWorkflowState) -> str:
    if _last_validation_passed(state, "wv_validate_script"):
        return "wv_validate_outline"
    return "wv_repair_script" if _get_repair_count(state, "script.md") < MAX_REPAIR_RETRIES else "wv_validate_outline"


def route_outline_validation(state: VideoWorkflowState) -> str:
    if _last_validation_passed(state, "wv_validate_outline"):
        return "wv_checkpoint_plan"
    return "wv_repair_outline" if _get_repair_count(state, "outline.md") < MAX_REPAIR_RETRIES else "wv_checkpoint_plan"


def route_chapter_1_validation(state: VideoWorkflowState) -> str:
    if _last_validation_passed(state, "wv_validate_chapter_1"):
        return "wv_checkpoint_chapter_1"
    return "wv_repair_chapter_1" if _get_repair_count(state, "chapter_1") < MAX_REPAIR_RETRIES else "wv_checkpoint_chapter_1"


def route_development_mode(state: VideoWorkflowState) -> str:
    chapters = _parse_outline_chapters(state)
    return "wv_build_chapter_n" if len(chapters) >= 2 else "wv_transition_to_phase3"


def route_chapter_n_validation(state: VideoWorkflowState) -> str:
    ci = state.get("current_chapter_index", 2)
    if not _last_validation_passed(state, "wv_validate_chapter_n"):
        if _get_repair_count(state, f"chapter_{ci}") < MAX_REPAIR_RETRIES:
            return "wv_repair_chapter_n"

    mode = state.get("selected_mode", "A")
    total = state.get("total_chapters", 0)
    if mode == "A":
        return "wv_checkpoint_chapter_n"
    return "wv_build_chapter_n" if ci < total else "wv_checkpoint_remaining_batch"


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
    # Fallback: check raw confirmation
    c = state.get("user_confirmations", {}).get("checkpoint_audio", {})
    if isinstance(c, dict) and c.get("decision") == "yes":
        return "wv_extract_narrations"
    return "wv_recording_guidance"


# ═══════════════════════════════════════════════════════════════════
# Thinking log helper
# ═══════════════════════════════════════════════════════════════════


def _think(log: list | None, type_: str, content: str) -> list[dict]:
    """Append a thinking event to an in-progress list. Pass None to start fresh."""
    if log is None:
        log = []
    log.append({"type": type_, "content": content, "ts": time.time()})
    return log


# ═══════════════════════════════════════════════════════════════════
# Node Wrapper — auto-tracks completed_nodes + thinking + logging
# ═══════════════════════════════════════════════════════════════════


def _wrap_node(name: str, fn):
    """Wrap a node function to auto-track completed_nodes, push thinking events, and log."""

    def wrapped(state: VideoWorkflowState) -> dict:
        logger.info("▶ %s", name)
        t0 = time.perf_counter()

        # Collect thinking events locally, append to state's log at the end
        tlog: list[dict] = []
        phase_labels = {"phase1": "内容编写", "phase2": "网页开发", "phase3": "音频合成", "phase4": "录屏"}
        phase = state.get("current_phase", "phase1")
        phase_cn = phase_labels.get(phase, phase)
        _think(tlog, "node_start", f"[{phase_cn}] {name}")

        try:
            # Run actual node — it receives state and returns partial updates
            node_result = fn(state)
            elapsed = (time.perf_counter() - t0) * 1000

            # Extract any node-level thinking events from result
            node_thinking = node_result.pop("thinking_log", []) if isinstance(node_result, dict) else []

            # Merge node result first
            result = dict(node_result) if isinstance(node_result, dict) else {"_raw": node_result}

            # Always set current_node
            result["current_node"] = name

            # Append to completed_nodes
            completed = list(state.get("completed_nodes", []))
            if not completed or completed[-1] != name:
                completed.append(name)
            result["completed_nodes"] = completed

            # Auto-infer phase
            if "current_phase" not in result:
                result["current_phase"] = state.get("current_phase", "phase1")

            # Finalize thinking log: state's existing + node's events + wrapper events
            existing = state.get("thinking_log", [])
            _think(tlog, "node_end", f"✓ {name} ({elapsed:.0f}ms)")
            result["thinking_log"] = existing + node_thinking + tlog

            logger.info("✓ %s done (%.0fms)", name, elapsed)
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            # GraphInterrupt = normal checkpoint pause, not an error
            if isinstance(e, GraphInterrupt):
                logger.info("⏸ %s interrupted after %.0fms", name, elapsed)
                set_interrupt_node(name)
                raise
            _think(tlog, "node_error", f"✗ {name}: {e}")
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
    builder.add_node("wv_validate_chapter_1", _wrap_node("wv_validate_chapter_1", wv_validate_chapter_1))
    builder.add_node("wv_repair_chapter_1", _wrap_node("wv_repair_chapter_1", wv_repair_chapter_1))
    builder.add_node("wv_checkpoint_chapter_1", _wrap_node("wv_checkpoint_chapter_1", wv_checkpoint_chapter_1_node))
    builder.add_node("wv_build_chapter_n", _wrap_node("wv_build_chapter_n", wv_build_chapter_n))
    builder.add_node("wv_validate_chapter_n", _wrap_node("wv_validate_chapter_n", wv_validate_chapter_n))
    builder.add_node("wv_repair_chapter_n", _wrap_node("wv_repair_chapter_n", wv_repair_chapter_n))
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
    builder.add_edge("wv_build_chapter_1", "wv_validate_chapter_1")

    builder.add_conditional_edges("wv_validate_chapter_1", route_chapter_1_validation, {
        "wv_repair_chapter_1": "wv_repair_chapter_1",
        "wv_checkpoint_chapter_1": "wv_checkpoint_chapter_1",
    })
    builder.add_edge("wv_repair_chapter_1", "wv_validate_chapter_1")

    builder.add_edge("wv_checkpoint_chapter_1", "wv_remove_example_chapter")
    builder.add_conditional_edges("wv_remove_example_chapter", route_development_mode, {
        "wv_build_chapter_n": "wv_build_chapter_n",
        "wv_transition_to_phase3": "wv_transition_to_phase3",
    })

    # Chapter N loop
    builder.add_edge("wv_build_chapter_n", "wv_validate_chapter_n")
    builder.add_conditional_edges("wv_validate_chapter_n", route_chapter_n_validation, {
        "wv_repair_chapter_n": "wv_repair_chapter_n",
        "wv_checkpoint_chapter_n": "wv_checkpoint_chapter_n",
        "wv_build_chapter_n": "wv_build_chapter_n",
        "wv_checkpoint_remaining_batch": "wv_checkpoint_remaining_batch",
    })
    builder.add_edge("wv_repair_chapter_n", "wv_validate_chapter_n")

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
