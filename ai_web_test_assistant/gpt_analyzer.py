"""OpenAI-powered screenshot analysis for test reporting."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from ai_web_test_assistant.capture import ScreenshotResult
from ai_web_test_assistant.flow_test import FunctionalFlowResult


DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class AnalysisResult:
    ui_report: str
    responsive_report: str
    bug_report: str
    ui_issues: list[str]
    responsive_issues: list[str]


def analyze_screenshots(
    results: list[ScreenshotResult],
    functional_result: FunctionalFlowResult | None = None,
) -> AnalysisResult:
    """Analyze successful screenshots and return report text."""
    successful_results = [result for result in results if result.success and result.file_path]
    if not successful_results:
        return AnalysisResult(
            ui_report="没有成功生成截图，无法进行 UI 分析。",
            responsive_report="没有成功生成截图，无法进行移动端适配分析。",
            bug_report="没有可分析的截图，因此未生成缺陷报告。",
            ui_issues=[],
            responsive_issues=[],
        )

    load_dotenv()
    load_dotenv("env.env")
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return AnalysisResult(
            ui_report="未配置 OPENAI_API_KEY，已跳过 AI 分析。",
            responsive_report="未配置 OPENAI_API_KEY，已跳过适配分析。",
            bug_report="未配置 OPENAI_API_KEY，无法生成 AI 缺陷报告。",
            ui_issues=["请在项目根目录创建 .env 文件，并配置 OPENAI_API_KEY。"],
            responsive_issues=[],
        )

    try:
        client = OpenAI(api_key=api_key)
    except Exception as exc:
        return AnalysisResult(
            ui_report="OpenAI 客户端初始化失败，已跳过 AI 分析。",
            responsive_report="OpenAI 客户端初始化失败，已跳过适配分析。",
            bug_report=f"OpenAI 客户端初始化失败，无法生成 AI 缺陷报告。\n\n失败原因：{exc}",
            ui_issues=["OpenAI 客户端初始化失败，请检查 API Key 配置。"],
            responsive_issues=[],
        )
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": _build_content(successful_results, functional_result),
                }
            ],
        )
    except Exception as exc:
        return _analysis_error(exc)

    return _parse_analysis(response.output_text)


def _analysis_error(exc: Exception) -> AnalysisResult:
    message = str(exc)
    if "insufficient_quota" in message or "exceeded your current quota" in message or "429" in message:
        reason = "OpenAI API 当前配额不足或账单额度不可用，已跳过 AI 分析。"
        suggestion = "请检查 OpenAI 账号套餐、账单状态或更换可用 API Key 后重新测试。"
    else:
        reason = "OpenAI API 调用失败，已跳过 AI 分析。"
        suggestion = "请检查网络、模型名称、API Key 权限后重新测试。"

    return AnalysisResult(
        ui_report=f"{reason}\n\n{suggestion}",
        responsive_report=f"{reason}\n\n{suggestion}",
        bug_report=f"截图与页面流程测试已完成，但 AI 缺陷报告未生成。\n\n失败原因：{message}\n\n处理建议：{suggestion}",
        ui_issues=[reason],
        responsive_issues=[reason],
    )


def _build_content(
    results: list[ScreenshotResult],
    functional_result: FunctionalFlowResult | None = None,
) -> list[dict]:
    content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                "你是一名高级 Web 测试工程师，正在测试一个心理测试网站。"
                "请基于 Desktop Chrome、iPhone SE、iPhone 15、Pixel 7 的截图和页面流程测试结果进行测试分析。"
                "重点关注：页面可见功能入口、题目/按钮/结果区域的 UI 表现、移动端适配、"
                "遮挡、溢出、字号、间距、点击区域、首屏关键内容是否可见。"
                "同时关注：是否能正常进入题目页面、是否能正常显示结果、结果页面点击保存是否能正常保存。"
                "只返回合法 JSON，不要使用 Markdown 代码块。JSON 字段必须为："
                "ui_report: string，responsive_report: string，bug_report: string，"
                "ui_issues: string[]，responsive_issues: string[]。"
                "所有内容使用中文。bug_report 中每个缺陷请包含严重级别、影响设备、现象、预期结果、实际结果和建议。"
            ),
        }
    ]

    if functional_result:
        content.append(
            {
                "type": "input_text",
                "text": _functional_summary(functional_result),
            }
        )

    for result in results:
        content.append(
            {
                "type": "input_text",
                "text": f"Device: {result.device_name}",
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": _image_data_url(Path(result.file_path)),
            }
        )

    return content


def _functional_summary(functional_result: FunctionalFlowResult) -> str:
    lines = ["页面流程测试结果："]
    for step in functional_result.steps:
        status = "成功" if step.success else "失败"
        lines.append(f"- {step.name}: {status}。{step.detail}")

    return "\n".join(lines)


def _image_data_url(path: Path) -> str:
    image_bytes = path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _parse_analysis(output_text: str) -> AnalysisResult:
    normalized_text = _strip_json_fence(output_text)
    try:
        payload = json.loads(normalized_text)
    except json.JSONDecodeError:
        return AnalysisResult(
            ui_report=output_text.strip() or "AI 未返回 UI 报告内容。",
            responsive_report="AI 未返回结构化适配报告内容。",
            bug_report=output_text.strip() or "AI 未返回缺陷报告内容。",
            ui_issues=[],
            responsive_issues=[],
        )

    return AnalysisResult(
        ui_report=str(payload.get("ui_report") or "未发现明确 UI 问题。"),
        responsive_report=str(payload.get("responsive_report") or "未发现明确适配问题。"),
        bug_report=str(payload.get("bug_report") or "未发现明确缺陷。"),
        ui_issues=_string_list(payload.get("ui_issues")),
        responsive_issues=_string_list(payload.get("responsive_issues")),
    )


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item).strip() for item in value if str(item).strip()]


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        stripped = stripped.removesuffix("```").strip()

    return stripped
