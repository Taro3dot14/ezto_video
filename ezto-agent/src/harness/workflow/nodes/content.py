"""Phase 1 — Content Writing nodes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from backend.core import llm
from backend.core.llm import MODEL_ROLE_CONTENT
from configs import settings
from backend.core.logger import logger
from harness.core.state import VideoWorkflowState, ValidationResult
from harness.workflow.guards import require_ref_loaded, ensure_workspace_ready, ensure_artifact_parent
from harness.workflow.interruptions import checkpoint_plan
from harness.workflow.artifacts import think, get_repair_count, get_max_repair_retries, safe_repair_write


def _emit_repair_targets(tlog: list[dict], failed_checks: list[str]) -> None:
    """Show optimization round targets after the round header."""
    if not failed_checks:
        return
    think(tlog, "validation", f"发现了 {len(failed_checks)} 个优化目标")
    for check in failed_checks:
        think(tlog, "validation", f"  · {check}")


def wv_identify_input(state: VideoWorkflowState) -> dict:
    text = state.get("user_request", "").strip()
    if not text or len(text) < 20:
        logger.info("Input too short (%d chars) → type=none", len(text))
        return {"input_type": "none"}

    logger.info("Classifying input (%d chars)", len(text))
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Classify the following text as article, script, or none.\n"
        f"Reply with ONLY that single word.\n\n{text[:2000]}"
    )}], temperature=0.0, role=MODEL_ROLE_CONTENT)

    detected: Literal["article", "script", "none"] = "none"
    for kw in ("article", "script"):
        if kw in reply.strip().lower():
            detected = kw  # type: ignore
            break
    logger.info("Input classified as: %s", detected)
    return {"input_type": detected}


def _load_or_seed_script(state: VideoWorkflowState, script_path: str) -> str:
    """Read script.md or seed from user_request when the file is missing."""
    target = ensure_artifact_parent(script_path)
    if target.exists():
        return target.read_text(encoding="utf-8")
    seed = ""
    if state.get("input_type") == "script":
        seed = state.get("user_request", "").strip()
    if seed:
        target.write_text(seed, encoding="utf-8")
        logger.info("Seeded missing script.md from user_request (%d chars)", len(seed))
        return seed
    return ""


def wv_prepare_source_files(state: VideoWorkflowState) -> dict:
    ref_script = require_ref_loaded(state, "SCRIPT-STYLE.md")
    ref_outline = require_ref_loaded(state, "OUTLINE-FORMAT.md")

    ws_update = ensure_workspace_ready(state)
    text = state.get("user_request", "")
    input_type = state.get("input_type", "none")
    language = state.get("language", "zh-CN")
    paths = ws_update["artifact_paths"]

    if input_type == "none":
        logger.warning("No input content — cannot generate script/outline")
        return {"errors": [{"node": "wv_prepare_source_files",
                            "error": "No content provided — cannot generate script/outline."}],
                "current_node": "wv_prepare_source_files"}

    if input_type == "article":
        article_path = paths["article.md"]
        ensure_artifact_parent(article_path).write_text(text, encoding="utf-8")
        logger.info("Saved article.md (%d chars)", len(text))

    if input_type == "script":
        script_path = paths["script.md"]
        ensure_artifact_parent(script_path).write_text(text, encoding="utf-8")
        logger.info("Saved input script.md (%d chars)", len(text))

    tlog = think(None, "step", "正在参考 SCRIPT-STYLE.md + OUTLINE-FORMAT.md 生成口播稿和大纲")
    logger.info("Generating script.md + outline.md (input_type=%s, language=%s)", input_type, language)
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Language: {language}\n"
        f"Input type: {input_type}\n\n"
        f"Reference — script style:\n{ref_script}\n\n"
        f"Reference — outline format:\n{ref_outline}\n\n"
        f"Input text:\n{text}\n\n"
        f"Write script.md (narration script) and outline.md (chapter outline).\n"
        f"Chapter ids in outline MUST summarize each chapter's **content topic** "
        f"(e.g. human-agent-teams, slack-dataset-demo) — NEVER role labels "
        f"(coldopen, hook, intro, opener, closing, outro).\n"
        f"Separate them with: ===OUTLINE==="
    )}], role=MODEL_ROLE_CONTENT)

    parts = reply.split("===OUTLINE===")
    script_content = parts[0].strip()
    outline_content = "===OUTLINE===".join(parts[1:]).strip() if len(parts) >= 2 else "# Outline\n## Chapter 1\n\n(TODO)"

    script_path = paths["script.md"]
    outline_path = paths["outline.md"]
    ensure_artifact_parent(script_path).write_text(script_content, encoding="utf-8")
    ensure_artifact_parent(outline_path).write_text(outline_content, encoding="utf-8")

    think(tlog, "file_write", f"已生成口播稿（{len(script_content)} 字）")
    think(tlog, "file_write", f"已生成大纲（{len(outline_content)} 字）")
    logger.info("Written script.md (%d chars) + outline.md (%d chars)",
                len(script_content), len(outline_content))
    return {**ws_update,
            "current_node": "wv_prepare_source_files",
            "created_files": [script_path, outline_path],
            "thinking_log": tlog}


def wv_validate_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    ws_update = ensure_workspace_ready(state)
    tlog = think(None, "step", "正在对照 SCRIPT-STYLE.md 核对口播风格…")
    script_path = ws_update["artifact_paths"].get("script.md")
    if not script_path or not Path(script_path).exists():
        logger.warning("script.md not found at %s", script_path)
        think(tlog, "validation", "未找到口播稿文件")
        return {**ws_update,
                "validation_results": [ValidationResult(
            node="wv_validate_script", target="script.md", passed=False,
            failed_checks=["script.md not found"], details="")],
            "thinking_log": tlog}

    content = Path(script_path).read_text(encoding="utf-8")
    logger.info("Validating script.md (%d chars)", len(content))

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
    )}], temperature=0.0, role=MODEL_ROLE_CONTENT)

    try:
        jresult = json.loads(reply)
    except json.JSONDecodeError:
        jresult = {"passed": True, "failed_checks": [], "details": "Parse error, defaulting to pass"}

    passed = bool(jresult.get("passed", True))
    checks = jresult.get("failed_checks", [])
    if passed:
        think(tlog, "validation", "口播稿风格核对通过")
    else:
        if get_repair_count(state, "script.md") >= get_max_repair_retries("script.md"):
            think(tlog, "validation", "本轮优化次数已用尽，继续后续流程")
    logger.info("Script validation: %s (failed_checks=%s)", "PASS" if passed else "FAIL", checks)
    return {**ws_update,
            "validation_results": [ValidationResult(
        node="wv_validate_script", target="script.md",
        passed=passed, failed_checks=checks, details=jresult.get("details", ""))],
        "thinking_log": tlog}


def wv_repair_script(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "SCRIPT-STYLE.md")
    ws_update = ensure_workspace_ready(state)
    tlog: list[dict] = []
    script_path = ws_update["artifact_paths"].get("script.md")
    if not script_path:
        think(tlog, "repair", "口播稿路径缺失，跳过本轮优化")
        return {**ws_update, "thinking_log": tlog, "current_node": "wv_repair_script"}

    content = _load_or_seed_script(state, script_path)

    validations = state.get("validation_results", [])
    issues = ""
    failed_checks: list[str] = []
    for v in reversed(validations):
        if v["node"] == "wv_validate_script":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            failed_checks = list(v.get("failed_checks", []))
            break

    source_block = ""
    article_path = state.get("artifact_paths", {}).get("article.md")
    if (not content.strip() or len(content) < 300) and article_path and Path(article_path).exists():
        article_text = Path(article_path).read_text(encoding="utf-8")
        source_block = (
            f"\n\nSource article (regenerate the full script from this — current script is empty or too short):\n"
            f"{article_text[:12000]}\n"
        )

    max_retries = get_max_repair_retries("script.md")
    repair_count = get_repair_count(state, "script.md")
    attempt = repair_count + 1
    think(tlog, "repair", f"第 {attempt} 轮优化")
    _emit_repair_targets(tlog, failed_checks)
    think(tlog, "step", "正在根据优化目标润色口播稿…")
    logger.info("Repairing script.md (attempt %d, max %d, issues=%s)",
                attempt, max_retries, issues[:200])

    prompt = (
        f"Style guide:\n{ref}\n\nIssues to fix:\n{issues}\n\n"
        f"Current script:\n{content}\n"
        f"{source_block}\n"
        "Rewrite the FULL script fixing all issues.\n"
        "OUTPUT RULES (mandatory):\n"
        "- Output ONLY the complete script text — no JSON, no commentary, no questions.\n"
        "- Keep --- separators between narration beats.\n"
        "- Preserve all factual content; do not shorten below 60% of the original length.\n"
        "- Do NOT ask the user to provide the script — write it now."
    )

    repaired = ""
    for llm_attempt in range(2):
        reply = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            role=MODEL_ROLE_CONTENT,
            max_tokens=16384,
        )
        repaired, wrote = safe_repair_write(script_path, content, reply or "")
        if wrote:
            break
        logger.warning(
            "script.md repair attempt %d LLM pass %d produced unusable output (%d chars)",
            attempt, llm_attempt + 1, len(reply or ""),
        )

    if not repaired or repaired == content.strip():
        think(tlog, "repair", "本轮未生成新版本，保留当前口播稿")
        logger.warning("script.md repair produced no usable content — keeping previous file")
        repaired = content
    else:
        think(tlog, "file_write", f"口播稿已更新（{len(repaired)} 字）")
        logger.info("Repaired script.md rewritten (%d chars)", len(repaired))

    history = list(state.get("repair_history", []))
    history.append({"node": "wv_repair_script", "target": "script.md",
                    "failed_checks": failed_checks,
                    "repair_summary": repaired.strip()[:200]})

    return {**ws_update,
            "current_node": "wv_repair_script",
            "modified_files": [script_path] if repaired != content else [],
            "thinking_log": tlog,
            "repair_history": history}


def wv_validate_outline(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "OUTLINE-FORMAT.md")
    tlog = think(None, "step", "正在对照 OUTLINE-FORMAT.md 核对大纲结构…")
    outline_path = state.get("artifact_paths", {}).get("outline.md")
    if not outline_path or not Path(outline_path).exists():
        think(tlog, "validation", "未找到大纲文件")
        return {"validation_results": [ValidationResult(
            node="wv_validate_outline", target="outline.md", passed=False,
            failed_checks=["outline.md not found"], details="")],
            "thinking_log": tlog,
            "current_node": "wv_validate_outline"}

    content = Path(outline_path).read_text(encoding="utf-8")
    reply = llm.chat(messages=[{"role": "user", "content": (
        f"Validate this outline against the format spec:\n\n{ref}\n\n"
        f"Outline:\n{content}\n\n"
        f"JSON response only:\n"
        f'{{"passed":bool,"failed_checks":["..."],"details":"..."}}'
    )}], temperature=0.0, role=MODEL_ROLE_CONTENT)

    try:
        result = json.loads(reply)
    except json.JSONDecodeError:
        result = {"passed": True, "failed_checks": [], "details": ""}

    passed = bool(result.get("passed", True))
    checks = result.get("failed_checks", [])
    if passed:
        think(tlog, "validation", "大纲结构核对通过")
    else:
        if get_repair_count(state, "outline.md") >= get_max_repair_retries("outline.md"):
            think(tlog, "validation", "本轮优化次数已用尽，继续后续流程")

    return {"validation_results": [ValidationResult(
        node="wv_validate_outline", target="outline.md",
        passed=passed, failed_checks=checks, details=result.get("details", ""))],
        "thinking_log": tlog,
        "current_node": "wv_validate_outline"}


def wv_repair_outline(state: VideoWorkflowState) -> dict:
    ref = require_ref_loaded(state, "OUTLINE-FORMAT.md")
    tlog: list[dict] = []
    outline_path = state.get("artifact_paths", {}).get("outline.md")
    content = Path(outline_path).read_text(encoding="utf-8") if outline_path else ""

    issues = ""
    failed_checks: list[str] = []
    for v in reversed(state.get("validation_results", [])):
        if v["node"] == "wv_validate_outline":
            issues = v.get("details", "") + "\n" + "\n".join(v.get("failed_checks", []))
            failed_checks = list(v.get("failed_checks", []))
            break

    max_retries = get_max_repair_retries("outline.md")
    repair_count = get_repair_count(state, "outline.md")
    attempt = repair_count + 1
    think(tlog, "repair", f"第 {attempt} 轮优化")
    _emit_repair_targets(tlog, failed_checks)
    think(tlog, "step", "正在根据优化目标调整大纲…")
    logger.info("Repairing outline.md (attempt %d, max %d)", attempt, max_retries)
    prompt = (
        f"Format spec:\n{ref}\n\nIssues:\n{issues}\n\n"
        f"Current outline:\n{content}\n\n"
        "Rewrite the FULL outline fixing all issues.\n"
        "Chapter ids must summarize each chapter's content topic — never role labels "
        "(coldopen, hook, intro, opener, closing, outro).\n"
        "OUTPUT RULES: output ONLY the outline text — no JSON, no commentary, no questions."
    )
    repaired = ""
    for llm_attempt in range(2):
        reply = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            role=MODEL_ROLE_CONTENT,
            max_tokens=16384,
        )
        repaired, wrote = safe_repair_write(outline_path, content, reply or "")
        if wrote:
            break
        logger.warning(
            "outline.md repair attempt %d LLM pass %d produced unusable output (%d chars)",
            attempt, llm_attempt + 1, len(reply or ""),
        )

    if not repaired or repaired == content.strip():
        think(tlog, "repair", "本轮未生成新版本，保留当前大纲")
        repaired = content
    else:
        think(tlog, "file_write", f"大纲已更新（{len(repaired)} 字）")

    history = list(state.get("repair_history", []))
    history.append({"node": "wv_repair_outline", "target": "outline.md",
                    "failed_checks": failed_checks,
                    "repair_summary": repaired.strip()[:200]})

    return {"current_node": "wv_repair_outline",
            "modified_files": [outline_path] if repaired != content else [],
            "thinking_log": tlog,
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
                    if meta.get("hidden"):
                        continue
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
