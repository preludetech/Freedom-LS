"""Tests for deferred login — user intent survives authentication.

Covers:
- Deferred-login flows via `@login_required`: anonymous access to
  `initiate_course_access` / `apply` redirects to login with `?next=` set,
  and after login the free/gated course flows land the learner correctly.
- Open-redirect rejection in the completion view's post-submit redirect.
- The completion view re-emitting a safe `?next=` as a hidden form field.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.tests._completion_view_fixtures import STORED_PHONE_NUMBERS
from freedom_ls.student_management.models import UserCourseRegistration

PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


def _next_param(location: str) -> str | None:
    """Return the single `next` query-param value from a redirect Location, if any."""
    values = parse_qs(urlparse(location).query).get("next")
    return values[0] if values else None


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
