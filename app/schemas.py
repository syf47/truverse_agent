"""请求和响应的 Pydantic 数据模型。

定义对话接口的输入输出结构，包括聊天请求、标注信息和聊天响应。
"""

from __future__ import annotations

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
