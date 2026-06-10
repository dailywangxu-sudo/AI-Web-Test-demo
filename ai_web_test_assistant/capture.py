"""Playwright screenshot capture helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ai_web_test_assistant.devices import DeviceProfile, SUPPORTED_DEVICES
from ai_web_test_assistant.utils import ensure_directory, normalize_url, timestamp


DEFAULT_SCREENSHOT_DIR = Path("screenshots")
DEFAULT_TIMEOUT_MS = 30_000


@dataclass(frozen=True)
class ScreenshotResult:
    device_name: str
    device_slug: str
    file_path: Path | None
    success: bool
    error: str | None = None


def capture_screenshots(
    raw_url: str,
    output_dir: str | Path = DEFAULT_SCREENSHOT_DIR,
) -> list[ScreenshotResult]:
    """Capture screenshots for all supported devices."""
    url = normalize_url(raw_url)
    run_id = timestamp()
    screenshot_dir = ensure_directory(Path(output_dir) / run_id)
    results: list[ScreenshotResult] = []

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)

        try:
            for device in SUPPORTED_DEVICES:
                result = _capture_device_screenshot(
                    playwright=playwright,
                    browser=browser,
                    device=device,
                    url=url,
                    screenshot_dir=screenshot_dir,
                )
                results.append(result)
        finally:
            browser.close()

    return results


def _launch_chromium(playwright):
    try:
        return playwright.chromium.launch(headless=True)
    except Exception:
        fallback_path = _find_chromium_executable()
        if fallback_path is None:
            raise

        return playwright.chromium.launch(
            headless=True,
            executable_path=str(fallback_path),
        )


def _find_chromium_executable() -> Path | None:
    candidates = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        cache_dir = Path(local_app_data) / "ms-playwright"
        candidates.extend(
            sorted(
                cache_dir.glob("chromium-*/chrome-win64/chrome.exe"),
                reverse=True,
            )
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _capture_device_screenshot(
    playwright,
    browser,
    device: DeviceProfile,
    url: str,
    screenshot_dir: Path,
) -> ScreenshotResult:
    context_options = _context_options(playwright, device)
    page = None
    context = None
    file_path = screenshot_dir / f"{device.slug}.png"

    try:
        context = browser.new_context(**context_options)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=DEFAULT_TIMEOUT_MS)
        page.screenshot(path=str(file_path), full_page=True)

        return ScreenshotResult(
            device_name=device.name,
            device_slug=device.slug,
            file_path=file_path,
            success=True,
        )
    except PlaywrightTimeoutError as exc:
        return ScreenshotResult(
            device_name=device.name,
            device_slug=device.slug,
            file_path=None,
            success=False,
            error=f"Page load timed out: {exc}",
        )
    except Exception as exc:
        return ScreenshotResult(
            device_name=device.name,
            device_slug=device.slug,
            file_path=None,
            success=False,
            error=str(exc),
        )
    finally:
        if page is not None:
            page.close()
        if context is not None:
            context.close()


def _context_options(playwright, device: DeviceProfile) -> dict:
    if device.playwright_device and device.playwright_device in playwright.devices:
        return dict(playwright.devices[device.playwright_device])

    options: dict = {
        "viewport": device.viewport or {"width": 390, "height": 844},
        "device_scale_factor": device.device_scale_factor,
        "is_mobile": device.is_mobile,
    }
    if device.user_agent:
        options["user_agent"] = device.user_agent

    return options
