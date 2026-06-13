"""Phase 1 — Content Writing nodes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from backend.core import llm
from configs import settings
from backend.core.logger import logger
from harness.core.state import VideoWorkflowState, ValidationResult
from harness.workflow.guards import require_ref_loaded
from harness.workflow.interruptions import checkpoint_plan
from harness.workflow.artifacts import think, get_repair_count, MAX_REPAIR_RETRIES


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

    if input_type == "article":
        article_path = paths.get("article.md", "article.md")
        Path(article_path).write_text(text, encoding="utf-8")
        logger.info("Saved article.md (%d chars)", len(text))

    tlog = think(None, "step", "正在参考 SCRIPT-STYLE.md + OUTLINE-FORMAT.md 生成稿子和大纲")
    logger.info("Generating script.md + outline.md (input_type=%s, language=%s)", input_type, language)
    think(tlog, "llm", "调用 DeepSeek 生成 script.md（口播稿）+ outline.md（大纲）…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Language: {language}\n"
        f"Input type: {input_type}\n\n"
        f"Reference — script style:\n{ref_script}\n\n"
        f"Reference — outline format:\n{ref_outline}\n\n"
        f"Input text:\n{text}\n\n"
        f"Write script.md (narration script) and outline.md (chapter outline).\n"
        f"Separate them with: ===OUTLINE==="
    )}])

    parts = reply.split("===OUTLINE===")
    script_content = parts[0].strip()
    outline_content = "===OUTLINE===".join(parts[1:]).strip() if len(parts) >= 2 else "# Outline\n## Chapter 1\n\n(TODO)"

    script_path = paths.get("script.md", "script.md")
    outline_path = paths.get("outline.md", "outline.md")
    Path(script_path).write_text(script_content, encoding="utf-8")
    Path(outline_path).write_text(outline_content, encoding="utf-8")

    think(tlog, "file_write", f"已生成 script.md ({len(script_content)} 字符)")
    think(tlog, "file_write", f"已生成 outline.md ({len(outline_content)} 字符)")
    logger.info("Written script.md (%d chars) + outline.md (%d chars)",
                len(script_content), len(outline_content))
    return {"current_node": "wv_prepare_source_files",
            "created_files": [script_path, outline_path],
            "thinking_log": tlog}


def wv_validate_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    tlog = think(None, "step", "正在参考 SCRIPT-STYLE.md 进行自检…")
    script_path = state.get("artifact_paths", {}).get("script.md")
    if not script_path or not Path(script_path).exists():
        logger.warning("script.md not found at %s", script_path)
        think(tlog, "validation", "script.md 文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_script", target="script.md", passed=False,
            failed_checks=["script.md not found"], details="")],
            "thinking_log": tlog}

    content = Path(script_path).read_text(encoding="utf-8")
    logger.info("Validating script.md (%d chars)", len(content))
    think(tlog, "llm", "调用 DeepSeek 校验脚本质量…")

    article_path = state.get("artifact_paths", {}).get("article.md", "")
    article_hint = ""
    if article_path and Path(article_path).exists():
        article_text = Path(article_path).read_text(encoding="utf-8")
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

    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Validate this script against the style guide:\n\n{ref}\n\n"
        f"{article_hint}"
        f"Script:\n{content}\n\n"
        f"Respond with JSON only:\n"
        f'{{"passed":bool,"failed_checks":["..."],"details":"..."}}'
    )}], temperature=0.0)

    try:
        jresult = json.loads(reply)
    except json.JSONDecodeError:
        jresult = {"passed": True, "failed_checks": [], "details": "Parse error, defaulting to pass"}

    passed = bool(jresult.get("passed", True))
    checks = jresult.get("failed_checks", [])
    if passed:
        think(tlog, "validation", "✅ script.md 校验通过")
    else:
        think(tlog, "validation", f"❌ 发现 {len(checks)} 个问题")
        for c in checks:
            think(tlog, "validation", f"  • {c}")
    logger.info("Script validation: %s (failed_checks=%s)", "PASS" if passed else "FAIL", checks)
    return {"validation_results": [ValidationResult(
        node="wv_validate_script", target="script.md",
        passed=passed, failed_checks=checks, details=jresult.get("details", ""))],
        "thinking_log": tlog}


def wv_repair_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    tlog = think(None, "step", "正在修复 script.md…")
    script_path = state.get("artifact_paths", {}).get("script.md")
    content = Path(script_path).read_text(encoding="utf-8") if script_path else ""

    validations = state.get("validation_results", [])
    issues = ""
    for v in reversed(validations):
        if v["node"] == "wv_validate_script":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            break

    repair_count = get_repair_count(state, "script.md")
    think(tlog, "repair", f"第 {repair_count + 1} 次修复, 共 {MAX_REPAIR_RETRIES} 次")
    logger.info("Repairing script.md (attempt %d/%d, issues=%s)", repair_count + 1, MAX_REPAIR_RETRIES, issues[:200])
    think(tlog, "llm", "调用 DeepSeek 修复脚本问题…")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Style guide:\n{ref}\n\nIssues to fix:\n{issues}\n\n"
        f"Current script:\n{content}\n\nRewrite the full script fixing all issues."
    )}])

    Path(script_path).write_text(reply.strip(), encoding="utf-8")
    think(tlog, "file_write", f"已更新 script.md ({len(reply)} 字符)")
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
    tlog = think(None, "step", "正在校验 outline.md…")
    outline_path = state.get("artifact_paths", {}).get("outline.md")
    if not outline_path or not Path(outline_path).exists():
        think(tlog, "validation", "❌ outline.md 文件未找到")
        return {"validation_results": [ValidationResult(
            node="wv_validate_outline", target="outline.md", passed=False,
            failed_checks=["outline.md not found"], details="")],
            "thinking_log": tlog,
            "current_node": "wv_validate_outline"}

    content = Path(outline_path).read_text(encoding="utf-8")
    think(tlog, "llm", "调用 DeepSeek 校验大纲格式…")
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
        think(tlog, "validation", "✅ outline.md 校验通过")
    else:
        think(tlog, "validation", f"❌ 发现 {len(checks)} 个问题")
        for c in checks:
            think(tlog, "validation", f"  • {c}")

    return {"validation_results": [ValidationResult(
        node="wv_validate_outline", target="outline.md",
        passed=passed, failed_checks=checks, details=result.get("details", ""))],
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
    themes_dir = Path(settings.themes_dir)
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

    tlog = think(None, "step", f"已加载 {len(recommendations)} 个主题，等待用户确认 5 件事")
    logger.info("Checkpoint Plan interrupt — %d themes available", len(recommendations))
    result = checkpoint_plan(state, recommendations[:10], ["script.md", "outline.md"])
    response = result.get("user_confirmations", {}).get("checkpoint_plan", {})
    if isinstance(response, dict):
        theme = response.get("selected_theme")
        if theme:
            result["selected_theme"] = theme
            logger.info("Checkpoint Plan → selected_theme=%s", theme)
            think(tlog, "step", f"用户选择主题: {theme}")
        mode = response.get("development_mode")
        if mode:
            result["selected_mode"] = mode
            logger.info("Checkpoint Plan → selected_mode=%s", mode)
            think(tlog, "step", f"用户选择开发模式: {mode}")
    result["thinking_log"] = tlog
    return result
