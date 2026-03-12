"""Multimodal processing utilities: image encoding, OCR via GPT-4o vision, annotation."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """Encode raw image bytes to a base64 data-URI string."""
    b64 = base64.b64encode(image_bytes).decode()
    return f"data:{media_type};base64,{b64}"


def decode_base64_image(data_uri: str) -> bytes:
    """Decode a base64 data-URI string back to raw bytes."""
    if "," in data_uri:
        data_uri = data_uri.split(",", 1)[1]
    return base64.b64decode(data_uri)


def build_vision_message(text: str, image_b64_list: list[str]) -> dict:
    """Build a HumanMessage-compatible content list with text and images."""
    content: list[dict] = [{"type": "text", "text": text}]
    for img_b64 in image_b64_list:
        url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": "user", "content": content}


async def ocr_with_vision(llm, image_b64: str) -> str:
    """Use GPT-4o vision to extract text from an image."""
    from langchain_core.messages import HumanMessage

    msg = HumanMessage(content=[
        {"type": "text", "text": "请提取这张图片中的所有文字内容，保持原始布局。如果没有文字，回复'图片中未发现文字'。"},
        {"type": "image_url", "image_url": {"url": image_b64 if image_b64.startswith("data:") else f"data:image/jpeg;base64,{image_b64}"}},
    ])
    resp = await llm.ainvoke([msg])
    return resp.content


async def analyze_image_with_vision(llm, image_b64: str) -> str:
    """Use GPT-4o vision to analyze product info in an image."""
    from langchain_core.messages import HumanMessage

    msg = HumanMessage(content=[
        {"type": "text", "text": "请分析这张图片中的商品信息，包括：商品类别、颜色、品牌（如果可见）、风格、材质等。用中文回答。"},
        {"type": "image_url", "image_url": {"url": image_b64 if image_b64.startswith("data:") else f"data:image/jpeg;base64,{image_b64}"}},
    ])
    resp = await llm.ainvoke([msg])
    return resp.content


def annotate_image(image_bytes: bytes, annotations: list[dict]) -> bytes:
    """Draw annotation boxes and labels on an image.

    Each annotation: {"box": [x1, y1, x2, y2], "label": "text"}
    Returns annotated image as JPEG bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for ann in annotations:
        box = ann.get("box", [])
        label = ann.get("label", "")
        if len(box) == 4:
            draw.rectangle(box, outline="red", width=2)
            draw.text((box[0], box[1] - 20), label, fill="red", font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
