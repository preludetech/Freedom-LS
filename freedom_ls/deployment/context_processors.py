from django.http import HttpRequest

from freedom_ls.deployment.config import config as deployment_config


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
