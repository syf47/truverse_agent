"""图片相关工具：OCR、图片分析、图片标注。"""

from __future__ import annotations

from langchain_core.tools import tool

from app.agent.tools.base import get_llm


@tool
async def ocr_image(image_base64: str) -> str:
    """对图片进行 OCR 文字提取。输入为 Base64 编码的图片。"""
    from app.agent.multimodal import ocr_with_vision

    return await ocr_with_vision(get_llm(), image_base64)


@tool
async def analyze_image(image_base64: str) -> str:
    """分析图片中的商品信息，包括类别、颜色、品牌、风格等。输入为 Base64 编码的图片。"""
    from app.agent.multimodal import analyze_image_with_vision

    return await analyze_image_with_vision(get_llm(), image_base64)


@tool
async def annotate_image(image_base64: str, annotations_json: str) -> str:
    """在图片上标注信息。

    annotations_json 为 JSON 数组，每项包含 box([x1,y1,x2,y2]) 和 label。
    返回标注后图片的 Base64 编码。
    """
    import json

    from app.agent.multimodal import annotate_image as do_annotate
    from app.agent.multimodal import decode_base64_image, encode_image_to_base64

    image_bytes = decode_base64_image(image_base64)
    annotations = json.loads(annotations_json)
    result_bytes = do_annotate(image_bytes, annotations)
    return encode_image_to_base64(result_bytes)
