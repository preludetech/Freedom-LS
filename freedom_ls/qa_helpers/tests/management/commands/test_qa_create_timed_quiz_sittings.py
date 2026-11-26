"""The seeder replaces only the named learner's sittings at the timed quiz with
one time-expired and one learner-submitted sitting, both linked to the course."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.enums import CompletionReason
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.learner_progress.queries import course_progress_for

pytestmark = pytest.mark.dev_tooling

TIME_LIMIT = 10

CaptureCallbacks = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture
def qa_site(mock_site_context: Site) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _timed_course() -> tuple[Course, Form, ContentCollectionItem]:
    course: Course = CourseFactory()
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, time_limit_minutes=TIME_LIMIT)
    item: ContentCollectionItem = ContentCollectionItemFactory(
        collection_object=course, child_object=form, order=0
    )
    page = FormPageFactory(form=form, order=0)
    for order in range(2):
        question = FormQuestionFactory(form_page=page, order=order)
        QuestionOptionFactory(question=question, order=0, correct=True)
        QuestionOptionFactory(question=question, order=1, correct=False)
    return course, form, item


@pytest.mark.django_db
def test_replaces_the_learners_sittings_with_one_expired_and_one_submitted(
    qa_site: Site,
    django_capture_on_commit_callbacks: CaptureCallbacks,
) -> None:
    course, form, item = _timed_course()
    member: CohortMembership = CohortMembershipFactory()
    bystander: CohortMembership = CohortMembershipFactory(cohort=member.cohort)
    user = member.learner.user
    # The registration mints its records on commit, which a test transaction
    # never reaches, so it is made up front with the callbacks run; the command
    # then finds the cohort already registered.
    with django_capture_on_commit_callbacks(execute=True):
        CohortCourseRegistrationFactory(cohort=member.cohort, course=course)

    call_command(
        "qa_create_timed_quiz_sittings",
        "--course-slug",
        course.slug,
        "--cohort-name",
        member.cohort.name,
        "--email",
        user.email,
    )
    record = course_progress_for(user, course)
    assert record is not None
    first_run = set(
        FormProgress.objects.filter(user=user, form=form).values_list("pk", flat=True)
    )

    bystander_record = CourseProgress.objects.get(
        learner=bystander.learner, course=course
    )
    bystander_sitting = CourseFormAttemptFactory(
        course_progress=bystander_record, collection_item=item, form=form
    ).form_progress

    call_command(
        "qa_create_timed_quiz_sittings",
        "--course-slug",
        course.slug,
        "--cohort-name",
        member.cohort.name,
        "--email",
        user.email,
    )

    sittings = {
        sitting.completion_reason: sitting
        for sitting in FormProgress.objects.filter(user=user, form=form)
    }
    assert set(sittings) == {
        CompletionReason.TIME_EXPIRED,
        CompletionReason.LEARNER_SUBMITTED,
    }
    assert first_run.isdisjoint(sitting.pk for sitting in sittings.values())

    expired = sittings[CompletionReason.TIME_EXPIRED]
    assert expired.time_limit_minutes == TIME_LIMIT
    assert expired.completed_time == expired.start_time + timedelta(minutes=TIME_LIMIT)
    submitted = sittings[CompletionReason.LEARNER_SUBMITTED]
    assert submitted.time_limit_minutes == TIME_LIMIT
    assert submitted.completed_time is not None
    assert submitted.completed_time - submitted.start_time < timedelta(
        minutes=TIME_LIMIT
    )
    for sitting in sittings.values():
        assert sitting.scores is not None
        assert CourseFormAttempt.objects.filter(
            form_progress=sitting, course_progress=record, collection_item=item
        ).exists()

    assert FormProgress.objects.filter(pk=bystander_sitting.pk).exists()
