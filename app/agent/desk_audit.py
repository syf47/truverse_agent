"""桌面清洁审核模块。

对比后台参考图和员工上传图，输出是否通过、清洁评分和问题描述。
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from PIL import Image

from app.agent.multimodal import encode_image_to_base64
from app.config import settings
from app.schemas import DeskAuditReferenceResponse, DeskAuditResponse


class DeskAuditError(Exception):
    """桌面清洁审核异常。"""


def _get_reference_image_path() -> Path:
    raw_path = settings.desk_audit_reference_image.strip() or "./data/reference/desk_clean_baseline.jpg"
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _build_audit_llm() -> ChatOpenAI:
    llm_kwargs = dict(
        model=settings.desk_audit_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
    )
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**llm_kwargs)


def _extract_text_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _extract_json_payload(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise DeskAuditError(f"模型未返回有效 JSON: {raw_text}")

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise DeskAuditError(f"解析审核结果失败: {exc}") from exc


def _normalize_score(score: object) -> int:
    if isinstance(score, str):
        score = score.strip().rstrip("%")
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return 0

    if 0 <= numeric <= 1:
        numeric *= 100

    numeric = max(0, min(100, numeric))
    return int(round(numeric))


def _normalize_lines(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [value]
    else:
        items = []

    normalized: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _load_configured_reference_image() -> tuple[bytes, str, str]:
    path = _get_reference_image_path()
    if not path.exists():
        raise DeskAuditError(
            f"参考图不存在: {path}。请先在前端保存一张干净桌面的参考图。"
        )

    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return path.read_bytes(), media_type, "configured"


def _build_audit_prompt(notes: str = "") -> str:
    extra_notes = notes.strip()
    if extra_notes:
        extra_notes = f"\n补充说明：{extra_notes}"

    return f"""你是桌面清洁审核助手，需要比较两张图片：
1. 参考图：干净、符合标准的桌面
2. 待审核图：员工清洁后拍摄的桌面

审核规则：
- 重点检查桌面/桌垫区域是否存在新增的污渍、水渍、液体残留、纸屑、灰尘堆积、明显杂物
- 忽略轻微的拍摄角度差异、光线差异，以及键盘/鼠标等固定办公物品的小幅位置变化
- 如果出现明显液体残留、污渍、未清理干净的痕迹，应判定为不通过
- 评分范围是 0 到 100，80 分及以上且没有明显卫生问题才算通过
- 问题描述必须用中文，尽量指出位置，比如“桌垫中央偏左有水渍残留”

请只返回 JSON，不要带 markdown 代码块，也不要输出额外说明，格式如下：
{{
  "passed": true,
  "score": 92,
  "summary": "桌面整体较干净，达到参考图标准。",
  "issues": [],
  "suggestions": []
}}{extra_notes}
"""


async def analyze_desk_cleanliness(
    submitted_image: bytes,
    submitted_media_type: str,
    reference_image: bytes | None = None,
    reference_media_type: str | None = None,
    notes: str = "",
) -> DeskAuditResponse:
    """分析员工上传桌面图是否达到清洁标准。"""
    if not submitted_image:
        raise DeskAuditError("待审核图片不能为空。")

    reference_mode = "uploaded"
    if reference_image is None:
        reference_image, reference_media_type, reference_mode = _load_configured_reference_image()

    ref_data_uri = encode_image_to_base64(
        reference_image,
        reference_media_type or "image/jpeg",
    )
    submitted_data_uri = encode_image_to_base64(
        submitted_image,
        submitted_media_type or "image/jpeg",
    )

    llm = _build_audit_llm()
    prompt = _build_audit_prompt(notes=notes)
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "text", "text": "下面是参考图（干净标准图）。"},
            {"type": "image_url", "image_url": {"url": ref_data_uri}},
            {"type": "text", "text": "下面是待审核图（员工上传图）。"},
            {"type": "image_url", "image_url": {"url": submitted_data_uri}},
        ]
    )

    try:
        response = await llm.ainvoke([message])
    except Exception as exc:
        raise DeskAuditError(
            "调用视觉模型失败，请确认当前模型支持图片输入，并检查 API 配置。"
        ) from exc

    payload = _extract_json_payload(_extract_text_content(response.content))
    score = _normalize_score(payload.get("score", 0))
    threshold = settings.desk_audit_pass_score
    model_passed = bool(payload.get("passed", False))
    passed = model_passed and score >= threshold

    issues = _normalize_lines(payload.get("issues"))
    suggestions = _normalize_lines(payload.get("suggestions"))

    summary = str(payload.get("summary", "")).strip()
    if not summary:
        summary = (
            "桌面整体清洁情况符合标准。"
            if passed
            else "桌面与参考图存在明显清洁差异，建议重新擦拭后再提交。"
        )

    if not passed and not issues:
        issues = ["桌面与参考图相比存在可见差异，建议复查桌垫和桌面区域。"]

    return DeskAuditResponse(
        passed=passed,
        score=score,
        threshold=threshold,
        summary=summary,
        issues=issues,
        suggestions=suggestions,
        reference_mode=reference_mode,
    )


def get_reference_image_status() -> DeskAuditReferenceResponse:
    """返回当前参考图的保存状态。"""
    path = _get_reference_image_path()
    if not path.exists():
        return DeskAuditReferenceResponse(configured=False)

    return DeskAuditReferenceResponse(
        configured=True,
        filename=path.name,
        updated_at=path.stat().st_mtime,
    )


def save_reference_image(image_bytes: bytes) -> DeskAuditReferenceResponse:
    """保存新的桌面参考图。

    图片会统一转为 JPEG，便于后续稳定加载。
    """
    if not image_bytes:
        raise DeskAuditError("参考图不能为空。")

    target_path = _get_reference_image_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from io import BytesIO

        image = Image.open(BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(target_path, format="JPEG", quality=95)
    except Exception as exc:
        raise DeskAuditError("保存参考图失败，请上传有效的图片文件。") from exc

    return DeskAuditReferenceResponse(
        configured=True,
        filename=target_path.name,
        updated_at=target_path.stat().st_mtime,
    )
