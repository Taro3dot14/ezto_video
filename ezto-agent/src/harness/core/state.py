"""Unified workflow state for the web-video-presentation LangGraph."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ValidationResult(TypedDict):
    """Result of a validation check against a reference spec."""

    node: str
    target: str  # e.g. "script.md", "chapter_1"
    passed: bool
    failed_checks: list[str]
    details: str | None


class RepairEntry(TypedDict):
    """Record of a repair action taken after validation failure."""

    node: str
    target: str
    failed_checks: list[str]
    repair_summary: str


class ToolCallRecord(TypedDict):
    """Record of a single tool invocation for audit."""

    node: str
    tool: str
    args: dict[str, Any]
    allowed: bool
    reason: str
    timestamp: str


class VideoWorkflowState(TypedDict):
    """Central state type for the web-video-presentation LangGraph.

    Every node reads from and writes to this state. Fields are grouped by
    concern: identity, request, flow control, skill metadata, artifacts,
    user decisions, validation, and tool policy.
    """

    # ── identity ──
    thread_id: str
    run_id: str

    # ── request ──
    user_request: str
    language: str
    input_type: NotRequired[Literal["article", "script", "none"]]

    # ── flow control ──
    current_phase: str
    current_node: str
    completed_nodes: list[str]
    execution_trace: list[dict]
    execution_revision: NotRequired[int]
    token_usage: NotRequired[dict]
    thinking_log: list[dict]  # deprecated — use execution_trace
    current_chapter_index: int
    total_chapters: int
    pending_interrupt: dict | None
    required_refs: list[str]
    loaded_refs: list[str]

    # ── artifacts ──
    workspace_root: str
    artifact_paths: dict[str, str]
    created_files: list[str]
    modified_files: list[str]

    # ── user decisions ──
    user_confirmations: dict[str, Any]
    selected_theme: NotRequired[str | None]
    selected_mode: NotRequired[Literal["A", "B", "C"] | None]
    synthesize_audio: NotRequired[bool | None]
    approved_chapter_ids: NotRequired[list[str]]
    chapter_missing_assets: NotRequired[dict[str, Any]]  # chapter_id → {items, note}

    # ── validation ──
    validation_results: list[ValidationResult]
    repair_history: list[RepairEntry]
    errors: list[dict]

    # ── tool policy ──
    allowed_tools: list[str]
    denied_tools: list[str]
    tool_calls: list[ToolCallRecord]

    # ── final ──
    final_summary: str | None
    presentation_url: NotRequired[str | None]
