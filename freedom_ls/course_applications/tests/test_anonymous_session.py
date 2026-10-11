"""Tests for the anonymous applicant session map."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore

from freedom_ls.course_applications.anonymous_session import (
    forget_anonymous_applicant,
    owned_applications,
    remember_anonymous_applicant,
)
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)

pytestmark = pytest.mark.django_db


def _request(rf, user=None):
    request = rf.get("/")
    request.user = user if user is not None else AnonymousUser()
    request.session = SessionStore()
    return request


def test_signed_in_user_owns_their_applications(mock_site_context, rf):
    user = UserFactory()
    mine = CourseApplicationFactory(user=user)
    CourseApplicationFactory()

    assert list(owned_applications(_request(rf, user))) == [mine]


def test_session_owns_the_application_of_the_applicant_it_holds(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    request = _request(rf)
    remember_anonymous_applicant(request, application.anonymous_applicant)

    assert list(owned_applications(request)) == [application]


def test_session_that_holds_no_applicant_owns_nothing(mock_site_context, rf):
    CourseApplicationFactory(anonymous=True)

    assert list(owned_applications(_request(rf))) == []


def test_claimed_applicant_is_no_longer_owned_by_the_session(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    request = _request(rf)
    remember_anonymous_applicant(request, application.anonymous_applicant)
    application.user = UserFactory()
    application.save()

    assert list(owned_applications(request)) == []


def test_forgetting_an_applicant_removes_only_that_applicant(mock_site_context, rf):
    kept = AnonymousApplicantFactory()
    dropped = AnonymousApplicantFactory()
    request = _request(rf)
    remember_anonymous_applicant(request, kept)
    remember_anonymous_applicant(request, dropped)

    forget_anonymous_applicant(request, dropped)

    assert request.session["course_applications_anonymous_applicants"] == {
        str(kept.course_id): str(kept.pk)
    }
