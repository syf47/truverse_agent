"""Basic tests for the Truverse Agent."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.agent.multimodal import encode_image_to_base64, decode_base64_image, annotate_image
from app.context.viking import VikingContextManager
from app.schemas import ChatRequest, ChatResponse


@pytest.mark.asyncio
async def test_health():
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


def test_viking_context_manager():
    mgr = VikingContextManager()
    mgr.add_resource("test-key", "红色连衣裙推荐", layer="L0", metadata={"session_id": "s1"})
    mgr.add_resource("test-key2", "蓝色外套推荐", layer="L1")

    results = mgr.search("红色")
    assert len(results) >= 1
    assert "红色" in results[0].content

    context = mgr.get_context("s1", "红色")
    assert "红色连衣裙" in context


def test_annotate_image():
    """Test image annotation with Pillow."""
    from PIL import Image
    import io

    # Create a simple test image
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    annotations = [{"box": [10, 10, 100, 100], "label": "test"}]
    result = annotate_image(img_bytes, annotations)
    assert len(result) > 0
    # Verify it's a valid JPEG
    result_img = Image.open(io.BytesIO(result))
    assert result_img.size == (200, 200)
