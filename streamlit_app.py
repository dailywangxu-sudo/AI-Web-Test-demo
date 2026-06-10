"""Streamlit entry point for the AI Web Test Assistant demo."""

from __future__ import annotations

import streamlit as st

from ai_web_test_assistant.capture import capture_screenshots
from ai_web_test_assistant.capture import ScreenshotResult
from ai_web_test_assistant.flow_test import (
    FunctionalFlowResult,
    ResultScreenshot,
    capture_result_screenshots,
    run_functional_flow_test,
)
from ai_web_test_assistant.gpt_analyzer import AnalysisResult, analyze_screenshots
from ai_web_test_assistant.report import build_markdown_report, capture_errors
from ai_web_test_assistant.utils import normalize_url


st.set_page_config(
    page_title="AI web 测试助手",
    page_icon="AI",
    layout="wide",
)


def main() -> None:
    _apply_styles()

    st.title("AI web 测试助手")
    st.caption("面向asksoul.me网站的自动测试截图、移动端适配检查与 AI 缺陷分析。")

    with st.sidebar:
        st.header("AI测试")
        raw_url = st.text_input(
            "测试页面 URL",
            placeholder="https://example.com/test",
        )
        run_button = st.button("开始测试", type="primary", use_container_width=True)

    st.subheader("测试流程")
    st.write(
        "输入 URL -> 首页 UI 截图 -> 多设备截图 -> 题目流程测试 -> 结果页测试 -> "
        "多结果截图 -> 保存结果测试 -> AI 分析 -> UI 报告 -> 适配报告 -> 缺陷报告"
    )

    if not run_button:
        st.info("请在左侧输入测试页面 URL，然后点击“开始测试”。")
        return

    try:
        url = normalize_url(raw_url)
    except ValueError as exc:
        st.error(str(exc))
        return

    with st.status("正在执行自动测试...", expanded=True) as status:
        st.write("1. 页面截图：Playwright 正在打开目标页面。")
        st.write("2. 多设备截图：Desktop Chrome、iPhone SE、iPhone 15、Pixel 7。")
        screenshot_results = capture_screenshots(url)
        st.write("3. 页面流程测试：验证入口、题目页、结果页和保存结果。")
        functional_result = run_functional_flow_test(url)
        st.write("4. 结果页截图：模拟不同选项组合并保存结果页截图。")
        result_screenshots = capture_result_screenshots(url)
        status.update(label="截图和页面流程测试完成，等待 AI 分析。", state="running")

    errors = capture_errors(screenshot_results)
    if errors:
        st.warning("部分设备截图失败。")
        for error in errors:
            st.code(error)

    successful_results = [result for result in screenshot_results if result.success and result.file_path]
    if successful_results:
        st.subheader("首页与多设备截图")
        columns = st.columns(2)
        for index, result in enumerate(successful_results):
            with columns[index % 2]:
                st.image(str(result.file_path), caption=result.device_name, use_container_width=True)
    else:
        st.error("没有成功生成截图，无法继续 AI 分析。")
        return

    st.subheader("页面流程测试")
    _render_flow_result(functional_result)

    st.subheader("结果页与保存后截图")
    _render_result_screenshots(result_screenshots)

    with st.status("正在进行 AI 分析...", expanded=True) as status:
        st.write("5. AI 分析：识别功能、UI 与移动端适配风险。")
        st.write("6. 生成 UI 报告。")
        st.write("7. 生成适配报告。")
        st.write("8. 生成缺陷报告。")
        analysis_inputs = screenshot_results + _result_screenshots_as_analysis_inputs(result_screenshots)
        analysis = _safe_analyze_screenshots(analysis_inputs, functional_result)
        status.update(label="AI 测试分析完成。", state="complete")

    report_markdown = build_markdown_report(
        url,
        screenshot_results,
        analysis,
        functional_result,
        result_screenshots,
    )

    ui_tab, responsive_tab, bug_tab = st.tabs(["UI问题列表", "适配问题列表", "缺陷报告下载"])

    with ui_tab:
        st.markdown("### UI 测试报告")
        st.markdown(analysis.ui_report)
        st.markdown("### UI 问题列表")
        _render_issue_list(analysis.ui_issues)

    with responsive_tab:
        st.markdown("### 移动端适配报告")
        st.markdown(analysis.responsive_report)
        st.markdown("### 适配问题列表")
        _render_issue_list(analysis.responsive_issues)

    with bug_tab:
        st.markdown("### 缺陷报告")
        st.markdown(analysis.bug_report)
        st.download_button(
            label="下载缺陷报告",
            data=report_markdown,
            file_name="ai-web-test-defect-report.md",
            mime="text/markdown",
            use_container_width=True,
        )


def _render_issue_list(issues: list[str]) -> None:
    if not issues:
        st.success("暂未发现明确问题。")
        return

    for index, issue in enumerate(issues, start=1):
        st.markdown(f"{index}. {issue}")


def _render_flow_result(functional_result: FunctionalFlowResult) -> None:
    for step in functional_result.steps:
        if step.success:
            st.success(f"{step.name}：{step.detail}")
        else:
            st.error(f"{step.name}：{step.detail}")


def _render_result_screenshots(result_screenshots: list[ResultScreenshot]) -> None:
    result_page_screenshots = [result for result in result_screenshots if result.stage == "result"]
    saved_page_screenshots = [result for result in result_screenshots if result.stage == "saved"]

    result_tab, saved_tab = st.tabs(["结果页适配截图", "保存后截图"])

    with result_tab:
        _render_screenshot_grid(result_page_screenshots)

    with saved_tab:
        _render_screenshot_grid(saved_page_screenshots)


def _render_screenshot_grid(items: list[ResultScreenshot]) -> None:
    displayable_results = [result for result in items if result.file_path]
    failed_without_image = [result for result in items if not result.success and not result.file_path]

    if displayable_results:
        columns = st.columns(2)
        for index, result in enumerate(displayable_results):
            with columns[index % 2]:
                st.image(str(result.file_path), caption=result.name, use_container_width=True)
                if not result.success:
                    st.warning(result.detail)

    for result in failed_without_image:
        st.warning(f"{result.name}：{result.detail}")

    if not displayable_results and not failed_without_image:
        st.info("暂未生成截图。")


def _result_screenshots_as_analysis_inputs(
    result_screenshots: list[ResultScreenshot],
) -> list[ScreenshotResult]:
    return [
        ScreenshotResult(
            device_name=result.name,
            device_slug=f"result-{index}",
            file_path=result.file_path,
            success=True,
        )
        for index, result in enumerate(result_screenshots, start=1)
        if result.success and result.file_path
    ]


def _safe_analyze_screenshots(
    screenshot_results,
    functional_result: FunctionalFlowResult,
) -> AnalysisResult:
    try:
        return analyze_screenshots(screenshot_results, functional_result)
    except Exception as exc:
        message = f"AI 分析暂不可用：{exc}"
        st.warning(message)
        return AnalysisResult(
            ui_report="截图已完成，但 AI 分析暂不可用。请检查 OPENAI_API_KEY、网络连接或模型配置。",
            responsive_report="截图已完成，但 AI 适配分析暂不可用。请检查 OPENAI_API_KEY、网络连接或模型配置。",
            bug_report=(
                "截图已完成，但未能生成 AI 缺陷报告。\n\n"
                f"失败原因：{exc}\n\n"
                "处理建议：在项目根目录创建 .env 文件，配置 OPENAI_API_KEY 后重新点击开始测试。"
            ),
            ui_issues=["AI 分析失败，请检查 OpenAI API 配置后重试。"],
            responsive_issues=["AI 分析失败，请检查 OpenAI API 配置后重试。"],
        )


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="InputInstructions"] {
            display: none;
        }

        [data-testid="stSidebar"] input {
            font-size: 14px;
            line-height: 1.35;
        }

        [data-testid="stSidebar"] .stTextInput {
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
