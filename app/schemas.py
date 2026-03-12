from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str
    images: list[str] | None = Field(default=None, description="Base64 encoded images")


class AnnotationInfo(BaseModel):
    image_base64: str | None = None
    description: str | None = None


class ChatResponse(BaseModel):
    reply: str
    annotations: list[AnnotationInfo] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
