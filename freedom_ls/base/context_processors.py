import colorsys
import hashlib

from django.conf import settings
from django.http import HttpRequest

from freedom_ls.base.git_utils import get_current_branch
from freedom_ls.deployment.config import config as deployment_config


def branch_name_to_color(name: str) -> str:
    hash_hex = hashlib.md5(name.encode()).hexdigest()  # noqa: S324  # nosec B324
    hue = int(hash_hex[:8], 16) % 360
    sat = 0.45 + (int(hash_hex[8:16], 16) % 100) / 100 * 0.30
    light = 0.40 + (int(hash_hex[16:24], 16) % 100) / 100 * 0.20

    r, g, b = colorsys.hls_to_rgb(hue / 360, light, sat)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def get_text_color(bg_hex: str) -> str:
    r = int(bg_hex[1:3], 16) / 255
    g = int(bg_hex[3:5], 16) / 255
    b = int(bg_hex[5:7], 16) / 255

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
    return "#000000" if luminance > 0.179 else "#ffffff"


def debug_branch_info(_request: HttpRequest) -> dict[str, str]:
    if not settings.DEBUG:
        return {}
    branch = get_current_branch()
    if branch is None:
        return {}
    bg_color = branch_name_to_color(branch)
    return {
        "debug_branch_name": branch,
        "debug_branch_color": bg_color,
        "debug_branch_text_color": get_text_color(bg_color),
    }


def posthog_config(_request: HttpRequest) -> dict[str, str | None]:
    """
    Context processor that provides PostHog configuration.

    Args:
        _request: The current HttpRequest (required by Django context processors)

    Returns:
        dict: posthog_api_key, posthog_api_host, and posthog_ui_host resolved
        through freedom_ls.deployment.config.
    """
    return {
        "posthog_api_key": deployment_config.POSTHOG_API_KEY,
        "posthog_api_host": deployment_config.POSTHOG_API_HOST,
        "posthog_ui_host": deployment_config.POSTHOG_UI_HOST,
    }
