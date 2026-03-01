from allauth.account.adapter import get_adapter

from django.conf import settings
from django.http import HttpRequest


def signup_policy(request: HttpRequest) -> dict[str, bool]:
    """
    Expose whether signup is allowed for the current request/site.
    Uses the configured ACCOUNT_ADAPTER so frontend behavior matches backend.
    """
    adapter = get_adapter(request)
    return {
        "allow_signups": adapter.is_open_for_signup(request),
    }


def email_settings(request: HttpRequest) -> dict[str, str | None]:
    """Expose email template settings to all templates."""
    return {
        "email_color_primary": settings.EMAIL_COLOR_PRIMARY,
        "email_color_foreground": settings.EMAIL_COLOR_FOREGROUND,
        "email_color_muted": settings.EMAIL_COLOR_MUTED,
        "email_font_family": settings.EMAIL_FONT_FAMILY,
        "email_logo_static_path": settings.EMAIL_LOGO_STATIC_PATH,
    }
