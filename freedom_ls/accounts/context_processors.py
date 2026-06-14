from allauth.account.adapter import get_adapter

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
