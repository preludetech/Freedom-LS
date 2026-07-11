"""Investigation + regression test: site-scoped password-reset dead-end.

`UserTokenForm._get_user()` (allauth) resolves a keyed reset link's user via
`User.objects.get(pk=...)`, which goes through this project's site-scoped
`UserManager`. If the request's resolved Site differs from the user's `site`
FK, that lookup raises `DoesNotExist` and the reset dead-ends as
`invalid_password_reset` -- even though the link itself is genuinely valid.
Confirmed reachable (see `test_reset_key_resolves_but_session_does_not_survive_a_site_mismatch`
below); fixed narrowly with `SiteUnscopedUserTokenForm` (`forms.py`), registered
as the `user_token` `ACCOUNT_FORMS` key (`config/settings_base.py`).

The test settings module (`config/settings_dev.py`) pins `FORCE_SITE_NAME =
"DemoDev"`, which forces every request to the same Site and therefore masks
this defect. `conftest.py`'s autouse `_disable_force_site_name` fixture
already resets `FORCE_SITE_NAME` to `None` for every test; this test also
sets it explicitly so it is self-contained and clearly drives real,
host-based Site resolution (`django.contrib.sites`, keyed off
`request.get_host()`) rather than the forced single-site shortcut.

**Documented residual limit:** the fix makes the reset *key*
itself resolve correctly regardless of Site (steps 1-3), but it does not --
and was deliberately not widened to -- restore a persisted logged-in session
across a genuine Site mismatch (step 4). `django.contrib.auth` re-resolves
`request.user` on every request via `User._default_manager.get(pk=...)`,
which is the *same* site-scoped `UserManager` (`User` declares no manager
besides `objects = UserManager()`, so `_default_manager` is not the unscoped
`_base_manager`). So a reset completed across a Site mismatch logs the user
in for that one request/response, then the very next request silently drops
back to `AnonymousUser` -- a quieter version of the same underlying dead end.
Widening the fix to cover that per-request re-resolution was explicitly
ruled out (user decision 2026-07-11) as too tenant-isolation-sensitive for
this bugfix; a genuinely mismatched-Site reset link is therefore not fully
recoverable within this bugfix. Ensuring reset links always resolve to the
user's home Site, or a project-wide per-request re-resolution change, is left
as separate future work.
"""

from __future__ import annotations

import re

import pytest

from django.core import mail
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import EmailAddressFactory, SiteFactory, UserFactory
from freedom_ls.accounts.forms import SiteUnscopedUserTokenForm
from freedom_ls.accounts.models import User
from freedom_ls.site_aware_models.models import _thread_locals

NEW_PASSWORD = "a-brand-new-p4ssw0rd!"  # noqa: S105  # pragma: allowlist secret


def _extract_reset_url(body: str) -> str:
    """Pull the keyed reset URL out of the rendered password-reset email body."""
    match = re.search(r"Reset Password: (\S+)", body)
    assert match, f"no reset URL found in email body:\n{body}"
    return match.group(1)


@pytest.mark.django_db
def test_reset_key_resolves_but_session_does_not_survive_a_site_mismatch(
    settings,
) -> None:
    """Reproduction of the site-mismatch reset flow (steps 1-4 below).

    Steps 1-3: a keyed reset link must resolve its user regardless of the
    current request's resolved Site (confirmed fixed by
    `SiteUnscopedUserTokenForm`).

    Step 4: a follow-up request to a `@login_required` page, still resolving
    to the mismatched Site, would need to find the session still
    authenticated for the reset to fully recover the user's access. It does
    not -- see the module docstring for why this is a documented, deliberate
    residual limit rather than a bug in this fix.
    """
    settings.FORCE_SITE_NAME = None

    # Step 1: two Sites; the user's `site` FK is A.
    site_a = SiteFactory(
        name="ResetMismatchSiteA", domain="reset-mismatch-a.example.com"
    )
    site_b = SiteFactory(
        name="ResetMismatchSiteB", domain="reset-mismatch-b.example.com"
    )
    settings.ALLOWED_HOSTS = [site_a.domain, site_b.domain]

    user = UserFactory(site=site_a, email="mismatched-site-user@example.com")
    # Verified, so `filter_users_by_email` resolves the user via the
    # (unscoped) EmailAddress table rather than falling back to the
    # site-scoped `User.objects` table lookup -- isolating this test to the
    # reset-*key* resolution seam, not the reset-request step.
    EmailAddressFactory(user=user, email=user.email, verified=True, primary=True)

    client = Client()

    # Step 2: request a reset while resolved to the user's home Site (A).
    response = client.post(
        reverse("account_reset_password"),
        {"email": user.email},
        HTTP_HOST=site_a.domain,
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    reset_url = _extract_reset_url(mail.outbox[0].body)

    # Step 3: submit the keyed link, but resolve the request to Site B.
    # A valid link must not dead-end as invalid_password_reset purely
    # because the request resolves to a different Site than the user's own.
    get_response = client.get(reset_url, HTTP_HOST=site_b.domain, follow=False)
    assert get_response.status_code == 302, (
        "expected the key-in-session redirect (valid token); got "
        f"{get_response.status_code} -- the reset key dead-ended as "
        "invalid_password_reset purely due to the Site mismatch"
    )
    key_free_url = get_response["Location"]

    get_response = client.get(key_free_url, HTTP_HOST=site_b.domain, follow=False)
    assert get_response.status_code == 200

    post_response = client.post(
        key_free_url,
        {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        HTTP_HOST=site_b.domain,
        follow=False,
    )
    assert post_response.status_code == 302

    # Step 4: a follow-up request, still resolving to Site B, re-resolves
    # request.user via the site-scoped UserManager and finds no match --
    # the session is anonymous again, not a persisted logged-in state.
    # This is the documented residual limit (see module docstring).
    profile_response = client.get(
        reverse("accounts:account_profile"), HTTP_HOST=site_b.domain, follow=False
    )
    assert profile_response.status_code == 302
    assert profile_response["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
def test_site_unscoped_user_token_form_resolves_user_across_sites(settings) -> None:
    """`SiteUnscopedUserTokenForm._get_user` bypasses the Site filter directly."""
    from allauth.account.utils import user_pk_to_url_str

    site_a = SiteFactory(name="TokenFormSiteA", domain="token-form-a.example.com")
    site_b = SiteFactory(name="TokenFormSiteB", domain="token-form-b.example.com")
    settings.ALLOWED_HOSTS = [site_a.domain, site_b.domain]
    user = UserFactory(site=site_a, email="token-form-user@example.com")

    request = RequestFactory().get("/", HTTP_HOST=site_b.domain)
    _thread_locals.request = request
    try:
        resolved = SiteUnscopedUserTokenForm()._get_user(user_pk_to_url_str(user))
    finally:
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    assert resolved == user


@pytest.mark.django_db
def test_site_unscoped_user_token_form_does_not_widen_user_objects_scope(
    settings,
) -> None:
    """The bypass is scoped to `_get_user` only; `User.objects` stays site-scoped.

    Guards against the fix accidentally leaking into `User.objects` /
    `_default_manager`, which must keep filtering by Site everywhere else --
    the bypass must not broadly unscope `User.objects`.
    """
    site_a = SiteFactory(name="ScopeCheckSiteA", domain="scope-check-a.example.com")
    site_b = SiteFactory(name="ScopeCheckSiteB", domain="scope-check-b.example.com")
    settings.ALLOWED_HOSTS = [site_a.domain, site_b.domain]
    UserFactory(site=site_a, email="scope-check-user@example.com")

    request = RequestFactory().get("/", HTTP_HOST=site_b.domain)
    _thread_locals.request = request
    try:
        assert not User.objects.filter(email="scope-check-user@example.com").exists()
    finally:
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
