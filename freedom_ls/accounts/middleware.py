"""Middleware that redirects authenticated users with incomplete registration
forms to the completion view.

Match strategy for the exempt list is **explicit** — either the request path
starts with one of `EXEMPT_PATH_PREFIXES`, or the resolved view name (from
`resolve(request.path).view_name`, which includes any `app_name:` namespace)
is in `EXEMPT_URL_NAMES`. No substring or `in` matching.

Completion status is cached in `request.session[CACHE_SESSION_KEY]` and keyed
on a hash of the configured `additional_registration_forms` list — a site
config change automatically invalidates the cache. The completion view also
clears the cache on successful submit. Admin edits to learner data do NOT
invalidate the cache mid-session: the next login will re-evaluate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import cast

from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

EXEMPT_URL_NAMES: frozenset[str] = frozenset(
    {
        "account_login",
        "account_logout",
        "account_signup",
        "account_email_verification_sent",
        "account_confirm_email",
        "account_email",
        "account_reset_password",
        "account_reset_password_done",
        "account_reset_password_from_key",
        "account_reset_password_from_key_done",
        "accounts:legal_doc",
        "accounts:complete_registration",
    }
)

EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/media/",
    "/health/",
)

CACHE_SESSION_KEY = "_registration_completion_state"


def _hash_dotted_paths(dotted_paths: list[str]) -> str:
    serialised = json.dumps(sorted(dotted_paths))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


class RegistrationCompletionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._should_check(request):
            return self.get_response(request)

        if self._is_exempt(request):
            return self.get_response(request)

        # `_should_check` already verified `user.is_authenticated`, so this is a
        # concrete `User` not `AnonymousUser`.
        user = cast(AbstractBaseUser, request.user)
        if getattr(user, "is_superuser", False):
            return self.get_response(request)

        # Local imports to avoid app-loading order issues.
        from .registration_forms import get_incomplete_forms
        from .utils import get_signup_policy_for_request

        policy = get_signup_policy_for_request(request)
        dotted_paths = (
            list(policy.additional_registration_forms) if policy is not None else []
        )
        dotted_paths_hash = _hash_dotted_paths(dotted_paths)

        if self._is_complete_cached(request, dotted_paths_hash):
            return self.get_response(request)

        incomplete = get_incomplete_forms(user, dotted_paths)

        if not incomplete:
            self._mark_complete(request, dotted_paths_hash)
            return self.get_response(request)

        return redirect(reverse("accounts:complete_registration"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_check(self, request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        return bool(user is not None and user.is_authenticated)

    def _is_exempt(self, request: HttpRequest) -> bool:
        path = request.path or ""
        for prefix in EXEMPT_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        try:
            match = resolve(path)
        except Resolver404:
            return False
        view_name = match.view_name or ""
        return view_name in EXEMPT_URL_NAMES

    def _is_complete_cached(self, request: HttpRequest, expected_hash: str) -> bool:
        session = getattr(request, "session", None)
        if session is None:
            return False
        entry = session.get(CACHE_SESSION_KEY)
        if not isinstance(entry, dict):
            return False
        return entry.get("hash") == expected_hash

    def _mark_complete(self, request: HttpRequest, dotted_paths_hash: str) -> None:
        session = getattr(request, "session", None)
        if session is None:
            return
        session[CACHE_SESSION_KEY] = {"hash": dotted_paths_hash}
