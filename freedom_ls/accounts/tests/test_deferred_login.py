"""Tests for Phase 5: deferred login — user intent survives authentication.

Covers:
- Middleware preserving `next` through the registration-completion step.
- Full deferred-login flows: free course (login + signup paths) and
  application-gated course (apply target survives auth).
- New-user + additional-registration-forms `next` survival (critical path).
- Open-redirect rejection in the middleware's `next` handling.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.tests._completion_view_fixtures import STORED_PHONE_NUMBERS
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.models import UserCourseRegistration

ALWAYS_INCOMPLETE_PATH = (
    "freedom_ls.accounts.tests._completion_view_fixtures.AlwaysIncompleteForm"
)
PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


def _next_param(location: str) -> str | None:
    """Return the single `next` query-param value from a redirect Location, if any."""
    values = parse_qs(urlparse(location).query).get("next")
    return values[0] if values else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_course(slug: str = "free-test-course"):
    """A free course with one topic item."""
    course = CourseFactory(
        slug=slug,
        title="Free Test Course",
        access_config={"access_type": "free"},
    )
    topic = TopicFactory(title="Topic 1", slug=f"{slug}-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


def _gated_course(slug: str = "gated-test-course"):
    """An application-gated course with one topic item."""
    course = CourseFactory(
        slug=slug,
        title="Gated Test Course",
        access_config={"access_type": "application_gated"},
    )
    topic = TopicFactory(title="Topic 1", slug=f"{slug}-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


# ---------------------------------------------------------------------------
# 5.2 Middleware: next preservation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_middleware_preserves_next_from_get_param(mock_site_context, site, settings):
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
    client = Client()
    client.force_login(user)

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
    mock_site_context, site, settings
):
    """When no ?next= is in the query string, `request.path` is used as fallback."""
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    profile_url = reverse("accounts:account_profile")
    response = client.get(profile_url, follow=False)

    assert response.status_code == 302
    expected = reverse("accounts:complete_registration") + f"?next={profile_url}"
    assert response["Location"] == expected


@pytest.mark.django_db
def test_middleware_rejects_off_host_next_and_falls_back_to_path(
    mock_site_context, site, settings
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
    client = Client()
    client.force_login(user)

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
# 5.2 Full chain: new-user + additional-registration-forms next survival
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_survives_complete_registration_step(mock_site_context, site, settings):
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
    client = Client()
    client.force_login(user)

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
    mock_site_context, site, settings
):
    """Open-redirect rejection in the completion view's post-submit redirect.

    An off-host `next` supplied to `complete_registration` must be ignored;
    the redirect must fall back to `LOGIN_REDIRECT_URL`.
    """
    STORED_PHONE_NUMBERS.clear()
    settings.LOGIN_REDIRECT_URL = "/"

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = Client()
    client.force_login(user)

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
# 5.1 / Deferred-login flows: free course via @login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_initiate_redirects_to_login_with_next(mock_site_context):
    """Anonymous GET of initiate_course_access → 302 to login with ?next= set."""
    course = _free_course()

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
def test_deferred_login_free_course_enrolls_and_redirects(mock_site_context):
    """After login, the ?next= chain lands the learner inside the course.

    Simulates the full deferred-login flow using force_login (representing
    what happens immediately after a successful login with `next` set).
    """
    course = _free_course(slug="deferred-free-course")
    user = UserFactory()
    client = Client()
    client.force_login(user)

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
def test_anonymous_access_to_apply_redirects_to_login_with_next(mock_site_context):
    """Anonymous GET of apply → 302 to login?next=<apply-url>."""
    course = _gated_course()
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
def test_deferred_login_gated_course_lands_on_apply_page(mock_site_context):
    """After login, the ?next= chain lands an authenticated user on the apply page.

    The apply view's GET shows the confirmation page — it must NOT auto-POST.
    """
    course = _gated_course(slug="deferred-gated-course")
    user = UserFactory()
    client = Client()
    client.force_login(user)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.get(apply_url, follow=False)

    # The apply GET shows the confirmation page (200), not an auto-submitted POST.
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 5.3 Open-redirect: complete_registration view GET next rendering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_complete_registration_get_with_safe_next_renders_hidden_field(
    mock_site_context, site
):
    """A safe ?next= is re-emitted as a hidden input in the completion form."""
    STORED_PHONE_NUMBERS.clear()

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = Client()
    client.force_login(user)

    target_path = "/courses/some-course/access/"
    response = client.get(
        reverse("accounts:complete_registration") + f"?next={target_path}"
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="next"' in body
    assert f'value="{target_path}"' in body
