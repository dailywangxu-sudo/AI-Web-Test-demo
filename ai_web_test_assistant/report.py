"""Report formatting helpers for the AI Web Test Assistant demo."""

from __future__ import annotations

from ai_web_test_assistant.capture import ScreenshotResult
from ai_web_test_assistant.flow_test import FunctionalFlowResult, ResultScreenshot
from ai_web_test_assistant.gpt_analyzer import AnalysisResult


def build_markdown_report(
    url: str,
    screenshot_results: list[ScreenshotResult],
    analysis: AnalysisResult,
    functional_result: FunctionalFlowResult | None = None,
    result_screenshots: list[ResultScreenshot] | None = None,
) -> str:
    """Build a downloadable markdown report."""
    lines = [
        "# AI Web 测试报告",
        "",
        f"测试地址：{url}",
        "",
        "## 截图结果",
        "",
    ]

    for result in screenshot_results:
        status = "成功" if result.success else "失败"
        path = result.file_path.as_posix() if result.file_path else "N/A"
        lines.append(f"- {result.device_name}: {status} ({path})")
        if result.error:
            lines.append(f"  错误：{result.error}")

    if functional_result:
        lines.extend(["", "## 页面流程测试结果", ""])
        for step in functional_result.steps:
            status = "成功" if step.success else "失败"
            lines.append(f"- {step.name}: {status}")
            lines.append(f"  说明：{step.detail}")

    if result_screenshots:
        lines.extend(["", "## 结果页截图", ""])
        for result in result_screenshots:
            status = "成功" if result.success else "失败"
            path = result.file_path.as_posix() if result.file_path else "N/A"
            lines.append(f"- {result.name}: {status} ({path})")
            lines.append(f"  设备：{result.device_name}")
            lines.append(f"  阶段：{'点击保存后' if result.stage == 'saved' else '结果页'}")
            lines.append(f"  说明：{result.detail}")

    lines.extend(
        [
            "",
            "## UI 测试报告",
            "",
            analysis.ui_report,
            "",
            "## UI 问题列表",
            "",
            *_format_issue_lines(analysis.ui_issues),
            "",
            "## 移动端适配报告",
            "",
            analysis.responsive_report,
            "",
            "## 适配问题列表",
            "",
            *_format_issue_lines(analysis.responsive_issues),
            "",
            "## 缺陷报告",
            "",
            analysis.bug_report,
            "",
        ]
    )

    return "\n".join(lines)


def capture_errors(results: list[ScreenshotResult]) -> list[str]:
    """Return human-readable capture errors."""
    return [
        f"{result.device_name}: {result.error}"
        for result in results
        if not result.success and result.error
    ]


def _format_issue_lines(issues: list[str]) -> list[str]:
    if not issues:
        return ["- 暂未发现明确问题。"]

    return [f"- {issue}" for issue in issues]
