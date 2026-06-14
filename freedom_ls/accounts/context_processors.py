from allauth.account.adapter import get_adapter

from django.http import HttpRequest

from .email_utils import get_email_theme


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
    # @claude this seems heavy handed:
    # 1. Why do we need to rename every theme token to "email_$theme_token"? Why the misdirection? Why not just call it what it is?
    # 2. injecting this context into literally every view seems inefficient. Why do this? What are the alternatives
    """Expose the resolved email theme values to all templates.

    Registered globally in TEMPLATES because Django's email rendering uses the
    same template engine and context processors as regular views. There is no
    email-only context processor hook, so global registration is the simplest
    way to ensure these values are available when allauth renders email templates.
    The values are derived once and cached by ``get_email_theme`` so the
    per-request overhead is negligible.
    """
    theme = get_email_theme()
    return {
        "email_color_primary": theme.color_primary,
        "email_color_foreground": theme.color_foreground,
        "email_color_muted": theme.color_muted,
        "email_color_surface": theme.color_surface,
        "email_color_surface_2": theme.color_surface_2,
        "email_color_on_primary": theme.color_on_primary,
        "email_color_border": theme.color_border,
        "email_color_header": theme.color_header,
        "email_color_on_header": theme.color_on_header,
        "email_font_family": theme.font_family,
        "email_button_radius": theme.button_radius,
    }
