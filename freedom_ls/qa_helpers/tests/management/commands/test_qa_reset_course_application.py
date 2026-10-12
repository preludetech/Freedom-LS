"""Resetting a QA applicant also clears the unverified applications for that address."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

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


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _reset(email: str, slug: str) -> None:
    call_command(
        "qa_reset_course_application",
        "--learner",
        email,
        "--course-slug",
        slug,
        "--site-name",
        "DemoDev",
    )


@pytest.mark.django_db
def test_a_reset_removes_the_anonymous_application_for_that_address_and_course(
    qa_site,
):
    UserFactory(email="qa.applicant@example.com")
    course = CourseFactory()
    application = CourseApplicationFactory(
        anonymous=True,
        course=course,
        anonymous_applicant=AnonymousApplicantFactory(
            course=course, email="qa.applicant@example.com"
        ),
        form_progress=FormProgressFactory(user=None),
    )
    progress_pk = application.form_progress.pk

    _reset("qa.applicant@example.com", course.slug)

    assert not AnonymousApplicant.objects.filter(
        email="qa.applicant@example.com"
    ).exists()
    assert not CourseApplication.objects.filter(pk=application.pk).exists()
    assert not FormProgress.objects.filter(pk=progress_pk).exists()


@pytest.mark.django_db
def test_a_reset_keeps_another_addresses_anonymous_application(qa_site):
    UserFactory(email="qa.applicant@example.com")
    course = CourseFactory()
    other = AnonymousApplicantFactory(course=course, email="someone.else@example.com")

    _reset("qa.applicant@example.com", course.slug)

    assert AnonymousApplicant.objects.filter(pk=other.pk).exists()


@pytest.mark.django_db
def test_a_reset_works_for_an_applicant_who_never_claimed(qa_site):
    course = CourseFactory()
    applicant = AnonymousApplicantFactory(
        course=course, email="qa.applicant@example.com"
    )
    CourseApplicationFactory(
        anonymous=True, course=course, anonymous_applicant=applicant
    )

    _reset("qa.applicant@example.com", course.slug)

    assert not AnonymousApplicant.objects.filter(pk=applicant.pk).exists()


@pytest.mark.django_db
def test_a_reset_withdraws_every_application_the_account_holds(qa_site):
    user = UserFactory(email="qa.applicant@example.com")
    course = CourseFactory()
    CourseApplicationFactory(user=user, course=course)
    CourseApplicationFactory(anonymous=True, user=user, course=course)

    _reset("qa.applicant@example.com", course.slug)

    assert not CourseApplication.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db
def test_a_reset_finds_the_account_whatever_the_case_of_the_address(qa_site):
    user = UserFactory(email="QA.Applicant@example.com")
    course = CourseFactory()
    CourseApplicationFactory(user=user, course=course)

    _reset("qa.applicant@example.com", course.slug)

    assert not CourseApplication.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db
def test_a_reset_takes_a_claimed_applications_applicant_row_with_it(qa_site):
    user = UserFactory(email="qa.applicant@example.com")
    course = CourseFactory()
    applicant = AnonymousApplicantFactory(
        course=course, email="qa.applicant@example.com", user=user
    )
    CourseApplicationFactory(
        anonymous=True, user=user, course=course, anonymous_applicant=applicant
    )

    _reset("qa.applicant@example.com", course.slug)

    assert not AnonymousApplicant.objects.filter(pk=applicant.pk).exists()
