"""FastAPI 应用入口模块。

提供 HTTP 路由和服务器启动配置，包括文本对话、多模态对话和流式对话接口。
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.agent.desk_audit import (
    DeskAuditError,
    analyze_desk_cleanliness,
    get_reference_image_status,
    save_reference_image,
)
from app.agent.graph import run_agent, stream_agent
from app.agent.multimodal import encode_image_to_base64
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DeskAuditReferenceResponse,
    DeskAuditResponse,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Truverse Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    reply = await run_agent(
        message=req.message,
        session_id=req.session_id,
        images=req.images,
    )
    return ChatResponse(reply=reply, metadata={"session_id": req.session_id})


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话接口，通过 SSE（Server-Sent Events）逐步返回推理过程和回答。

    Event types:
    - token: LLM 输出的文本 token
    - tool_start: 开始调用工具（含工具名和输入）
    - tool_end: 工具返回结果（含工具名和输出）
    - done: 流结束
    """

    async def event_generator():
        async for event in stream_agent(
            message=req.message,
            session_id=req.session_id,
            images=req.images,
        ):
            payload = json.dumps(event, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat/multimodal", response_model=ChatResponse)
async def chat_multimodal(
    message: str = Form(...),
    session_id: str = Form(...),
    images: list[UploadFile] = File(default=[]),
):
    image_b64_list: list[str] = []
    for img_file in images:
        raw = await img_file.read()
        content_type = img_file.content_type or "image/jpeg"
        image_b64_list.append(encode_image_to_base64(raw, content_type))

    reply = await run_agent(
        message=message,
        session_id=session_id,
        images=image_b64_list,
    )
    return ChatResponse(
        reply=reply,
        metadata={"session_id": session_id, "images_count": len(image_b64_list)},
    )


@app.post("/audit/desk-cleanliness", response_model=DeskAuditResponse)
async def audit_desk_cleanliness(
    submitted_image: UploadFile = File(...),
    reference_image: UploadFile | None = File(default=None),
    notes: str = Form(default=""),
):
    submitted_bytes = await submitted_image.read()
    reference_bytes = await reference_image.read() if reference_image else None

    try:
        return await analyze_desk_cleanliness(
            submitted_image=submitted_bytes,
            submitted_media_type=submitted_image.content_type or "image/jpeg",
            reference_image=reference_bytes,
            reference_media_type=reference_image.content_type if reference_image else None,
            notes=notes,
        )
    except DeskAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/audit/desk-cleanliness/reference", response_model=DeskAuditReferenceResponse)
async def audit_reference_status():
    return get_reference_image_status()


@app.post("/audit/desk-cleanliness/reference", response_model=DeskAuditReferenceResponse)
async def upload_audit_reference(
    reference_image: UploadFile = File(...),
):
    reference_bytes = await reference_image.read()
    try:
        return save_reference_image(reference_bytes)
    except DeskAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    from app.config import settings

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
