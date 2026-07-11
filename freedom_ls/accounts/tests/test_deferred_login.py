"""Tests for deferred login — user intent survives authentication.

Covers:
- Middleware preserving `next` through the registration-completion step.
- Full deferred-login flows: free course (login + signup paths) and
  application-gated course (apply target survives auth).
- New-user + additional-registration-forms `next` survival (critical path).
- Open-redirect rejection in the middleware's `next` handling.
- Enrolment intent surviving the existing-email/enumeration signup branch,
  and enumeration parity between the new-email and existing-email branches.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import (
    EmailAddressFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.accounts.tests._completion_view_fixtures import STORED_PHONE_NUMBERS
from freedom_ls.student_management.models import UserCourseRegistration

ALWAYS_INCOMPLETE_PATH = (
    "freedom_ls.accounts.tests._completion_view_fixtures.AlwaysIncompleteForm"
)
PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"

# Legal-doc consent is required in the test settings module, so every direct
# signup POST must carry these regardless of what the test is actually about.
SIGNUP_BASE_FIELDS = {
    "password1": "Sup3rSecretPass!!",  # pragma: allowlist secret
    "password2": "Sup3rSecretPass!!",  # pragma: allowlist secret
    "first_name": "Learner",
    "accept_terms": "on",
    "accept_privacy": "on",
}

# Two sources of per-render noise that are not enumeration signals — both
# vary on *every* request regardless of whether the email is new or existing,
# so both must be normalised out of a byte-for-byte parity comparison:
# - Django masks the CSRF token differently on every render (BREACH
#   mitigation), even within one unchanged session; this page embeds it in
#   the HTMX header attribute.
# - The toast component mints a fresh random element id per message render.
_CSRF_HX_HEADER_RE = re.compile(rb'"X-CSRFToken":\s*"[^"]*"')
_TOAST_ID_RE = re.compile(rb"toast-[0-9a-f]{32}")


def _normalized_response_content(content: bytes, email: str) -> bytes:
    """Response body with per-render noise blanked out, for parity comparison.

    Both the new-account and existing-account branches echo the submitted
    email back in the "Confirmation email sent to <email>" message — that's
    not an enumeration signal (the requester always sees their own input),
    but comparing two different literal email strings would otherwise make an
    identical-response assertion fail for a reason that has nothing to do
    with enumeration. Assumes the address appears only verbatim in the body
    (this screen does not URL-encode it); revisit if that ever changes.
    """
    without_csrf = _CSRF_HX_HEADER_RE.sub(b'"X-CSRFToken": "<CSRF>"', content)
    without_toast_id = _TOAST_ID_RE.sub(b"toast-<ID>", without_csrf)
    return without_toast_id.replace(email.encode(), b"<EMAIL>")


def _next_param(location: str) -> str | None:
    """Return the single `next` query-param value from a redirect Location, if any."""
    values = parse_qs(urlparse(location).query).get("next")
    return values[0] if values else None


# ---------------------------------------------------------------------------
# Middleware: next preservation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_middleware_preserves_next_from_get_param(
    mock_site_context, site, settings, logged_in_client
):
    """Middleware appends the in-flight `next` to the completion redirect URL.

    When the user reaches a protected page that carries `?next=…` (e.g.
    allauth forwarded it after signup), the middleware must forward that
    same `next` into the `complete_registration` redirect so the chain
    survives to the end.
    """
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = logged_in_client(user)

    target_path = "/courses/free-test-course/access/"
    # The completion view is exempt — hit a non-exempt URL that carries ?next
    # to trigger the middleware.
    profile_url = reverse("accounts:account_profile") + f"?next={target_path}"
    response = client.get(profile_url, follow=False)

    assert response.status_code == 302
    expected = reverse("accounts:complete_registration") + f"?next={target_path}"
    assert response["Location"] == expected


@pytest.mark.django_db
def test_middleware_falls_back_to_request_path_when_no_next_param(
    mock_site_context, site, settings, logged_in_client
):
    """When no ?next= is in the query string, `request.path` is used as fallback."""
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = logged_in_client(user)

    profile_url = reverse("accounts:account_profile")
    response = client.get(profile_url, follow=False)

    assert response.status_code == 302
    expected = reverse("accounts:complete_registration") + f"?next={profile_url}"
    assert response["Location"] == expected


@pytest.mark.django_db
def test_middleware_rejects_off_host_next_and_falls_back_to_path(
    mock_site_context, site, settings, logged_in_client
):
    """An off-host `next` value must NOT be forwarded by the middleware.

    When `url_has_allowed_host_and_scheme` rejects the supplied `?next=`, the
    middleware discards it and falls back to the (always same-host)
    `request.path`, so no unvalidated redirect leaks and the user still keeps a
    sensible destination.
    """
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = logged_in_client(user)

    profile_path = reverse("accounts:account_profile")
    response = client.get(
        profile_path + "?next=https://evil.example.com/phish", follow=False
    )

    assert response.status_code == 302
    # The off-host value is rejected; the same-host request path is preserved.
    assert "evil.example.com" not in response["Location"]
    expected = reverse("accounts:complete_registration") + f"?next={profile_path}"
    assert response["Location"] == expected


# ---------------------------------------------------------------------------
# Full chain: new-user + additional-registration-forms next survival
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_survives_complete_registration_step(
    mock_site_context, site, settings, logged_in_client
):
    """Intent destination survives the forced registration-completion step.

    Simulates the critical path:
      1. User is authenticated but has incomplete registration forms.
      2. They request a protected page (simulated via the middleware redirect).
      3. The middleware forwards `next` into `complete_registration?next=…`.
      4. They submit the form.
      5. The view redirects them to the original destination.
    """
    STORED_PHONE_NUMBERS.clear()

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = logged_in_client(user)

    target_path = "/courses/free-test-course/access/"

    # Submit the completion form with the next parameter (as if the middleware
    # forwarded the user there with ?next=...).
    response = client.post(
        reverse("accounts:complete_registration") + f"?next={target_path}",
        {
            "PhoneNumberForm-phone_number": "+27 11 555 0001",
            "next": target_path,
        },
        follow=False,
    )

    assert response.status_code == 302
    assert response["Location"] == target_path


@pytest.mark.django_db
def test_unsafe_next_in_complete_registration_falls_back_to_login_redirect(
    mock_site_context, site, settings, logged_in_client
):
    """Open-redirect rejection in the completion view's post-submit redirect.

    An off-host `next` supplied to `complete_registration` must be ignored;
    the redirect must fall back to `LOGIN_REDIRECT_URL`.
    """
    STORED_PHONE_NUMBERS.clear()
    settings.LOGIN_REDIRECT_URL = "/"

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = logged_in_client(user)

    response = client.post(
        reverse("accounts:complete_registration"),
        {
            "PhoneNumberForm-phone_number": "+27 11 555 0002",
            "next": "https://evil.example.com/steal",
        },
        follow=False,
    )

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert "evil.example.com" not in response["Location"]


# ---------------------------------------------------------------------------
# Deferred-login flows: free course via @login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_initiate_redirects_to_login_with_next(
    mock_site_context, course_with_topic
):
    """Anonymous GET of initiate_course_access → 302 to login with ?next= set."""
    course = course_with_topic(access_type="free")

    client = Client()
    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    assert response.status_code == 302
    login_url = reverse("account_login")
    assert response["Location"].startswith(login_url)
    assert _next_param(response["Location"]) == access_url


@pytest.mark.django_db
def test_deferred_login_free_course_enrolls_and_redirects(
    mock_site_context, logged_in_client, course_with_topic
):
    """After login, the ?next= chain lands the learner inside the course.

    Simulates the full deferred-login flow using force_login (representing
    what happens immediately after a successful login with `next` set).
    """
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    # The view registers the user and redirects to course_home which then
    # redirects into the first item — we only need to verify the first hop.
    assert response.status_code == 302
    assert UserCourseRegistration.objects.filter(user=user, collection=course).exists()


@pytest.mark.django_db
def test_anonymous_access_to_apply_redirects_to_login_with_next(
    mock_site_context, course_with_topic
):
    """Anonymous GET of apply → 302 to login?next=<apply-url>."""
    course = course_with_topic(access_type="application_gated")
    client = Client()
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.get(apply_url, follow=False)

    assert response.status_code == 302
    login_url = reverse("account_login")
    assert response["Location"].startswith(login_url)
    assert _next_param(response["Location"]) == apply_url


@pytest.mark.django_db
def test_deferred_login_gated_course_lands_on_apply_page(
    mock_site_context, logged_in_client, course_with_topic
):
    """After login, the ?next= chain lands an authenticated user on the apply page.

    The apply view's GET shows the confirmation page — it must NOT auto-POST.
    """
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.get(apply_url, follow=False)

    # The apply GET shows the confirmation page (200), not an auto-submitted POST.
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Open-redirect: complete_registration view GET next rendering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_complete_registration_get_with_safe_next_renders_hidden_field(
    mock_site_context, site, logged_in_client
):
    """A safe ?next= is re-emitted as a hidden input in the completion form."""
    STORED_PHONE_NUMBERS.clear()

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = logged_in_client(user)

    target_path = "/courses/some-course/access/"
    response = client.get(
        reverse("accounts:complete_registration") + f"?next={target_path}"
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="next"' in body
    assert f'value="{target_path}"' in body


# ---------------------------------------------------------------------------
# Enrolment intent survives the existing-email/enumeration signup branch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_email_signup_with_next_lands_on_course_after_login(
    mock_site_context, course_with_topic
):
    """A learner recovering an existing account lands back on their course.

    Signing up via the course CTA (`?next=<course access url>`) with an email
    that already has a verified account routes through the enumeration-safe
    branch, dropping no error and no distinguishable response. Once that
    learner actually authenticates in the same session, they must land on the
    course they were enrolling in, not the default LOGIN_REDIRECT_URL.
    """
    course = course_with_topic(access_type="free")
    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )

    user = UserFactory()
    EmailAddressFactory(user=user, email=user.email, verified=True, primary=True)

    client = Client()
    signup_response = client.post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": user.email, "next": access_url},
        follow=False,
    )
    assert signup_response.status_code == 302

    login_response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": user.email},
        follow=False,
    )

    assert login_response.status_code == 302
    assert login_response["Location"] == access_url


@pytest.mark.django_db
def test_off_host_next_on_signup_is_ignored_and_login_falls_back_to_default(
    mock_site_context, settings
):
    """Open redirect: an off-host `next` at signup must not survive to login.

    Both the stash (`try_save`) and the consume
    (`AccountAdapter.get_login_redirect_url`) sides re-validate with the same
    same-host guard, so an attacker-supplied off-host `next` can never come
    back out as a later authenticated redirect.
    """
    settings.LOGIN_REDIRECT_URL = "/"
    user = UserFactory()
    EmailAddressFactory(user=user, email=user.email, verified=True, primary=True)

    client = Client()
    client.post(
        reverse("account_signup"),
        {
            **SIGNUP_BASE_FIELDS,
            "email": user.email,
            "next": "https://evil.example.com/phish",
        },
        follow=False,
    )

    login_response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": user.email},
        follow=False,
    )

    assert login_response.status_code == 302
    assert login_response["Location"] == "/"
    assert "evil.example.com" not in login_response["Location"]


@pytest.mark.django_db
def test_stale_signup_stash_does_not_leak_into_unrelated_later_login(
    mock_site_context, course_with_topic, settings
):
    """An abandoned CTA stash must not redirect an unrelated later login.

    Signing up (existing-email branch) with `?next=<course>` stashes that
    destination. If that signup is abandoned and a *different*, next-less
    signup happens later in the same session, the later signup must clear —
    not inherit — the earlier stash, so a subsequent login for that unrelated
    account lands on the default LOGIN_REDIRECT_URL, not the stale course.
    """
    settings.LOGIN_REDIRECT_URL = "/"
    course = course_with_topic(access_type="free")
    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )

    stashing_user = UserFactory()
    EmailAddressFactory(user=stashing_user, email=stashing_user.email, verified=True)

    unrelated_user = UserFactory()
    EmailAddressFactory(user=unrelated_user, email=unrelated_user.email, verified=True)

    client = Client()
    # Abandoned CTA signup: stashes `access_url`, but the caller never returns.
    client.post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": stashing_user.email, "next": access_url},
        follow=False,
    )

    # A later, next-less signup for a DIFFERENT existing account, same session.
    client.post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": unrelated_user.email},
        follow=False,
    )

    login_response = client.post(
        reverse("account_login"),
        {"login": unrelated_user.email, "password": unrelated_user.email},
        follow=False,
    )

    assert login_response.status_code == 302
    assert login_response["Location"] == "/"


# ---------------------------------------------------------------------------
# Enumeration parity — new-vs-existing email, direct and via the CTA
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("existing_verified", [True, False])
def test_direct_signup_response_identical_for_new_vs_existing_email(
    mock_site_context, existing_verified
):
    """Direct signup page, no `next`: new vs existing email look identical.

    The requester-visible response for signing up with a brand-new email and
    with an email that already has an account (verified or not) must be
    indistinguishable: same status code, same redirect chain, same rendered
    content. This is the baseline branch that had no coverage before this fix
    — the exact gap that let the enrolment-intent bug ship.
    """
    existing_user = UserFactory()
    EmailAddressFactory(
        user=existing_user, email=existing_user.email, verified=existing_verified
    )
    new_email = "brand-new-learner@example.com"

    # A fresh client per request: each gets its own session and its own
    # freshly-masked CSRF token, both normalised out below — so the only
    # thing the comparison can react to is a real branch-dependent difference.
    new_response = Client().post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": new_email},
        follow=True,
    )
    existing_response = Client().post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": existing_user.email},
        follow=True,
    )

    assert new_response.status_code == existing_response.status_code
    assert new_response.redirect_chain == existing_response.redirect_chain
    assert _normalized_response_content(
        new_response.content, new_email
    ) == _normalized_response_content(existing_response.content, existing_user.email)


@pytest.mark.django_db
@pytest.mark.parametrize("existing_verified", [True, False])
def test_cta_signup_response_identical_for_new_vs_existing_email(
    mock_site_context, course_with_topic, existing_verified
):
    """Via the CTA, both carrying the same `?next=`: responses look identical.

    Same identical-response requirement as the direct-signup case, but with
    an in-flight enrolment `next` present — the stash mechanism that carries
    it forward must not itself become an observable difference.
    """
    course = course_with_topic(access_type="free")
    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )

    existing_user = UserFactory()
    EmailAddressFactory(
        user=existing_user, email=existing_user.email, verified=existing_verified
    )
    new_email = "brand-new-cta-learner@example.com"

    new_response = Client().post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": new_email, "next": access_url},
        follow=True,
    )
    existing_response = Client().post(
        reverse("account_signup"),
        {**SIGNUP_BASE_FIELDS, "email": existing_user.email, "next": access_url},
        follow=True,
    )

    assert new_response.status_code == existing_response.status_code
    assert new_response.redirect_chain == existing_response.redirect_chain
    assert _normalized_response_content(
        new_response.content, new_email
    ) == _normalized_response_content(existing_response.content, existing_user.email)
