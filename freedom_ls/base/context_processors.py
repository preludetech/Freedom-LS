import os
from django.http import HttpRequest


def posthog_config(_request: HttpRequest) -> dict[str, str | None]:
    """
    Context processor that provides PostHog configuration from environment variables.

    Args:
        _request: The current HttpRequest (required by Django context processors)

    Returns:
        dict: Dictionary containing posthog_api_key if defined in environment
    """
    posthog_api_key = os.environ.get('POSTHOG_API_KEY')

    return {
        'posthog_api_key': posthog_api_key,
    }
