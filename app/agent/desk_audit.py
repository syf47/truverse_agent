"""桌面清洁审核模块。

对比后台参考图和员工上传图，输出是否通过、清洁评分和问题描述。
"""

from __future__ import annotations

import json
import mimetypes
from io import BytesIO
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from PIL import Image, ImageDraw, ImageFont

from app.agent.multimodal import encode_image_to_base64
from app.config import settings
from app.schemas import (
    DeskAuditIssueAnnotation,
    DeskAuditReferenceResponse,
    DeskAuditResponse,
)


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


def _normalize_box(box: object, width: int, height: int) -> list[int]:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return []

    try:
        x1, y1, x2, y2 = [float(v) for v in box]
    except (TypeError, ValueError):
        return []

    max_coord = max(abs(x1), abs(y1), abs(x2), abs(y2))
    if max_coord <= 1.0:
        x1, x2 = x1 * width, x2 * width
        y1, y2 = y1 * height, y2 * height
    elif max_coord <= 1000.0:
        x1, x2 = x1 / 1000 * width, x2 / 1000 * width
        y1, y2 = y1 / 1000 * height, y2 / 1000 * height

    left, right = sorted((int(round(x1)), int(round(x2))))
    top, bottom = sorted((int(round(y1)), int(round(y2))))

    left = max(0, min(width - 1, left))
    right = max(0, min(width - 1, right))
    top = max(0, min(height - 1, top))
    bottom = max(0, min(height - 1, bottom))

    if right - left < 4 or bottom - top < 4:
        return []

    return [left, top, right, bottom]


def _normalize_issue_annotations(
    value: object,
    width: int,
    height: int,
) -> list[DeskAuditIssueAnnotation]:
    if isinstance(value, dict):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []

    normalized: list[DeskAuditIssueAnnotation] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        label = str(item.get("label") or item.get("title") or "").strip()
        detail = str(item.get("detail") or item.get("description") or "").strip() or None
        box = _normalize_box(item.get("box"), width, height)

        if not label and detail:
            label = detail
        if not label:
            continue

        normalized.append(
            DeskAuditIssueAnnotation(
                label=label,
                detail=detail,
                box=box,
            )
        )

    return normalized


def _annotate_audit_image(
    image_bytes: bytes,
    issue_annotations: list[DeskAuditIssueAnnotation],
) -> str | None:
    boxed_issues = [issue for issue in issue_annotations if len(issue.box) == 4]
    if not boxed_issues:
        return None

    image = Image.open(BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    draw = ImageDraw.Draw(image)
    width, height = image.size
    stroke_width = max(3, min(width, height) // 150)
    label_padding_x = max(8, stroke_width * 2)
    label_padding_y = max(4, stroke_width)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", max(18, min(width, height) // 28))
    except (OSError, IOError):
        font = ImageFont.load_default()

    for issue in boxed_issues:
        x1, y1, x2, y2 = issue.box
        draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=max(8, stroke_width * 2),
            outline="#ff4d4f",
            width=stroke_width,
        )

        label = issue.label
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = x1
        text_y = max(0, y1 - text_height - label_padding_y * 2 - 6)
        label_box = [
            text_x,
            text_y,
            min(width - 1, text_x + text_width + label_padding_x * 2),
            min(height - 1, text_y + text_height + label_padding_y * 2),
        ]

        draw.rounded_rectangle(
            label_box,
            radius=max(6, stroke_width),
            fill="#ff4d4f",
        )
        draw.text(
            (label_box[0] + label_padding_x, label_box[1] + label_padding_y),
            label,
            fill="white",
            font=font,
        )

    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    return encode_image_to_base64(output.getvalue(), "image/jpeg")


def _build_handling_advice(
    passed: bool,
    summary: str,
    issues: list[str],
    suggestions: list[str],
    issue_annotations: list[DeskAuditIssueAnnotation],
    score: int,
    threshold: int,
) -> tuple[str, dict]:
    if passed:
        advice = (
            f"当前桌面审核通过，评分 {score} 分，达到 {threshold} 分阈值。"
            "可以直接通过本次检查，建议保持当前清洁标准和拍摄角度。"
        )
    else:
        focus_items = issues[:3]
        focus_text = "；".join(focus_items) if focus_items else "请复查桌面与桌垫区域"
        followup = "；".join(suggestions[:3]) if suggestions else "处理完成后重新拍照提交审核"
        advice = (
            f"当前桌面审核未通过，评分 {score} 分，未达到 {threshold} 分阈值。"
            f"优先处理：{focus_text}。建议动作：{followup}。"
        )

    handling_json = {
        "status": "passed" if passed else "failed",
        "score": score,
        "threshold": threshold,
        "summary": summary,
        "issue_count": len(issues),
        "issues": issues,
        "suggestions": suggestions,
        "annotated_issue_count": len([item for item in issue_annotations if len(item.box) == 4]),
        "next_step": "直接通过" if passed else "处理问题后重新提交审核",
    }
    return advice, handling_json


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
  "suggestions": [],
  "issue_annotations": []
}}

issue_annotations 规则：
- 每个元素表示一个不卫生点
- 字段格式为 {{"label":"简短标签","detail":"详细说明","box":[x1,y1,x2,y2]}}
- box 是相对于待审核图的归一化坐标，范围 0 到 1000
- 如果没有明确问题点，issue_annotations 返回空数组
- 如果发现明显污渍、水渍、纸屑等，请尽量给出对应 box
{extra_notes}
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

    with Image.open(BytesIO(submitted_image)) as img:
        width, height = img.size

    issues = _normalize_lines(payload.get("issues"))
    suggestions = _normalize_lines(payload.get("suggestions"))
    issue_annotations = _normalize_issue_annotations(
        payload.get("issue_annotations") or payload.get("annotations"),
        width=width,
        height=height,
    )

    summary = str(payload.get("summary", "")).strip()
    if not summary:
        summary = (
            "桌面整体清洁情况符合标准。"
            if passed
            else "桌面与参考图存在明显清洁差异，建议重新擦拭后再提交。"
        )

    if not passed and not issues:
        issues = ["桌面与参考图相比存在可见差异，建议复查桌垫和桌面区域。"]

    if not issues and issue_annotations:
        issues = [issue.detail or issue.label for issue in issue_annotations]

    annotated_image_base64 = _annotate_audit_image(
        image_bytes=submitted_image,
        issue_annotations=issue_annotations,
    )
    handling_advice, handling_advice_json = _build_handling_advice(
        passed=passed,
        summary=summary,
        issues=issues,
        suggestions=suggestions,
        issue_annotations=issue_annotations,
        score=score,
        threshold=threshold,
    )

    return DeskAuditResponse(
        passed=passed,
        score=score,
        threshold=threshold,
        summary=summary,
        issues=issues,
        suggestions=suggestions,
        handling_advice=handling_advice,
        handling_advice_json=handling_advice_json,
        issue_annotations=issue_annotations,
        annotated_image_base64=annotated_image_base64,
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
