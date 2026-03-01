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
    """Expose email template settings to all templates.

    Registered globally in TEMPLATES because Django's email rendering uses the
    same template engine and context processors as regular views. There is no
    email-only context processor hook, so global registration is the simplest
    way to ensure these values are available when allauth renders email templates.
    The overhead is negligible (a few getattr calls on settings per request).
    """
    return {
        "email_color_primary": settings.EMAIL_COLOR_PRIMARY,
        "email_color_foreground": settings.EMAIL_COLOR_FOREGROUND,
        "email_color_muted": settings.EMAIL_COLOR_MUTED,
        "email_color_surface": settings.EMAIL_COLOR_SURFACE,
        "email_color_surface_2": settings.EMAIL_COLOR_SURFACE_2,
        "email_color_on_primary": settings.EMAIL_COLOR_ON_PRIMARY,
        "email_color_border": settings.EMAIL_COLOR_BORDER,
        "email_font_family": settings.EMAIL_FONT_FAMILY,
        "email_logo_static_path": settings.EMAIL_LOGO_STATIC_PATH,
    }
