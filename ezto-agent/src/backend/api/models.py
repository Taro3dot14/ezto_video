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


class ApplyThemeRequest(BaseModel):
    """POST /api/workflow/{id}/theme 请求体。"""
    theme_id: str = Field(..., description="主题 id，对应 assets/themes/<id>")


class ApplyThemeResponse(BaseModel):
    """主题切换响应。"""
    thread_id: str | None = None
    project_id: str | None = None
    theme_id: str
    selected_theme: str
    presentation_url: str | None = None


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
    execution_trace: list[dict] = []
    execution_revision: int = 0
    total_nodes: int = 20
    token_usage: dict = Field(default_factory=dict)
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
    paused: bool = False
    paused_at: float | None = None


class StartWorkflowResponse(BaseModel):
    """POST /api/workflow/start 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class ResumeWorkflowResponse(BaseModel):
    """POST /api/workflow/{id}/resume 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class PauseWorkflowResponse(BaseModel):
    """POST /api/workflow/{id}/pause 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class ContinueWorkflowResponse(BaseModel):
    """POST /api/workflow/{id}/continue 响应。"""
    thread_id: str
    state: WorkflowStateResponse


class ErrorResponse(BaseModel):
    """通用错误响应。"""
    error: str
    message: str
    detail: dict | None = None


class ProjectSummary(BaseModel):
    """GET /api/projects 列表项。"""
    id: str
    name: str
    status: str
    artifact_count: int = 0
    is_active: bool = False
    created_at: str = ""
    updated_at: str = ""
    input_type: str | None = None


class ProjectDetail(ProjectSummary):
    """GET /api/projects/{id} 详情。"""
    user_request: str = ""
    language: str = "zh-CN"
    artifacts: list[ArtifactInfo] = []


class RenameProjectRequest(BaseModel):
    """PATCH /api/projects/{id} 请求体。"""
    name: str = Field(..., min_length=1, max_length=80)


class DeleteProjectResponse(BaseModel):
    """DELETE /api/projects/{id} 响应。"""
    deleted: bool = True
    id: str
    name: str = ""
