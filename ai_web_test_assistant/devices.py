"""Supported browser/device profiles for screenshot capture."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    slug: str
    playwright_device: str | None = None
    viewport: dict[str, int] | None = None
    user_agent: str | None = None
    is_mobile: bool = False
    device_scale_factor: int = 1


SUPPORTED_DEVICES = (
    DeviceProfile(
        name="Desktop Chrome",
        slug="desktop-chrome",
        viewport={"width": 1440, "height": 1000},
    ),
    DeviceProfile(
        name="iPhone SE",
        slug="iphone-se",
        playwright_device="iPhone SE",
    ),
    DeviceProfile(
        name="iPhone 15",
        slug="iphone-15",
        playwright_device="iPhone 15",
    ),
    DeviceProfile(
        name="Pixel 7",
        slug="pixel-7",
        playwright_device="Pixel 7",
    ),
)


def device_names() -> list[str]:
    """Return user-facing names for all supported devices."""
    return [device.name for device in SUPPORTED_DEVICES]
