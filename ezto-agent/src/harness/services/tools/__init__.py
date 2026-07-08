"""Low-level capabilities for workflow and agent tools.

Layout::

    core/     shell execution, workflow telemetry
    fs/       file read/write
    chapter/  chapter context, narrations, bundle review
    craft/    CHAPTER-CRAFT checklist
    build/    tsc, vite, npm, scaffold

Import from the subpackage that owns the capability::

    from harness.services.tools.build.npm import run_npm
    from harness.services.tools.fs.file_ops import write_file
    from harness.services.tools.core.telemetry import record_tool_call

Shortcut (lazy)::

    from harness.services.tools import run_typecheck, write_file
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBPACKAGES = {
    "build": ".build",
    "chapter": ".chapter",
    "core": ".core",
    "craft": ".craft",
    "fs": ".fs",
}

# Lazy submodule access: ``from harness.services.tools import npm`` → build.npm
_SUBMODULES = {
    "npm": ".build.npm",
    "scaffold": ".build.scaffold",
    "typescript": ".build.typescript",
    "vite": ".build.vite",
    "shell": ".core.shell",
    "telemetry": ".core.telemetry",
    "file_ops": ".fs.file_ops",
    "chapter_bundle": ".chapter.chapter_bundle",
    "chapter_context": ".chapter.chapter_context",
    "missing_assets": ".chapter.missing_assets",
    "narration_args": ".chapter.narration_args",
    "narrations": ".chapter.narrations",
    "source_docs": ".chapter.source_docs",
    "craft_precheck": ".craft.craft_precheck",
    "craft_review": ".craft.craft_review",
}

_EXPORTS: dict[str, tuple[str, str]] = {
    "build_narrations_content": (".chapter.narrations", "build_narrations_content"),
    "check_vite": (".build.vite", "check_vite"),
    "edit_file": (".fs.file_ops", "edit_file"),
    "get_missing_assets": (".chapter.missing_assets", "get_missing_assets"),
    "list_files": (".fs.file_ops", "list_files"),
    "normalize_narration_lines": (".chapter.narration_args", "normalize_narration_lines"),
    "normalize_presentation_command": (".core.shell", "normalize_presentation_command"),
    "read_chapter_context": (".chapter.chapter_context", "read_chapter_context"),
    "read_file": (".fs.file_ops", "read_file"),
    "read_file_with_header": (".fs.file_ops", "read_file_with_header"),
    "read_files": (".fs.file_ops", "read_files"),
    "read_layout_catalog": (".chapter.chapter_context", "read_layout_catalog"),
    "read_motion_detail": (".chapter.chapter_context", "read_motion_detail"),
    "read_source_docs": (".chapter.source_docs", "read_source_docs"),
    "record_tool_call": (".core.telemetry", "record_tool_call"),
    "_record_tool_call": (".core.telemetry", "_record_tool_call"),
    "report_missing_assets": (".chapter.missing_assets", "report_missing_assets"),
    "resolve_tool_arguments": (".chapter.narration_args", "resolve_tool_arguments"),
    "restart_dev_server": (".build.npm", "restart_dev_server"),
    "review_chapter_bundle": (".chapter.chapter_bundle", "review_chapter_bundle"),
    "run_dev_server": (".build.npm", "run_dev_server"),
    "run_npm": (".build.npm", "run_npm"),
    "run_scaffold": (".build.scaffold", "run_scaffold"),
    "run_shell": (".core.shell", "run_shell"),
    "run_typecheck": (".build.typescript", "run_typecheck"),
    "validate_chapter_bundle": (".chapter.chapter_bundle", "validate_chapter_bundle"),
    "write_file": (".fs.file_ops", "write_file"),
    "write_narrations": (".chapter.narrations", "write_narrations"),
}

__all__ = sorted({*_SUBPACKAGES, *_SUBMODULES, *_EXPORTS})


def __getattr__(name: str) -> Any:
    if name in _SUBPACKAGES or name in _SUBMODULES:
        key = _SUBPACKAGES.get(name) or _SUBMODULES[name]
        return importlib.import_module(key, __name__)
    if name in _EXPORTS:
        module_path, attr = _EXPORTS[name]
        return getattr(importlib.import_module(module_path, __name__), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
