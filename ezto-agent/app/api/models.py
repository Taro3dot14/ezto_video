"""Pydantic request/response models for the workflow API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Request models ──


class StartRequest(BaseModel):
    """POST /api/workflow/start request body."""

    user_request: str = Field(
        ..., description="原始用户输入（文章、口播稿或需求描述）"
    )
    language: str = Field(
        "zh-CN", description="内容语言 (zh-CN / en)"
    )
    input_type: Literal["article", "script", "none"] | None = Field(
        None,
        description="输入类型: article=原文, script=口播稿, none=啥都没给, None=自动判断",
    )


class ResumeRequest(BaseModel):
    """POST /api/workflow/{id}/resume request body."""

    confirmations: dict[str, Any] = Field(
        ..., description="用户确认数据，按 checkpoint 类型对应不同 schema"
    )


class ResumePlanConfirmations(BaseModel):
    """Checkpoint Plan 的用户确认数据结构."""
    script_feedback: str | None = Field(None, description="对 script.md 的修改意见")
    outline_feedback: str | None = Field(None, description="对 outline.md 的修改意见")
    selected_theme: str = Field(..., description="选定的主题 id")
    material_plan: str = Field(..., description="素材准备方案: a/b/c")
    development_mode: Literal["A", "B", "C"] = Field(
        "A", description="开发模式: A=逐章确认, B=顺序+批量, C=并行"
    )


class ResumeChapterConfirmations(BaseModel):
    """章节验收的用户确认."""
    approved: bool = Field(..., description="是否通过")
    feedback: str | None = Field(None, description="修改反馈")


# ── Response models ──


class ThemeInfo(BaseModel):
    """主题信息（来自 theme.json）。"""
    id: str
    name: str
    nameZh: str
    description: str
    descriptionZh: str
    mood: list[str]
    bestFor: list[str]
    preview: dict[str, str] | None = None


class ArtifactInfo(BaseModel):
    """产出文件信息。"""
    logical_name: str
    path: str
    exists: bool
    size: int | None = None


class NodeInfo(BaseModel):
    """节点执行信息。"""
    name: str
    status: Literal["pending", "running", "completed", "skipped"] = "pending"


class WorkflowStateResponse(BaseModel):
    """GET /api/workflow/{id} 响应。"""
    thread_id: str
    current_phase: str
    current_node: str
    completed_nodes: list[str]
    thinking_log: list[dict] = []
    pending_interrupt: dict | None = None
    errors: list[dict] = []
    artifacts: list[ArtifactInfo] = []
    selected_theme: str | None = None
    selected_mode: str | None = None
    final_summary: str | None = None
    repair_history: list[dict] = []
    validation_results: list[dict] = []
    user_confirmations: dict = Field(default_factory=dict)
    presentation_url: str | None = None


class StartWorkflowResponse(BaseModel):
    """POST /api/workflow/start 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class ResumeWorkflowResponse(BaseModel):
    """POST /api/workflow/{id}/resume 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class ErrorResponse(BaseModel):
    """通用错误响应。"""
    error: str
    message: str
    detail: dict | None = None
