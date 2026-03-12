"""FastAPI application: routes and server entry point."""

from __future__ import annotations

import base64
import logging

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import run_agent
from app.agent.multimodal import encode_image_to_base64
from app.schemas import ChatRequest, ChatResponse

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


if __name__ == "__main__":
    import uvicorn

    from app.config import settings

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
