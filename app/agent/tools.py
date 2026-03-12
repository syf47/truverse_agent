"""Agent tools: OCR, image analysis, annotation, context search, product query."""

from __future__ import annotations

from langchain_core.tools import tool

# These will be injected at graph construction time
_llm = None
_context_manager = None


def set_dependencies(llm, context_manager) -> None:
    global _llm, _context_manager
    _llm = llm
    _context_manager = context_manager


@tool
async def ocr_image(image_base64: str) -> str:
    """对图片进行 OCR 文字提取。输入为 base64 编码的图片。"""
    from app.agent.multimodal import ocr_with_vision
    return await ocr_with_vision(_llm, image_base64)


@tool
async def analyze_image(image_base64: str) -> str:
    """分析图片中的商品信息，包括类别、颜色、品牌、风格等。输入为 base64 编码的图片。"""
    from app.agent.multimodal import analyze_image_with_vision
    return await analyze_image_with_vision(_llm, image_base64)


@tool
async def annotate_image(image_base64: str, annotations_json: str) -> str:
    """在图片上标注信息。annotations_json 为 JSON 数组，每项包含 box([x1,y1,x2,y2]) 和 label。返回标注后图片的 base64。"""
    import json

    from app.agent.multimodal import annotate_image as do_annotate
    from app.agent.multimodal import decode_base64_image, encode_image_to_base64

    image_bytes = decode_base64_image(image_base64)
    annotations = json.loads(annotations_json)
    result_bytes = do_annotate(image_bytes, annotations)
    return encode_image_to_base64(result_bytes)


@tool
def search_context(query: str, session_id: str = "") -> str:
    """从上下文知识库中搜索与查询相关的信息。"""
    if _context_manager is None:
        return "上下文管理器未初始化"
    context = _context_manager.get_context(session_id, query)
    return context or "未找到相关上下文信息"


@tool
def query_products(query: str) -> str:
    """查询商品信息。当前为 placeholder，后续接入 ClickHouse。"""
    return f"[商品查询 placeholder] 查询: {query} — 商品数据库尚未接入，请稍后再试。"
