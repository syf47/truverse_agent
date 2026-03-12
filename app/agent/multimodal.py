"""多模态处理工具模块。

提供图片编码解码、GPT-4o Vision OCR 文字提取、图片商品分析
以及 Pillow 图片标注等功能。
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """将原始图片字节编码为 Base64 data-URI 字符串。

    Args:
        image_bytes: 原始图片的字节数据。
        media_type: 图片的 MIME 类型。

    Returns:
        格式为 ``data:{media_type};base64,{data}`` 的 data-URI 字符串。
    """
    b64 = base64.b64encode(image_bytes).decode()
    return f"data:{media_type};base64,{b64}"


def decode_base64_image(data_uri: str) -> bytes:
    """将 Base64 data-URI 字符串解码为原始字节。

    Args:
        data_uri: Base64 编码的 data-URI 字符串。

    Returns:
        解码后的原始图片字节数据。
    """
    if "," in data_uri:
        data_uri = data_uri.split(",", 1)[1]
    return base64.b64decode(data_uri)


def build_vision_message(text: str, image_b64_list: list[str]) -> dict:
    """构建兼容 HumanMessage 的多模态消息内容。

    Args:
        text: 文本消息内容。
        image_b64_list: Base64 编码的图片列表。

    Returns:
        包含 role 和 content 的消息字典。
    """
    content: list[dict] = [{"type": "text", "text": text}]
    for img_b64 in image_b64_list:
        url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": "user", "content": content}


async def ocr_with_vision(llm, image_b64: str) -> str:
    """使用 GPT-4o Vision 从图片中提取文字。

    Args:
        llm: LangChain ChatOpenAI 实例。
        image_b64: Base64 编码的图片。

    Returns:
        提取到的文字内容。
    """
    from langchain_core.messages import HumanMessage

    msg = HumanMessage(content=[
        {"type": "text", "text": "请提取这张图片中的所有文字内容，保持原始布局。如果没有文字，回复'图片中未发现文字'。"},
        {"type": "image_url", "image_url": {"url": image_b64 if image_b64.startswith("data:") else f"data:image/jpeg;base64,{image_b64}"}},
    ])
    resp = await llm.ainvoke([msg])
    return resp.content


async def analyze_image_with_vision(llm, image_b64: str) -> str:
    """使用 GPT-4o Vision 分析图片中的商品信息。

    Args:
        llm: LangChain ChatOpenAI 实例。
        image_b64: Base64 编码的图片。

    Returns:
        商品信息分析结果文本。
    """
    from langchain_core.messages import HumanMessage

    msg = HumanMessage(content=[
        {"type": "text", "text": "请分析这张图片中的商品信息，包括：商品类别、颜色、品牌（如果可见）、风格、材质等。用中文回答。"},
        {"type": "image_url", "image_url": {"url": image_b64 if image_b64.startswith("data:") else f"data:image/jpeg;base64,{image_b64}"}},
    ])
    resp = await llm.ainvoke([msg])
    return resp.content


def annotate_image(image_bytes: bytes, annotations: list[dict]) -> bytes:
    """在图片上绘制标注框和标签文字。

    每个标注项的格式为 ``{"box": [x1, y1, x2, y2], "label": "文字"}``。

    Args:
        image_bytes: 原始图片的字节数据。
        annotations: 标注信息列表，每项包含 box 坐标和 label 文字。

    Returns:
        标注后图片的 JPEG 字节数据。
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
