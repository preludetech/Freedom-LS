"""The deadlines seed strips the QA learners' overrides and completions, rebuilds the fresh
learner's registration as of now, and leaves other learners' rows alone."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import cast

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.utils import timezone

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import CohortDeadlineOverride, LearnerDeadlineOverride
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.models import SiteTimeZoneConfig

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _parts_course() -> Course:
    course = cast(
        Course,
        CourseFactory(slug="functionality-demo-course-parts", time_limit_days=90),
    )
    for title, due_date, due_time, days in (
        ("Welcome", date(2024, 1, 31), None, None),
        ("What to Expect", None, None, 7),
        ("Key Ideas", None, time(17, 0), 14),
        ("Knowledge Check", None, None, 21),
        ("Course Feedback", None, None, 30),
    ):
        ContentCollectionItemFactory(
            collection_object=course,
            child_object=TopicFactory(title=title),
            due_date=due_date,
            due_time=due_time,
            due_days_after_registration=days,
        )
    return course


@pytest.mark.django_db
def test_seed_strips_qa_residue_and_spares_other_learners(qa_site):
    parts = _parts_course()
    CourseFactory(slug="functionality-demo-show-end-with-topic")
    organisation = OrganisationFactory(name="QA Deadlines Org")
    cohort_registration = CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation, name="QA Deadlines Cohort"),
        course=parts,
    )
    cohort_override = CohortDeadlineOverrideFactory(
        cohort_registration=cohort_registration
    )

    fresh = LearnerFactory(
        user=UserFactory(email="qa_deadline_fresh@email.com"), organisation=organisation
    )
    old_record = CourseProgressFactory(learner=fresh, course=parts)
    old_registration = old_record.learner_registration
    learner_override = LearnerDeadlineOverrideFactory(course_progress=old_record)
    completion = TopicProgressFactory(
        course_progress=old_record, complete_time=timezone.now()
    )

    bystander_record = CourseProgressFactory(course=parts)
    bystander_override = LearnerDeadlineOverrideFactory(
        course_progress=bystander_record
    )

    call_command("qa_create_deadlines_seed")

    assert not CohortDeadlineOverride._base_manager.filter(
        pk=cohort_override.pk
    ).exists()
    assert not LearnerDeadlineOverride._base_manager.filter(
        pk=learner_override.pk
    ).exists()
    assert not TopicProgress._base_manager.filter(pk=completion.pk).exists()
    assert not LearnerCourseRegistration._base_manager.filter(
        pk=old_registration.pk
    ).exists()
    assert LearnerDeadlineOverride._base_manager.filter(
        pk=bystander_override.pk
    ).exists()

    fresh_record = CourseProgress._base_manager.get(
        learner__user__email="qa_deadline_fresh@email.com", course=parts
    )
    assert timezone.now() - fresh_record.created_at < timedelta(minutes=1)
    cohort_record = CourseProgress._base_manager.get(
        learner__user__email="qa_deadline_cohort@email.com", course=parts
    )
    assert cohort_record.cohort_registration == cohort_registration
    assert cohort_record.created_at == datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    assert not CourseProgress._base_manager.filter(
        learner__user__email="qa_deadline_none@email.com"
    ).exists()
    config = SiteTimeZoneConfig._base_manager.get(site=qa_site)
    assert config.time_zone == "Africa/Johannesburg"
