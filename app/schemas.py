"""请求和响应的 Pydantic 数据模型。

定义对话接口的输入输出结构，包括聊天请求、标注信息和聊天响应。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型。

    Attributes:
        message: 用户发送的文本消息。
        session_id: 会话标识符。
        images: Base64 编码的图片列表，可选。
    """

    message: str
    session_id: str
    images: list[str] | None = Field(default=None, description="Base64 编码的图片列表")


class AnnotationInfo(BaseModel):
    """图片标注信息模型。

    Attributes:
        image_base64: 标注后图片的 Base64 编码。
        description: 标注描述文本。
    """

    image_base64: str | None = None
    description: str | None = None


class ChatResponse(BaseModel):
    """聊天响应模型。

    Attributes:
        reply: 助手的文本回复。
        annotations: 图片标注信息列表。
        metadata: 附加元数据字典。
    """

    reply: str
    annotations: list[AnnotationInfo] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DeskAuditResponse(BaseModel):
    """桌面清洁审核响应。"""

    passed: bool
    score: int = Field(description="清洁评分，0 到 100")
    threshold: int = Field(description="通过阈值")
    summary: str
    dimension_scores: dict[str, int] = Field(default_factory=dict, description="分项评分，如 cleanliness/tidiness/placement_consistency")
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    handling_advice: str = Field(default="", description="问题处理说明")
    handling_advice_json: dict = Field(default_factory=dict, description="结构化问题处理说明")
    issue_annotations: list["DeskAuditIssueAnnotation"] = Field(default_factory=list)
    annotated_image_base64: str | None = Field(default=None, description="后端已标记问题区域的图片")
    reference_mode: str = Field(default="configured", description="参考图来源：configured 或 uploaded")


class DeskAuditIssueAnnotation(BaseModel):
    """桌面清洁问题标注信息。"""

    label: str
    category: str = "unknown"
    detail: str | None = None
    box: list[int] = Field(default_factory=list, description="像素坐标 [x1, y1, x2, y2]")


class DeskAuditReferenceResponse(BaseModel):
    """桌面清洁审核参考图状态。"""

    configured: bool
    filename: str | None = None
    updated_at: float | None = Field(default=None, description="Unix 时间戳")

    @property
    def updated_at_display(self) -> str | None:
        if self.updated_at is None:
            return None
        return datetime.fromtimestamp(self.updated_at).isoformat()
