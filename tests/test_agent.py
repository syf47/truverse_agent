"""Basic tests for the Truverse Agent."""

from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.agent.multimodal import annotate_image, decode_base64_image, encode_image_to_base64
from app.schemas import ChatRequest, ChatResponse


@pytest.mark.asyncio
async def test_health():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_schema_chat_request():
    req = ChatRequest(message="hello", session_id="s1")
    assert req.message == "hello"
    assert req.images is None


def test_schema_chat_response():
    resp = ChatResponse(reply="hi")
    assert resp.reply == "hi"
    assert resp.annotations == []
    assert resp.metadata == {}


def test_base64_roundtrip():
    original = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    encoded = encode_image_to_base64(original, "image/png")
    assert encoded.startswith("data:image/png;base64,")
    decoded = decode_base64_image(encoded)
    assert decoded == original


def test_annotate_image():
    """Test image annotation with Pillow."""
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    annotations = [{"box": [10, 10, 100, 100], "label": "test"}]
    result = annotate_image(img_bytes, annotations)
    assert len(result) > 0
    result_img = Image.open(io.BytesIO(result))
    assert result_img.size == (200, 200)
