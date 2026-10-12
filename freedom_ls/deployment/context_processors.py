from django.http import HttpRequest

from freedom_ls.deployment.config import config as deployment_config

# Namespaced view names. Each carries a one-time token in the path, so caching
# or replaying the page must never be assumed safe the way an ordinary page's
# is. The first two are allauth's own (allauth/account/urls.py), which have no
# namespace; the claim link is a login token for the application it names.
TOKEN_BEARING_URL_NAMES = frozenset(
    {
        "account_confirm_email",
        "account_reset_password_from_key",
        "course_applications:claim",
    }
)


def analytics_enabled(request: HttpRequest) -> dict[str, bool]:
    """The one place that decides whether any analytics snippet loads.

    A downstream deployment that needs consent gating adds its own context
    processor here in place of this one, returning `analytics_enabled` from
    whatever consent state it tracks.
    """
    match = request.resolver_match
    view_name = match.view_name if match is not None else None
    return {"analytics_enabled": view_name not in TOKEN_BEARING_URL_NAMES}


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
