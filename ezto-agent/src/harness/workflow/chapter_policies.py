"""Chapter build policies — re-exports validation + tool guards for compatibility."""

from __future__ import annotations

from typing import Any

from harness.workflow.chapter_validation import (
    auto_validate_chapter,
    classify_tsx_css_classes,
    is_template_global_class,
    validate_chapter_tsx_contract,
    validate_no_header_footer_tsx,
    validate_theme_contrast,
    validate_tsx_css_classes,
)

__all__ = [
    "auto_validate_chapter",
    "check_tool_guard",
    "classify_tsx_css_classes",
    "is_template_global_class",
    "validate_chapter_tsx_contract",
    "validate_no_header_footer_tsx",
    "validate_theme_contrast",
    "validate_tsx_css_classes",
]


def __getattr__(name: str) -> Any:
    if name == "check_tool_guard":
        from harness.agent.tools.guards import check_tool_guard

        return check_tool_guard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
