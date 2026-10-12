"""Resetting a QA applicant strips every application the address holds, claimed or not."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.utils import timezone

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress

pytestmark = pytest.mark.dev_tooling

QA_EMAIL = "qa.applicant@example.com"


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _clean(email: str) -> None:
    call_command(
        "qa_create_clean_applicant", "--email", email, "--site-name", "DemoDev"
    )


def _claimed_application(user):
    """An anonymous application the account followed the claim link for."""
    course = CourseFactory()
    applicant = AnonymousApplicantFactory(
        course=course, email=user.email, user=user, claimed_at=timezone.now()
    )
    return CourseApplicationFactory(
        anonymous=True,
        user=user,
        course=course,
        anonymous_applicant=applicant,
        form_progress=FormProgressFactory(user=user),
    )


@pytest.mark.django_db
def test_a_reset_removes_a_claimed_applicant_row(qa_site):
    user = UserFactory(email=QA_EMAIL)
    application = _claimed_application(user)

    _clean(QA_EMAIL)

    assert not AnonymousApplicant.objects.filter(
        pk=application.anonymous_applicant.pk
    ).exists()


@pytest.mark.django_db
def test_a_reset_removes_a_claimed_applications_sitting(qa_site):
    user = UserFactory(email=QA_EMAIL)
    application = _claimed_application(user)

    _clean(QA_EMAIL)

    assert not FormProgress.objects.filter(pk=application.form_progress.pk).exists()


@pytest.mark.django_db
def test_a_reset_removes_an_unclaimed_application_for_the_address(qa_site):
    UserFactory(email=QA_EMAIL)
    course = CourseFactory()
    application = CourseApplicationFactory(
        anonymous=True,
        course=course,
        anonymous_applicant=AnonymousApplicantFactory(course=course, email=QA_EMAIL),
        form_progress=FormProgressFactory(user=None),
    )

    _clean(QA_EMAIL)

    assert not CourseApplication.objects.filter(pk=application.pk).exists()


@pytest.mark.django_db
def test_a_second_reset_finds_nothing_left_to_remove(qa_site):
    user = UserFactory(email=QA_EMAIL)
    _claimed_application(user)
    _clean(QA_EMAIL)

    _clean(QA_EMAIL)

    assert CourseApplication.objects.filter(user=user).count() == 0
