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
    """Stable identifier for this run. Used for checkpoint persistence
    and interrupt resume."""

    run_id: str
    """Per-invocation identifier."""

    # ── request ──
    user_request: str
    """Raw user input."""

    language: str
    """Detected language for the presentation (zh-CN / en)."""

    input_type: NotRequired[Literal["article", "script", "none"]]
    """What the user provided. 'article' = raw written article,
    'script' = ready-to-use voiceover script, 'none' = need to ask."""

    # ── flow control ──
    current_phase: str
    """Current high-level phase: phase1, phase2, phase3, phase4."""

    current_node: str
    """Name of the node currently executing."""

    completed_nodes: list[str]
    """Ordered list of nodes that have finished executing."""

    thinking_log: list[dict]
    """Real-time thinking events for frontend display. Each entry:
    {"type":"step"|"llm"|"node_start"|"node_end"|"validation"|"repair"|"file_write",
     "content": str, "ts": float}"""

    current_chapter_index: int
    """Index of the chapter currently being built (1-based). Chapter 1 starts
    at 1, then becomes 2 after checkpoint."""

    total_chapters: int
    """Total number of chapters parsed from outline.md."""

    pending_interrupt: dict | None
    """Data for the current interrupt (if any). Cleared on resume."""

    required_refs: list[str]
    """References that must be loaded before the current node proceeds."""

    loaded_refs: list[str]
    """References already loaded in this run."""

    # ── artifacts ──
    workspace_root: str
    """Root directory for this thread's artifacts
    (e.g. 'workspace/{thread_id}')."""

    artifact_paths: dict[str, str]
    """Maps logical file names (e.g. 'script.md') to actual paths."""

    created_files: list[str]
    """Files created during this run."""

    modified_files: list[str]
    """Files modified during this run."""

    # ── user decisions ──
    user_confirmations: dict[str, Any]
    """Stores user responses from interrupt checkpoints.
    Keyed by interrupt type (e.g. 'checkpoint_plan')."""

    selected_theme: NotRequired[str | None]
    """Theme id chosen by the user at Checkpoint Plan."""

    selected_mode: NotRequired[Literal["A", "B", "C"] | None]
    """Development mode: A=sequential+interrupt,
    B=sequential+batch, C=parallel."""

    synthesize_audio: NotRequired[bool | None]
    """Did the user choose to synthesize audio at Checkpoint Audio?"""

    # ── validation ──
    validation_results: list[ValidationResult]
    """Results from all validations performed so far."""

    repair_history: list[RepairEntry]
    """History of all repairs performed."""

    errors: list[dict]
    """Non-fatal errors encountered during execution."""

    # ── tool policy ──
    allowed_tools: list[str]
    """Tool names permitted for the current node."""

    denied_tools: list[str]
    """Tool names explicitly denied."""

    tool_calls: list[ToolCallRecord]
    """Audit log of all tool invocations."""

    # ── final ──
    final_summary: str | None
    """Summary presented to the user at the end of the workflow."""

    presentation_url: NotRequired[str | None]
    """URL for the Vite dev server serving the built presentation."""
