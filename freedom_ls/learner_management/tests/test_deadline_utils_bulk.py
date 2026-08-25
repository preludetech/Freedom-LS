from datetime import timedelta

import pytest

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.learner_management.deadline_utils import (
    get_course_deadlines,
    get_effective_deadlines,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_bulk_returns_course_level_deadline(mock_site_context):
    """Bulk resolution includes course-level deadlines under (None, None) key."""
    user = UserFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=7)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_course_deadlines(user, course)

    assert (None, None) in result
    assert len(result[(None, None)]) == 1
    assert result[(None, None)][0].deadline == course_dt


@pytest.mark.django_db
def test_bulk_returns_item_level_deadlines(mock_site_context):
    """Bulk resolution includes item-level deadlines under (ct_id, obj_id) keys."""
    user = UserFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    topic1: Topic = TopicFactory(title="T1")
    topic2: Topic = TopicFactory(title="T2")
    course.items.create(child=topic1, order=0)
    course.items.create(child=topic2, order=1)

    topic_ct = ContentType.objects.get_for_model(Topic)
    dt1 = timezone.now() + timedelta(days=5)
    dt2 = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic1,
        deadline=dt1,
    )
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic2,
        deadline=dt2,
    )

    result = get_course_deadlines(user, course)

    key1 = (topic_ct.id, topic1.id)
    key2 = (topic_ct.id, topic2.id)
    assert key1 in result
    assert key2 in result
    assert result[key1][0].deadline == dt1
    assert result[key2][0].deadline == dt2


@pytest.mark.django_db
def test_bulk_matches_per_item_resolution(mock_site_context):
    """Bulk resolution matches per-item resolution for each item."""
    user = UserFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    topic: Topic = TopicFactory(title="Match Topic")
    course.items.create(child=topic, order=0)

    topic_ct = ContentType.objects.get_for_model(Topic)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    bulk_result = get_course_deadlines(user, course)
    per_item_result = get_effective_deadlines(user, course, content_item=topic)

    key = (topic_ct.id, topic.id)
    assert len(bulk_result.get(key, [])) == len(per_item_result)
    assert bulk_result[key][0].deadline == per_item_result[0].deadline


@pytest.mark.django_db
def test_bulk_resolves_only_the_resolved_learners_row_not_a_union(mock_site_context):
    """A person holding two Learner rows for one course (one per organisation)
    sees only the deadline for whichever Learner learner_for_course resolves
    to, not a merged answer across both."""
    user = UserFactory()
    course: Course = CourseFactory()

    topic: Topic = TopicFactory(title="Two Orgs Topic")
    course.items.create(child=topic, order=0)
    topic_ct = ContentType.objects.get_for_model(Topic)

    reg_a = LearnerCourseRegistrationFactory(
        learner__user=user,
        collection=course,
        learner__organisation=OrganisationFactory(),
    )
    reg_b = LearnerCourseRegistrationFactory(
        learner__user=user,
        collection=course,
        learner__organisation=OrganisationFactory(),
    )

    dt_a = timezone.now() + timedelta(days=5)
    dt_b = timezone.now() + timedelta(days=10)
    LearnerDeadlineFactory(
        learner_course_registration=reg_a, content_item=topic, deadline=dt_a
    )
    LearnerDeadlineFactory(
        learner_course_registration=reg_b, content_item=topic, deadline=dt_b
    )

    result = get_course_deadlines(user, course)

    key = (topic_ct.id, topic.id)
    # reg_b was registered later, so it is the one learner_for_course resolves to.
    deadlines = {effective.deadline for effective in result[key]}
    assert deadlines == {dt_b}


@pytest.mark.django_db
def test_bulk_empty_when_no_deadlines(mock_site_context):
    """Bulk resolution returns empty dict when there are no deadlines."""
    user = UserFactory()
    course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    result = get_course_deadlines(user, course)

    assert result == {}


@pytest.mark.django_db
def test_bulk_drops_a_removed_learners_own_cohort_deadline(mock_site_context):
    """Same guard as the per-item resolution: a Learner reached through the
    individual fallback may be inactive, and their stale cohort deadlines must
    not resolve alongside their live individual one."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic: Topic = TopicFactory(title="Removed Learner Topic")
    course.items.create(child=topic, order=0)
    topic_ct = ContentType.objects.get_for_model(Topic)

    organisation = OrganisationFactory()
    removed = LearnerFactory(user=user, organisation=organisation, is_active=False)
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=removed)
    CohortDeadlineFactory(
        cohort_course_registration=CohortCourseRegistrationFactory(
            cohort=cohort, collection=course
        ),
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )
    individual_dt = timezone.now() - timedelta(days=1)
    LearnerDeadlineFactory(
        learner_course_registration=LearnerCourseRegistrationFactory(
            learner=removed, collection=course
        ),
        content_item=topic,
        deadline=individual_dt,
        is_hard_deadline=True,
    )

    result = get_course_deadlines(user, course)

    key = (topic_ct.id, topic.id)
    assert {effective.deadline for effective in result[key]} == {individual_dt}
