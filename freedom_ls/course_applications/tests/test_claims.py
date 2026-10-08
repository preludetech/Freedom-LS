"""Tests for the claims module: what a browser holds, and attaching it on login."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.http import HttpRequest

from freedom_ls.accounts.factories import EmailAddressFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.site_aware_models.models import _thread_locals
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import (
    CLAIM_REPORT_SESSION_KEY,
    UNCLAIMED_APPLICATIONS_SESSION_KEY,
    ClaimReport,
    claim_unclaimed_applications,
    remember_unclaimed_application,
    unclaimed_application_for_course,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication


def _request() -> HttpRequest:
    request = HttpRequest()
    request.session = SessionStore()
    return request


@pytest.mark.django_db
class TestClaims:
    def test_remember_stores_the_pk_as_a_string(self, mock_site_context):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)

        remember_unclaimed_application(request, app)

        assert request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == [str(app.pk)]

    def test_remember_reassigns_the_list(self, mock_site_context):
        request = _request()
        remember_unclaimed_application(
            request, CourseApplicationFactory(unclaimed=True)
        )
        request.session.modified = False

        remember_unclaimed_application(
            request, CourseApplicationFactory(unclaimed=True)
        )

        assert request.session.modified is True

    def test_unclaimed_application_for_course_finds_a_remembered_row(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, app.course) == app

    def test_unclaimed_application_for_course_ignores_a_claimed_row(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory()
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, app.course) is None

    def test_unclaimed_application_for_course_ignores_another_course(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, CourseFactory()) is None


def _request_holding(*applications: CourseApplication) -> HttpRequest:
    request = _request()
    for application in applications:
        remember_unclaimed_application(request, application)
    return request


@pytest.mark.django_db
class TestClaimUnclaimedApplications:
    def test_login_with_verified_matching_email_claims_the_application(
        self, mock_site_context
    ):
        user = UserFactory()
        EmailAddressFactory(user=user, email="pat@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        report = claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert (app.user, report.claimed) == (user, [str(app.pk)])

    def test_verified_address_matches_regardless_of_case(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user, email="Pat@Example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert app.user == user

    def test_claim_drops_the_id_from_the_session(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user, email="pat@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        request = _request_holding(app)

        claim_unclaimed_applications(request, user)

        assert request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == []

    def test_login_with_unverified_email_does_not_claim(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user, email="pat@example.com", verified=False)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        report = claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert (app.user, report.mismatched) == (None, [str(app.pk)])

    def test_login_with_different_email_leaves_it_unclaimed(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert app.user is None

    def test_login_with_different_email_keeps_the_id_in_the_session(
        self, mock_site_context
    ):
        user = UserFactory()
        EmailAddressFactory(user=user)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        request = _request_holding(app)

        claim_unclaimed_applications(request, user)

        assert request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == [str(app.pk)]

    def test_claim_never_happens_by_email_match_without_session(
        self, mock_site_context
    ):
        user = UserFactory()
        EmailAddressFactory(user=user, email="pat@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        claim_unclaimed_applications(_request(), user)

        app.refresh_from_db()
        assert app.user is None

    def test_claim_with_no_ids_writes_nothing(self, mock_site_context):
        request = _request()

        report = claim_unclaimed_applications(request, UserFactory())

        assert report.is_empty()
        assert not request.session.modified

    def test_claim_of_a_draft_with_no_email_sets_the_account_email(
        self, mock_site_context
    ):
        user = UserFactory(email="me@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="")

        claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert (app.user, app.email) == (user, "me@example.com")

    def test_claim_is_idempotent(self, mock_site_context):
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        request = _request_holding(app)

        report = claim_unclaimed_applications(request, user)

        assert report.claimed == [str(app.pk)]

    def test_claim_drops_an_application_owned_by_someone_else(self, mock_site_context):
        app = CourseApplicationFactory()
        request = _request_holding(app)

        report = claim_unclaimed_applications(request, UserFactory())

        assert report.is_empty()
        assert request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == []

    def test_claim_drops_an_id_with_no_row(self, mock_site_context):
        app = CourseApplicationFactory(unclaimed=True)
        request = _request_holding(app)
        app.delete()

        report = claim_unclaimed_applications(request, UserFactory())

        assert report.is_empty()

    def test_claim_collision_keeps_existing_application(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        existing = CourseApplicationFactory(user=user, course=course)
        held = CourseApplicationFactory(unclaimed=True, course=course, email=user.email)

        report = claim_unclaimed_applications(_request_holding(held), user)

        held.refresh_from_db()
        assert (held.user, report.collided) == (None, [str(existing.pk)])

    def test_claim_integrity_error_is_a_collision(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        EmailAddressFactory(user=user)
        winner = CourseApplicationFactory(user=user, course=course)
        held = CourseApplicationFactory(unclaimed=True, course=course, email=user.email)

        # The collision check misses the winner, as it does when the winner
        # commits between the check and the write; the unique constraint then
        # refuses the attach.
        with patch(
            "freedom_ls.course_applications.claims._existing_application",
            side_effect=[None, winner],
        ):
            report = claim_unclaimed_applications(_request_holding(held), user)

        held.refresh_from_db()
        assert (held.user, report.collided) == (None, [str(winner.pk)])

    def test_claim_skips_course_hidden_since_draft_began(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        app = CourseApplicationFactory(unclaimed=True, course=course, email=user.email)
        EmailAddressFactory(user=user)

        report = claim_unclaimed_applications(_request_holding(app), user)

        app.refresh_from_db()
        assert (app.user, report.is_empty()) == (None, True)

    def test_claim_report_merges_receiver_and_landing_results(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user, email="a@example.com")
        first = CourseApplicationFactory(unclaimed=True, email="a@example.com")
        second = CourseApplicationFactory(unclaimed=True, email="a@example.com")
        request = _request_holding(first)
        claim_unclaimed_applications(request, user)
        remember_unclaimed_application(request, second)

        claim_unclaimed_applications(request, user)

        stored = ClaimReport.from_session(request.session[CLAIM_REPORT_SESSION_KEY])
        assert stored.claimed == [str(first.pk), str(second.pk)]

    def test_a_later_claim_with_the_address_verified_claims_it(self, mock_site_context):
        user = UserFactory()
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        request = _request_holding(app)
        claim_unclaimed_applications(request, user)
        EmailAddressFactory(user=user, email="pat@example.com", verified=True)

        report = claim_unclaimed_applications(request, user)

        app.refresh_from_db()
        assert (app.user, report.claimed) == (user, [str(app.pk)])

    def test_a_later_claim_supersedes_the_earlier_mismatch_in_the_report(
        self, mock_site_context
    ):
        user = UserFactory()
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        request = _request_holding(app)
        claim_unclaimed_applications(request, user)
        EmailAddressFactory(user=user, email="pat@example.com", verified=True)

        claim_unclaimed_applications(request, user)

        stored = ClaimReport.from_session(request.session[CLAIM_REPORT_SESSION_KEY])
        assert stored.mismatched == []


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_claims_attach_once(mock_site_context):
    user = UserFactory()
    EmailAddressFactory(user=user, email="pat@example.com")
    app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
    request_double = _thread_locals.request
    reports: list[ClaimReport] = []
    barrier = threading.Barrier(2)

    def run() -> None:
        _thread_locals.request = request_double
        request = _request_holding(app)
        barrier.wait()
        reports.append(claim_unclaimed_applications(request, user))
        connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(len(r.claimed) for r in reports) == [1, 1]
    assert CourseApplication.objects.filter(user=user).count() == 1
