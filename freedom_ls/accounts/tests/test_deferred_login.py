"""Tests for deferred login — user intent survives authentication.

Covers:
- Deferred-login flows via `@login_required`: anonymous access to
  `initiate_course_access` / `apply` redirects to login with `?next=` set,
  and after login the free/gated course flows land the learner correctly.
- The signup arm of the same funnel: intent survives account creation and
  email verification, not only sign-in.
- Open-redirect rejection in the completion view's post-submit redirect.
- The completion view re-emitting a safe `?next=` as a hidden form field.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.accounts.tests._completion_view_fixtures import STORED_PHONE_NUMBERS
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.learner_management.models import LearnerCourseRegistration

PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


def _next_param(location: str) -> str | None:
    """Return the single `next` query-param value from a redirect Location, if any."""
    values = parse_qs(urlparse(location).query).get("next")
    return values[0] if values else None


def _signup_payload(email: str, last_name: str, next_url: str) -> dict[str, str]:
    """Return a signup form payload that passes validation, carrying `next_url`."""
    return {
        "email": email,
        "password1": "TestPass123!xyz",  # pragma: allowlist secret
        "password2": "TestPass123!xyz",  # pragma: allowlist secret
        "first_name": "Signup",
        "last_name": last_name,
        "accept_terms": "on",
        "accept_privacy": "on",
        "next": next_url,
    }


def _confirm_url_for(email: str) -> str:
    """Return the email-confirmation URL allauth would have emailed to `email`."""
    token = EmailConfirmationHMAC(EmailAddress.objects.get(email=email))
    return reverse("account_confirm_email", args=[token.key])


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
        "learner_interface:initiate_course_access",
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
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    # The view registers the user and redirects to course_home which then
    # redirects into the first item — we only need to verify the first hop.
    assert response.status_code == 302
    assert LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


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
# Deferred-login flow: express interest via @login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deferred_login_express_interest_round_trip(mock_site_context, client):
    """An anonymous express-interest click survives sign-in.

    The anonymous POST redirects to login with a next the browser can GET.
    After signing in, following that next records the interest and lands on
    the course detail page, instead of GET-ing the POST-only endpoint.
    """
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    user = UserFactory()

    express_interest_url = reverse(
        "course_interest:express_interest", kwargs={"course_slug": course.slug}
    )
    response = client.post(express_interest_url)
    next_url = _next_param(response["Location"])

    client.force_login(user)
    followed = client.get(next_url)

    assert followed.status_code != 405
    assert CourseInterest.objects.filter(user=user, course=course).exists()
    assert followed.status_code == 302
    assert followed["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_deferred_login_express_interest_repeat_visits_stay_idempotent(
    mock_site_context, client
):
    """Landing on the deferred-express-interest URL twice records one CourseInterest."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    user = UserFactory()

    express_interest_url = reverse(
        "course_interest:express_interest", kwargs={"course_slug": course.slug}
    )
    response = client.post(express_interest_url)
    deferred_url = _next_param(response["Location"])

    client.force_login(user)
    client.get(deferred_url)
    client.get(deferred_url)

    assert CourseInterest.objects.filter(user=user, course=course).count() == 1


@pytest.mark.django_db(transaction=True)
def test_signup_arm_express_interest_round_trip(mock_site_context):
    """An anonymous express-interest click survives signing *up*, not just in.

    The sign-in page offers a signup link, so the intent has to cross account
    creation and email verification as well as login. The deferred view writes
    only for the slug stashed in the session on the way out, so this also pins
    that the stash survives the session-key cycling signup and confirmation
    each perform.
    """
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    client = Client()

    express_interest_url = reverse(
        "course_interest:express_interest", kwargs={"course_slug": course.slug}
    )
    response = client.post(express_interest_url)
    next_url = _next_param(response["Location"])

    email = "signup-arm@example.com"
    client.post(
        reverse("account_signup"),
        _signup_payload(email, "Arm", next_url),
    )

    confirmed = client.post(_confirm_url_for(email), follow=True)

    assert confirmed.status_code == 200
    assert all(status != 405 for _, status in confirmed.redirect_chain)

    user = User.objects.get(email=email)
    assert CourseInterest.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db(transaction=True)
def test_signup_arm_records_interest_only_for_the_stashed_course(mock_site_context):
    """Signing up carries the clicked course through, and nothing else.

    Guards the stash against widening into "record interest for whatever slug
    the returning URL names" — a second coming-soon course stays untouched.
    """
    clicked = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    other = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    client = Client()

    response = client.post(
        reverse(
            "course_interest:express_interest", kwargs={"course_slug": clicked.slug}
        )
    )
    next_url = _next_param(response["Location"])

    email = "signup-arm-scope@example.com"
    client.post(
        reverse("account_signup"),
        _signup_payload(email, "Scope", next_url),
    )

    client.post(_confirm_url_for(email), follow=True)

    user = User.objects.get(email=email)
    assert CourseInterest.objects.filter(user=user, course=clicked).exists()
    assert not CourseInterest.objects.filter(user=user, course=other).exists()


# ---------------------------------------------------------------------------
# Deferred-login flow: apply via @login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deferred_login_apply_round_trip_creates_no_application(
    mock_site_context, client
):
    """An anonymous apply click survives sign-in without auto-submitting.

    The anonymous POST redirects to login with next set to the apply URL
    itself. Following that next after signing in lands on the GET
    confirmation page, not an auto-created application — apply's GET and
    POST share one URL, so `next` alone can't force the POST branch.
    """
    course = CourseFactory()
    user = UserFactory()

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.post(apply_url)
    next_url = _next_param(response["Location"])

    client.force_login(user)
    followed = client.get(next_url)

    assert followed.status_code == 200
    assert not CourseApplication.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db
def test_deferred_login_apply_repeat_submissions_stay_idempotent(
    mock_site_context, client
):
    """A second POST to apply after signing in does not duplicate the application."""
    course = CourseFactory()
    user = UserFactory()
    client.force_login(user)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    client.post(apply_url)
    client.post(apply_url)

    assert CourseApplication.objects.filter(user=user, course=course).count() == 1


# ---------------------------------------------------------------------------
# Deferred-login flow: initiate_course_access on a coming-soon course
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deferred_login_initiate_access_coming_soon_creates_no_registration(
    mock_site_context, client
):
    """A coming-soon course is not enrollable, deferred login or not.

    The anonymous GET redirects to login with next set to the access URL.
    Following that next after signing in lands on the course detail page
    without registering the learner, matching initiate_course_access's own
    coming-soon fallback.
    """
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    user = UserFactory()

    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(user)
    followed = client.get(next_url)

    assert followed.status_code == 302
    assert followed["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


# ---------------------------------------------------------------------------
# Deferred-login flow: application_status ownership after sign-in
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deferred_login_application_status_owner_sees_status_page(
    mock_site_context, client
):
    """After the login round trip, the application owner reaches their status page."""
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner)

    status_url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(status_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(owner)
    followed = client.get(next_url)

    assert followed.status_code == 200


@pytest.mark.django_db
def test_deferred_login_application_status_non_owner_gets_404(
    mock_site_context, client
):
    """After the login round trip, a non-owner still gets 404 on someone else's status page."""
    owner = UserFactory()
    other_user = UserFactory()
    app = CourseApplicationFactory(user=owner)

    status_url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(status_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(other_user)
    followed = client.get(next_url)

    assert followed.status_code == 404


# ---------------------------------------------------------------------------
# Hidden courses: login redirect, never a 404 (no enumeration signal)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["course_applications:apply", "learner_interface:initiate_course_access"],
)
def test_anonymous_access_to_hidden_course_redirects_to_login_not_404(
    mock_site_context, url_name
):
    """login_required runs before any visibility check, so an anonymous visitor
    to a hidden course's apply or access URL gets a login redirect rather than
    the 404 that confirms a registered learner would eventually see."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    client = Client()

    url = reverse(url_name, kwargs={"course_slug": course.slug})
    response = client.get(url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


@pytest.mark.django_db
def test_anonymous_access_to_status_for_hidden_course_application_redirects_to_login(
    mock_site_context,
):
    """The same holds for an application status page belonging to a hidden course."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner, course=course)
    client = Client()

    url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


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
