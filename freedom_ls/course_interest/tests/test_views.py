"""Tests for course_interest views (Task 3.1 + Task 3.2).

TDD: these tests are written before the implementation.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.accounts.tests._auth_page_helpers import _next_param
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

# ---------------------------------------------------------------------------
# express_interest view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestCreatesRow:
    """POST express_interest on a coming-soon course creates exactly one row."""

    def test_post_coming_soon_creates_interest_row(self, client, mock_site_context):
        """POST express_interest on a coming-soon course creates a CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 1

    def test_second_post_is_no_op(self, client, mock_site_context):
        """A second POST to express_interest is a no-op (still exactly one row)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 1

    def test_post_coming_soon_renders_interested_state(self, client, mock_site_context):
        """POST express_interest on a coming-soon course renders the interested state."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Interested" in content


@pytest.mark.django_db
class TestExpressInterestOnPublishedCourse:
    """POST express_interest on a published course returns 422 and creates no row."""

    def test_post_published_course_returns_422(self, client, mock_site_context):
        """POST express_interest on a published course returns HTTP 422."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 422

    def test_post_published_course_creates_no_row(self, client, mock_site_context):
        """POST express_interest on a published course does not create a CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 0


@pytest.mark.django_db
class TestExpressInterestOnHiddenCourse:
    """POST express_interest on a hidden course 404s for unregistered users.

    A hidden course must never confirm its existence, so it returns
    404, not the distinguishable 422 a published course returns.
    """

    def test_post_hidden_unregistered_returns_404(self, client, mock_site_context):
        """POST express_interest on a hidden course by an unregistered user returns 404."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 404
        assert CourseInterest.objects.filter(user=user, course=course).count() == 0

    def test_post_hidden_registered_returns_422(self, client, mock_site_context):
        """A registered learner on a hidden (non-coming-soon) course gets the 422 no-op."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# remove_interest view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRemoveInterest:
    """POST remove_interest deletes the row if present, no-op if absent."""

    def test_remove_interest_deletes_row(self, client, mock_site_context):
        """POST remove_interest deletes the CourseInterest row."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        client.post(url, HTTP_HX_REQUEST="true")

        assert CourseInterest.objects.filter(user=user, course=course).count() == 0

    def test_remove_interest_no_op_when_absent(self, client, mock_site_context):
        """POST remove_interest when no row exists is a no-op (no error)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 200

    def test_remove_interest_renders_not_interested_state(
        self, client, mock_site_context
    ):
        """POST remove_interest renders the not-interested state of the CTA."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode()
        assert response.status_code == 200
        assert "I'm interested" in content


@pytest.mark.django_db
class TestRemoveInterestOnHiddenCourse:
    """POST remove_interest on a hidden course 404s for unregistered users.

    Mirrors express_interest: a hidden course must never confirm its existence —
    so it returns 404, not the 200 CTA partial a coming-soon course returns, which
    would be a distinguishable existence oracle.
    """

    def test_post_hidden_unregistered_returns_404(self, client, mock_site_context):
        """POST remove_interest on a hidden course by an unregistered user returns 404."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 404

    def test_post_hidden_registered_returns_200(self, client, mock_site_context):
        """A registered learner on a hidden course can still remove interest (200)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET rejected (POST-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestGetRejected:
    """GET on express_interest and remove_interest endpoints is rejected."""

    def test_get_express_interest_rejected(self, client, mock_site_context):
        """GET express_interest is rejected (method not allowed)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.get(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 405

    def test_get_remove_interest_rejected(self, client, mock_site_context):
        """GET remove_interest is rejected (method not allowed)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.get(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 405


# ---------------------------------------------------------------------------
# Anonymous user redirected through login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestAnonymousRedirect:
    """Anonymous users expressing interest go to signup; removing interest goes to login.

    Expressing interest is an acquisition call to action, so it sends an
    anonymous visitor to signup (or login, once signups are closed).
    Removing interest is not acquiring anything, so it always goes to login.
    An htmx request gets 204 + HX-Redirect, since htmx would otherwise follow
    a 302 inside its own XHR and swap the auth page into the CTA. A
    non-htmx request gets a plain 302 the browser navigates on its own.
    """

    def test_anonymous_express_interest_htmx_gets_hx_redirect_to_signup(
        self, client, mock_site_context
    ):
        """Anonymous htmx POST to express_interest gets 204 + HX-Redirect to signup."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert urlparse(response["HX-Redirect"]).path == reverse("account_signup")
        deferred_url = reverse(
            "course_interest:deferred_express_interest",
            kwargs={"course_slug": course.slug},
        )
        assert _next_param(response["HX-Redirect"]) == deferred_url

    def test_anonymous_express_interest_non_htmx_gets_plain_redirect_to_signup(
        self, client, mock_site_context
    ):
        """Anonymous non-htmx POST to express_interest gets a plain 302 to signup."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url)

        assert response.status_code == 302
        assert urlparse(response["Location"]).path == reverse("account_signup")
        deferred_url = reverse(
            "course_interest:deferred_express_interest",
            kwargs={"course_slug": course.slug},
        )
        assert _next_param(response["Location"]) == deferred_url

    def test_anonymous_express_interest_with_signups_closed_goes_to_login(
        self, client, mock_site_context
    ):
        """Signups closed on the site falls express_interest back to login."""
        SiteSignupPolicyFactory(allow_signups=False)
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url)

        assert response.status_code == 302
        assert urlparse(response["Location"]).path == reverse("account_login")
        deferred_url = reverse(
            "course_interest:deferred_express_interest",
            kwargs={"course_slug": course.slug},
        )
        assert _next_param(response["Location"]) == deferred_url

    def test_anonymous_remove_interest_htmx_gets_hx_redirect_to_login(
        self, client, mock_site_context
    ):
        """Anonymous htmx POST to remove_interest gets 204 + HX-Redirect to login."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert urlparse(response["HX-Redirect"]).path == reverse("account_login")
        detail_url = reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        assert _next_param(response["HX-Redirect"]) == detail_url

    def test_anonymous_remove_interest_non_htmx_gets_plain_redirect_to_login(
        self, client, mock_site_context
    ):
        """Anonymous non-htmx POST to remove_interest gets a plain 302 to login."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        url = reverse(
            "course_interest:remove_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url)

        assert response.status_code == 302
        assert urlparse(response["Location"]).path == reverse("account_login")
        detail_url = reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        assert _next_param(response["Location"]) == detail_url


# ---------------------------------------------------------------------------
# Task 3.2: content assertions (success criterion 7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpressInterestCTAContent:
    """The interested-state CTA must NOT promise a notification."""

    def test_interested_state_contains_no_notification_promise(
        self, client, mock_site_context
    ):
        """The interested-state response does not contain notification-promising strings."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:express_interest", kwargs={"course_slug": course.slug}
        )
        response = client.post(url, HTTP_HX_REQUEST="true")

        content = response.content.decode().lower()
        assert "email" not in content
        assert "notify" not in content
        assert "notification" not in content
        assert "we'll let you know" not in content


# ---------------------------------------------------------------------------
# deferred_express_interest view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeferredExpressInterest:
    """The deferred landing view only records interest for a click it started."""

    def test_get_without_pending_click_creates_no_row(self, client, mock_site_context):
        """A GET with nothing stashed in the session records nothing.

        Guards against a forged `<img src>` or a link prefetch of this URL
        creating interest rows for a signed-in visitor.
        """
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        url = reverse(
            "course_interest:deferred_express_interest",
            kwargs={"course_slug": course.slug},
        )
        response = client.get(url)

        assert not CourseInterest.objects.filter(user=user, course=course).exists()
        assert response.status_code == 302
        assert response["Location"] == reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )


# ---------------------------------------------------------------------------
# GA4 course_access_requested event
# ---------------------------------------------------------------------------


def _express_interest_url(course_slug: str) -> str:
    return reverse(
        "course_interest:express_interest", kwargs={"course_slug": course_slug}
    )


@pytest.mark.django_db
class TestExpressInterestAnalyticsEvent:
    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_first_click_emits_the_event_in_the_swapped_partial(
        self, client, mock_site_context
    ):
        """The partial carries the script, so the event fires at the swap
        and does not wait in the session for the next full page."""
        user = UserFactory()
        course = CourseFactory(
            slug="coming-soon-course",
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "free"},
        )
        client.force_login(user)

        response = client.post(
            _express_interest_url("coming-soon-course"), HTTP_HX_REQUEST="true"
        )

        assert (
            """gtag('event', 'course_access_requested', """
            f'{{"course_slug": "coming-soon-course", "course_id": "{course.id}", '
            '"access_type": "free", "request_kind": "interest"})'
        ) in response.content.decode()

    @override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
    def test_a_repeat_click_emits_nothing(self, client, mock_site_context):
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        response = client.post(
            _express_interest_url(course.slug), HTTP_HX_REQUEST="true"
        )

        assert "gtag('event'" not in response.content.decode()

    def test_a_published_course_records_no_event(self, client, mock_site_context):
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        client.force_login(user)

        client.post(_express_interest_url(course.slug))

        assert "google_analytics_events" not in client.session

    def test_removing_interest_records_no_event(self, client, mock_site_context):
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course)
        client.force_login(user)

        client.post(
            reverse(
                "course_interest:remove_interest", kwargs={"course_slug": course.slug}
            )
        )

        assert "google_analytics_events" not in client.session


@pytest.mark.django_db
class TestDeferredExpressInterestAnalyticsEvent:
    def test_the_deferred_click_records_the_event_for_the_next_page(
        self, client, mock_site_context
    ):
        """This view redirects, so the event waits in the session for the
        course page the visitor lands on."""
        user = UserFactory()
        course = CourseFactory(
            slug="deferred-course",
            visibility=CourseVisibility.COMING_SOON,
            access_config={"access_type": "free"},
        )
        client.post(_express_interest_url("deferred-course"))
        client.force_login(user)

        client.get(
            reverse(
                "course_interest:deferred_express_interest",
                kwargs={"course_slug": "deferred-course"},
            )
        )

        assert client.session["google_analytics_events"] == [
            {
                "name": "course_access_requested",
                "params": {
                    "course_slug": "deferred-course",
                    "course_id": str(course.id),
                    "access_type": "free",
                    "request_kind": "interest",
                },
            }
        ]

    def test_a_get_without_a_pending_click_records_no_event(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        client.get(
            reverse(
                "course_interest:deferred_express_interest",
                kwargs={"course_slug": course.slug},
            )
        )

        assert "google_analytics_events" not in client.session


# Tests for deferred login — user intent survives authentication.
#
# Covers:
# - Deferred-login flows via `acquisition_login_required`: anonymous access to
#   `initiate_course_access` / `apply` redirects to signup (or login, once
#   signups are closed) with `?next=` set, and after login the free/gated
#   course flows land the learner correctly.
# - The signup arm of the same funnel: intent survives account creation and
#   email verification, not only sign-in.


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


# ---------------------------------------------------------------------------
# Deferred-login flow: express interest sends anonymous visitors to signup
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
