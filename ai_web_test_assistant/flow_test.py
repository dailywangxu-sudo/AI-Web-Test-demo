"""Functional flow checks for psychology test pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ai_web_test_assistant.capture import _context_options, _launch_chromium
from ai_web_test_assistant.devices import SUPPORTED_DEVICES
from ai_web_test_assistant.utils import ensure_directory, normalize_url, timestamp


DEFAULT_STEP_TIMEOUT_MS = 12_000
DEFAULT_RESULT_SCREENSHOT_DIR = Path("screenshots")
START_TEXTS = [
    "开始测试",
    "开始测验",
    "开始实验",
    "立即测试",
    "进入测试",
    "開始測試",
    "開始測驗",
    "開始實驗",
    "立即測試",
    "立即測驗",
    "進入測試",
    "進入測驗",
    "start",
    "begin",
    "take test",
]
NEXT_TEXTS = [
    "下一题",
    "下一步",
    "继续",
    "提交",
    "查看结果",
    "完成",
    "下一題",
    "繼續",
    "送出",
    "查看結果",
    "完成測驗",
    "next",
    "submit",
    "result",
]
SAVE_TEXTS = ["保存", "保存结果", "下载", "儲存", "保存結果", "下載", "download", "save"]
RESULT_TEXTS = ["结果", "测试结果", "分析", "得分", "报告", "类型", "保存", "結果", "測試結果", "報告", "類型", "儲存", "result", "score"]


@dataclass(frozen=True)
class FlowStepResult:
    name: str
    success: bool
    detail: str


@dataclass(frozen=True)
class FunctionalFlowResult:
    steps: list[FlowStepResult]

    @property
    def success(self) -> bool:
        return all(step.success for step in self.steps)


@dataclass(frozen=True)
class ResultScreenshot:
    name: str
    file_path: Path | None
    success: bool
    detail: str
    device_name: str
    stage: str


def run_functional_flow_test(raw_url: str) -> FunctionalFlowResult:
    """Run a best-effort functional flow test on desktop Chrome."""
    url = normalize_url(raw_url)
    steps: list[FlowStepResult] = []
    desktop = SUPPORTED_DEVICES[0]

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        context = browser.new_context(**_context_options(playwright, desktop))
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2_000)
            steps.append(FlowStepResult("首页入口 UI 显示", True, "页面已成功打开并完成首屏加载。"))

            start_result = _click_visible_by_text(page, START_TEXTS)
            steps.append(
                FlowStepResult(
                    "进入题目页面",
                    start_result["clicked"],
                    start_result["detail"],
                )
            )

            if start_result["clicked"]:
                _wait_after_action(page)
                question_page_result = _detect_question_page(page)
                steps.append(question_page_result)

                if not question_page_result.success:
                    steps.append(FlowStepResult("结果页面显示", False, "未检测到题目页面，无法继续验证结果页面。"))
                    steps.append(FlowStepResult("结果保存", False, "未进入结果页面，无法验证保存功能。"))
                    return FunctionalFlowResult(steps=steps)

                question_result = _answer_until_result(page)
                steps.append(question_result)

                save_result = _click_save(page)
                steps.append(save_result)
            else:
                steps.append(FlowStepResult("题目页面显示", False, "未找到可点击的开始测试入口。"))
                steps.append(FlowStepResult("结果页面显示", False, "未进入题目流程，无法验证结果页面。"))
                steps.append(FlowStepResult("结果保存", False, "未进入结果页面，无法验证保存功能。"))
        except PlaywrightTimeoutError as exc:
            steps.append(FlowStepResult("页面流程测试", False, f"页面加载或操作超时：{exc}"))
        except Exception as exc:
            steps.append(FlowStepResult("页面流程测试", False, f"执行异常：{exc}"))
        finally:
            context.close()
            browser.close()

    return FunctionalFlowResult(steps=steps)


def capture_result_screenshots(
    raw_url: str,
    output_dir: str | Path = DEFAULT_RESULT_SCREENSHOT_DIR,
) -> list[ResultScreenshot]:
    """Capture result and saved-result pages across representative scenarios."""
    url = normalize_url(raw_url)
    run_dir = ensure_directory(Path(output_dir) / f"{timestamp()}-results")
    desktop = SUPPORTED_DEVICES[0]
    mobile_devices = SUPPORTED_DEVICES[1:]
    scenarios = [
        (desktop, "偏第一选项", 0),
        (desktop, "偏第二选项", 1),
        (desktop, "轮换选项", -1),
        *[(device, "偏第一选项", 0) for device in mobile_devices],
    ]
    results: list[ResultScreenshot] = []

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            for index, (device, strategy_name, option_strategy) in enumerate(scenarios, start=1):
                context = browser.new_context(**_context_options(playwright, device))
                page = context.new_page()
                result_name = f"{device.name}-{strategy_name}-结果页"
                saved_name = f"{device.name}-{strategy_name}-保存后"
                result_path = run_dir / f"{index:02d}-{device.slug}-result.png"
                saved_path = run_dir / f"{index:02d}-{device.slug}-saved.png"

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(2_000)

                    start_result = _click_visible_by_text(page, START_TEXTS)
                    if not start_result["clicked"]:
                        results.append(
                            ResultScreenshot(result_name, None, False, "未找到开始测试入口。", device.name, "result")
                        )
                        results.append(
                            ResultScreenshot(saved_name, None, False, "未进入结果页，无法生成保存后截图。", device.name, "saved")
                        )
                        continue

                    _wait_after_action(page)
                    result_step = _answer_until_result(page, option_strategy=option_strategy)
                    if not result_step.success:
                        results.append(
                            ResultScreenshot(result_name, None, False, result_step.detail, device.name, "result")
                        )
                        results.append(
                            ResultScreenshot(saved_name, None, False, "未进入结果页，无法生成保存后截图。", device.name, "saved")
                        )
                        continue

                    page.screenshot(path=str(result_path), full_page=True)
                    results.append(
                        ResultScreenshot(result_name, result_path, True, "已生成结果页截图。", device.name, "result")
                    )

                    save_result = _click_save(page)
                    page.screenshot(path=str(saved_path), full_page=True)
                    detail = "已生成点击保存后的截图。" if save_result.success else f"已生成保存验证现场截图；{save_result.detail}"
                    results.append(
                        ResultScreenshot(saved_name, saved_path, save_result.success, detail, device.name, "saved")
                    )
                except Exception as exc:
                    results.append(
                        ResultScreenshot(result_name, None, False, f"生成结果页截图失败：{exc}", device.name, "result")
                    )
                    results.append(
                        ResultScreenshot(saved_name, None, False, f"生成保存后截图失败：{exc}", device.name, "saved")
                    )
                finally:
                    context.close()
        finally:
            browser.close()

    return results


def _detect_question_page(page) -> FlowStepResult:
    has_question = page.evaluate(
        """
        (blockedTexts) => {
            const blocked = blockedTexts.map((text) => text.toLowerCase());
            const selector = 'label,button,a,[role="button"],[role="radio"],input[type="radio"],input[type="checkbox"],[onclick],[tabindex],div,span';
            const elements = Array.from(document.querySelectorAll(selector));
            const bodyText = document.body.innerText.toLowerCase();

            const isVisible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    rect.width > 0 &&
                    rect.height > 0;
            };

            const hasOption = elements.some((element) => {
                if (!isVisible(element)) return false;
                const text = [
                    element.innerText,
                    element.value,
                    element.getAttribute('aria-label'),
                    element.getAttribute('title')
                ].filter(Boolean).join(' ').trim().toLowerCase();
                return text && !blocked.some((item) => text.includes(item));
            });

            return hasOption ||
                bodyText.includes('题目') ||
                bodyText.includes('question') ||
                bodyText.includes('选项') ||
                bodyText.includes('option') ||
                bodyText.includes('題目') ||
                bodyText.includes('選項');
        }
        """,
        START_TEXTS + NEXT_TEXTS + SAVE_TEXTS,
    )

    if has_question:
        return FlowStepResult("题目页面显示", True, "点击开始后检测到题目或可回答选项。")

    return FlowStepResult("题目页面显示", False, "点击开始后未检测到题目内容或可回答选项。")


def _answer_until_result(page, option_strategy: int = 0) -> FlowStepResult:
    saw_question = False

    for step_index in range(16):
        if _looks_like_result_page(page):
            return FlowStepResult("结果页面显示", True, "已检测到结果页相关内容。")

        option_index = step_index if option_strategy < 0 else option_strategy
        option_result = _click_answer_option(page, option_index=option_index)
        if option_result["clicked"]:
            saw_question = True
            _wait_after_action(page)

        next_result = _click_visible_by_text(page, NEXT_TEXTS)
        if next_result["clicked"]:
            saw_question = True
            _wait_after_action(page)
            continue

        if option_result["clicked"]:
            continue

        break

    if _looks_like_result_page(page):
        return FlowStepResult("结果页面显示", True, "已检测到结果页相关内容。")

    if saw_question:
        return FlowStepResult("结果页面显示", False, "已进入题目流程，但未能自动推进到结果页面。")

    return FlowStepResult("结果页面显示", False, "点击开始后未检测到可回答的题目选项。")


def _click_save(page) -> FlowStepResult:
    if not _looks_like_result_page(page):
        return FlowStepResult("结果保存", False, "当前页面未检测到结果页内容，跳过保存验证。")

    result = _click_visible_by_text(page, SAVE_TEXTS)
    if not result["clicked"]:
        _scroll_to_bottom(page)
        result = _click_visible_by_text(page, SAVE_TEXTS)

    if result["clicked"]:
        _wait_after_action(page)
        return FlowStepResult("结果保存", True, result["detail"])

    return FlowStepResult("结果保存", False, "结果页未找到保存、下载或保存结果按钮。")


def _click_visible_by_text(page, texts: list[str]) -> dict:
    locator_result = _click_locator_by_text(page, texts)
    if locator_result["clicked"]:
        return locator_result

    match = page.evaluate(
        """
        (texts) => {
            const targets = texts.map((text) => text.toLowerCase());
            const selector = 'button,a,[role="button"],input[type="button"],input[type="submit"],label,[onclick],[tabindex],div,span';
            const elements = Array.from(document.querySelectorAll(selector));

            const isVisible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                const isClickable = ['BUTTON', 'A', 'LABEL', 'INPUT'].includes(element.tagName) ||
                    element.getAttribute('role') === 'button' ||
                    element.hasAttribute('onclick') ||
                    element.hasAttribute('tabindex') ||
                    style.cursor === 'pointer';
                return style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    isClickable &&
                    rect.width > 0 &&
                    rect.height > 0 &&
                    rect.width < window.innerWidth * 0.95 &&
                    rect.height < window.innerHeight * 0.8;
            };

            for (const element of elements) {
                if (!isVisible(element)) continue;
                const text = [
                    element.innerText,
                    element.value,
                    element.getAttribute('aria-label'),
                    element.getAttribute('title')
                ].filter(Boolean).join(' ').trim();
                const lowerText = text.toLowerCase();
                if (!lowerText) continue;

                if (targets.some((target) => lowerText.includes(target))) {
                    const clickable = element.closest('button,a,[role="button"],label,[onclick],[tabindex]') || element;
                    clickable.scrollIntoView({ block: 'center', inline: 'center' });
                    return {
                        clicked: true,
                        text,
                        detail: `已点击「${text}」。`
                    };
                }
            }

            return {
                clicked: false,
                detail: `未找到可点击入口：${texts.join(' / ')}。`
            };
        }
        """,
        texts,
    )
    if match["clicked"]:
        _dom_click_by_text(page, texts)

    return match


def _click_answer_option(page, option_index: int = 0) -> dict:
    match = page.evaluate(
        """
        (optionIndex) => {
            const blocked = ['开始', '開始', '下一', '继续', '繼續', '提交', '结果', '結果', '保存', '儲存', '下载', '下載', 'start', 'next', 'submit', 'save'];
            const selector = 'label,button,[role="button"],[role="radio"],input[type="radio"],input[type="checkbox"],[onclick],[tabindex]';
            const elements = Array.from(document.querySelectorAll(selector));

            const isVisible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    rect.width > 0 &&
                    rect.height > 0;
            };

            const candidates = [];
            for (const element of elements) {
                if (!isVisible(element)) continue;
                const text = [
                    element.innerText,
                    element.value,
                    element.getAttribute('aria-label'),
                    element.getAttribute('title')
                ].filter(Boolean).join(' ').trim();
                const lowerText = text.toLowerCase();
                if (blocked.some((item) => lowerText.includes(item.toLowerCase()))) continue;
                candidates.push({ element, text });
            }

            if (!candidates.length) {
                return { clicked: false, detail: '未找到可点击的题目选项。' };
            }

            const selected = candidates[Math.abs(optionIndex) % candidates.length];
            selected.element.scrollIntoView({ block: 'center', inline: 'center' });
            return {
                clicked: true,
                text: selected.text,
                optionIndex,
                detail: selected.text ? `已选择题目选项「${selected.text}」。` : '已选择一个题目选项。'
            };
        }
        """,
        option_index,
    )
    if match["clicked"]:
        clicked_by_locator = _click_locator_by_text(page, [match.get("text", "")])
        if not clicked_by_locator["clicked"]:
            _dom_click_answer_by_index(page, option_index)

    return match


def _looks_like_result_page(page) -> bool:
    body_text = page.evaluate("() => document.body.innerText.toLowerCase()")
    current_url = page.url.lower()
    return any(text.lower() in body_text for text in RESULT_TEXTS) or "result" in current_url


def _wait_after_action(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=DEFAULT_STEP_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(1_200)


def _scroll_to_bottom(page) -> None:
    page.evaluate("() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' })")
    page.wait_for_timeout(800)


def _click_locator_by_text(page, texts: list[str]) -> dict:
    for text in texts:
        if not text:
            continue

        for locator_factory in (
            lambda value: page.get_by_role("button", name=value),
            lambda value: page.get_by_text(value, exact=False),
        ):
            try:
                locator = locator_factory(text)
                if locator.count() <= 0:
                    continue

                locator.first.click(timeout=3_000, force=True)
                return {
                    "clicked": True,
                    "text": text,
                    "detail": f"已点击「{text}」。",
                }
            except Exception:
                continue

    return {
        "clicked": False,
        "detail": f"未找到可点击入口：{' / '.join(texts)}。",
    }


def _dom_click_by_text(page, texts: list[str]) -> None:
    page.evaluate(
        """
        (texts) => {
            const targets = texts.map((text) => text.toLowerCase());
            const elements = Array.from(document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"],label,[onclick],[tabindex],div,span'));
            const element = elements.find((candidate) => {
                const text = [
                    candidate.innerText,
                    candidate.value,
                    candidate.getAttribute('aria-label'),
                    candidate.getAttribute('title')
                ].filter(Boolean).join(' ').trim().toLowerCase();
                return text && targets.some((target) => text.includes(target));
            });

            if (!element) return;
            const clickable = element.closest('button,a,[role="button"],label,[onclick],[tabindex]') || element;
            clickable.scrollIntoView({ block: 'center', inline: 'center' });
            clickable.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
            clickable.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
            clickable.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            if (typeof clickable.click === 'function') {
                clickable.click();
            }
        }
        """,
        texts,
    )


def _dom_click_answer_by_index(page, option_index: int = 0) -> None:
    page.evaluate(
        """
        (optionIndex) => {
            const blocked = ['开始', '開始', '下一', '继续', '繼續', '提交', '结果', '結果', '保存', '儲存', '下载', '下載', 'start', 'next', 'submit', 'save'];
            const elements = Array.from(document.querySelectorAll('label,button,[role="button"],[role="radio"],input[type="radio"],input[type="checkbox"],[onclick],[tabindex]'));
            const candidates = elements.filter((candidate) => {
                const style = window.getComputedStyle(candidate);
                const rect = candidate.getBoundingClientRect();
                if (style.visibility === 'hidden' || style.display === 'none' || rect.width <= 0 || rect.height <= 0) return false;
                const text = [
                    candidate.innerText,
                    candidate.value,
                    candidate.getAttribute('aria-label'),
                    candidate.getAttribute('title')
                ].filter(Boolean).join(' ').trim().toLowerCase();
                return !blocked.some((item) => text.includes(item.toLowerCase()));
            });

            const element = candidates[Math.abs(optionIndex) % candidates.length];
            if (!element) return;
            element.scrollIntoView({ block: 'center', inline: 'center' });
            element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
            element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
            element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            if (typeof element.click === 'function') {
                element.click();
            }
        }
        """,
        option_index,
    )
