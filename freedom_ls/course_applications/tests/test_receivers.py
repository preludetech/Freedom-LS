"""Tests for what signing in does to the session's anonymous applications."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import (
    EmailAddressFactory,
    SiteFactory,
    UserFactory,
)
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.anonymous_session import (
    ANONYMOUS_APPLICANTS_SESSION_KEY,
)
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.models import FormProgress, QuestionAnswerFile
from freedom_ls.form_engine.session_access import ANONYMOUS_FORM_PROGRESS_SESSION_KEY

from .helpers import gated_course_with_form, unverified_application_with_file

pytestmark = pytest.mark.django_db


def _start_anonymous_draft(client, email: str) -> CourseApplication:
    course, _form = gated_course_with_form()
    client.post(
        reverse(
            "course_applications:applicant_details",
            kwargs={"course_slug": course.slug},
        ),
        {"email": email, "first_name": "Ada", "last_name": "Lovelace"},
    )
    application: CourseApplication = CourseApplication.objects.get(course=course)
    return application


def _page_one(application: CourseApplication) -> str:
    return reverse(
        "course_applications:form_page",
        kwargs={"pk": application.pk, "page_number": 1},
    )


def test_signing_in_to_the_verified_address_adopts_the_draft(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    application.refresh_from_db()
    sitting = FormProgress.objects.get(course_application=application)
    assert (application.user, sitting.user) == (user, user)


def test_an_adopted_draft_stays_reachable_after_signing_in(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    assert client.get(_page_one(application)).status_code == 200


def test_an_adopted_applicant_is_marked_claimed(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    applicant = AnonymousApplicant.objects.get(course_application=application)
    assert (applicant.user, applicant.claimed_at is not None) == (user, True)


def test_signing_in_to_a_mixed_case_verified_address_adopts_the_draft(
    client, mock_site_context
):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="Ada@Example.com")
    EmailAddressFactory(user=user, email="Ada@Example.com")

    client.force_login(user)

    application.refresh_from_db()
    assert application.user == user


def test_signing_in_to_an_unverified_address_adopts_nothing(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user, verified=False)

    client.force_login(user)

    application.refresh_from_db()
    assert application.user is None


def test_signing_in_to_another_address_adopts_nothing(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    application.refresh_from_db()
    assert application.user is None


def test_a_draft_under_another_address_is_out_of_reach_after_signing_in(
    client, mock_site_context
):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    assert client.get(_page_one(application)).status_code == 404


def test_signing_in_empties_both_session_lists(client, mock_site_context):
    _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")

    client.force_login(user)

    assert (
        client.session.get(ANONYMOUS_APPLICANTS_SESSION_KEY),
        client.session.get(ANONYMOUS_FORM_PROGRESS_SESSION_KEY),
    ) == ({}, [])


def _unclaimed_application_for(email: str, site=None):
    unverified = unverified_application_with_file()
    unverified.applicant.email = email
    if site is not None:
        unverified.applicant.site = site
    unverified.applicant.save()
    return unverified


def test_deleting_a_user_erases_their_unclaimed_applications(mock_site_context):
    user = UserFactory(email="ada@example.com")
    unverified = _unclaimed_application_for("ada@example.com")

    user.delete()

    assert not CourseApplication.objects.filter(pk=unverified.application.pk).exists()


def test_deleting_a_user_removes_their_unclaimed_applications_files(mock_site_context):
    user = UserFactory(email="ada@example.com")
    unverified = _unclaimed_application_for("ada@example.com")
    answer_file = QuestionAnswerFile.objects.get(
        answer__form_progress=unverified.sitting
    )
    storage, name = answer_file.file.storage, answer_file.file.name

    user.delete()

    assert not storage.exists(name)


def test_deleting_a_user_matches_their_address_regardless_of_case(mock_site_context):
    user = UserFactory(email="Ada@Example.com")
    unverified = _unclaimed_application_for("ada@example.com")

    user.delete()

    assert not AnonymousApplicant.objects.filter(pk=unverified.applicant.pk).exists()


def test_deleting_a_user_leaves_another_sites_applicant_with_that_address(
    mock_site_context,
):
    user = UserFactory(email="ada@example.com")
    elsewhere = _unclaimed_application_for("ada@example.com", site=SiteFactory())

    user.delete()

    assert AnonymousApplicant._base_manager.filter(pk=elsewhere.applicant.pk).exists()


def test_deleting_a_user_leaves_another_addresses_applicant(mock_site_context):
    user = UserFactory(email="ada@example.com")
    other = _unclaimed_application_for("bob@example.com")

    user.delete()

    assert AnonymousApplicant.objects.filter(pk=other.applicant.pk).exists()
