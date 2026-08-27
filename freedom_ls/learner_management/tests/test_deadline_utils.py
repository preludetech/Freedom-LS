from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.deadline_utils import (
    get_effective_deadlines,
    is_item_locked_by_deadline,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
    LearnerFactory,
    UserCohortDeadlineOverrideFactory,
)
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.organisations.factories import OrganisationFactory

# --- get_effective_deadlines tests ---


@pytest.mark.django_db
def test_single_cohort_deadline_resolves(mock_site_context):
    """A single cohort deadline for a topic resolves correctly."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    deadline_dt = timezone.now() + timedelta(days=7)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == deadline_dt
    assert result[0].is_hard_deadline is True


@pytest.mark.django_db
def test_override_beats_cohort_deadline(mock_site_context):
    """UserCohortDeadlineOverride takes precedence over CohortDeadline for that user."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(
        learner__user=user, cohort=cohort
    )
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    cohort_dt = timezone.now() + timedelta(days=7)
    override_dt = timezone.now() + timedelta(days=14)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=cohort_dt,
    )
    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=override_dt,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == override_dt


@pytest.mark.django_db
def test_override_source_string_renders_the_person_not_learner_str(mock_site_context):
    """The source string must keep rendering the person -- str(learner.user)
    -- not str(learner), which is "user - organisation" and would silently
    change user-visible copy."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(
        learner__user=user, cohort=cohort
    )
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )
    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=14),
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert str(user) in result[0].source
    assert str(membership.learner) not in result[0].source


@pytest.mark.django_db
def test_get_effective_deadlines_returns_empty_when_learner_not_resolved(
    mock_site_context,
):
    """A user with no registration for the course at all -- learner_for_course
    resolves to None -- must yield an empty list rather than raising."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()

    assert get_effective_deadlines(user, course, content_item=topic) == []
    assert get_effective_deadlines(user, course, content_item=None) == []


@pytest.mark.django_db
def test_two_cohorts_in_the_same_organisation_show_both_deadlines(mock_site_context):
    """One Learner belonging to two cohorts in its own organisation, both
    registered for the same course, sees both deadlines -- deadlines are
    scoped to the resolved Learner, not to a single registration."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    organisation = OrganisationFactory()

    cohort_a = CohortFactory(organisation=organisation, name="Cohort A2")
    cohort_b = CohortFactory(organisation=organisation, name="Cohort B")
    CohortMembershipFactory(
        learner__user=user, learner__organisation=organisation, cohort=cohort_a
    )
    CohortMembershipFactory(
        learner__user=user, learner__organisation=organisation, cohort=cohort_b
    )

    reg_a = CohortCourseRegistrationFactory(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistrationFactory(cohort=cohort_b, collection=course)

    dt_a = timezone.now() + timedelta(days=5)
    dt_b = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=reg_a,
        content_item=topic,
        deadline=dt_a,
    )
    CohortDeadlineFactory(
        cohort_course_registration=reg_b,
        content_item=topic,
        deadline=dt_b,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {dt_a, dt_b}


def _two_organisation_deadlines(user, course, topic, *, active_organisation: str):
    """One person, two organisations, one course, a deadline in each.

    `active_organisation` names which of the two registrations is in force, so
    each test states the situation it is asking about rather than mutating its
    way there. Returns (deadline_a, deadline_b).
    """
    deadline_a = timezone.now() + timedelta(days=5)
    deadline_b = timezone.now() + timedelta(days=10)
    registration_a = LearnerCourseRegistrationFactory(
        learner__user=user,
        learner__organisation=OrganisationFactory(),
        collection=course,
        is_active=active_organisation == "a",
    )
    registration_b = LearnerCourseRegistrationFactory(
        learner__user=user,
        learner__organisation=OrganisationFactory(),
        collection=course,
        is_active=active_organisation == "b",
    )
    LearnerDeadlineFactory(
        learner_course_registration=registration_a,
        content_item=topic,
        deadline=deadline_a,
    )
    LearnerDeadlineFactory(
        learner_course_registration=registration_b,
        content_item=topic,
        deadline=deadline_b,
    )
    return deadline_a, deadline_b


@pytest.mark.django_db
def test_only_the_studied_organisations_deadline_is_returned(mock_site_context):
    """A person holding an individual registration for one course in two
    different organisations sees the deadline for whichever Learner
    learner_for_course resolves to -- never a union of both."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    deadline_a, _deadline_b = _two_organisation_deadlines(
        user, course, topic, active_organisation="a"
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert [entry.deadline for entry in result] == [deadline_a]


@pytest.mark.django_db
def test_the_other_organisations_deadline_is_returned_when_it_is_the_live_one(
    mock_site_context,
):
    """The mirror of the test above: neither organisation is the privileged one."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    _deadline_a, deadline_b = _two_organisation_deadlines(
        user, course, topic, active_organisation="b"
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert [entry.deadline for entry in result] == [deadline_b]


@pytest.mark.django_db
def test_cohort_plus_individual_registration_shows_both(mock_site_context):
    """One Learner holding both a cohort registration and an individual
    registration for the same course sees both deadlines -- both loops in
    get_effective_deadlines run against the one resolved Learner."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    membership = CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )
    learner_course_reg = LearnerCourseRegistrationFactory(
        learner=membership.learner, collection=course
    )

    cohort_dt = timezone.now() + timedelta(days=5)
    learner_dt = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=cohort_dt,
    )
    LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
        content_item=topic,
        deadline=learner_dt,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {cohort_dt, learner_dt}


@pytest.mark.django_db
def test_two_individual_registrations_through_different_organisations_show_only_the_resolved_one(
    mock_site_context,
):
    """Two individual registrations for one course became possible when the
    unique constraint widened to include organisation. With both active, the
    resolver reports only the deadline for whichever Learner
    learner_for_course resolves to (the more recently registered one),
    rather than merging both."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
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

    result = get_effective_deadlines(user, course, content_item=topic)

    # Both registrations are active, so the tiebreak in learner_for_course
    # (via latest_registration) falls to recency: reg_b was registered later.
    assert len(result) == 1
    assert result[0].deadline == dt_b


@pytest.mark.django_db
def test_item_level_deadline_beats_course_level(mock_site_context):
    """Item-level deadline takes precedence over course-level within the same registration."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=14)
    item_dt = timezone.now() + timedelta(days=7)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=item_dt,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == item_dt


@pytest.mark.django_db
def test_course_level_deadline_falls_through_when_no_item_level(mock_site_context):
    """Course-level deadline applies when no item-level deadline exists."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=14)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == course_dt


@pytest.mark.django_db
def test_inactive_registrations_ignored(mock_site_context):
    """Deadlines from inactive registrations are not returned."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course, is_active=False
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 0


@pytest.mark.django_db
def test_course_level_deadline_resolves_for_course(mock_site_context):
    """Course-level deadline resolves when asking for the course itself (no content_item)."""
    user = UserFactory()
    course = CourseFactory()
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

    result = get_effective_deadlines(user, course, content_item=None)

    assert len(result) == 1
    assert result[0].deadline == course_dt


# --- is_item_locked_by_deadline tests ---


@pytest.mark.django_db
def test_expired_hard_deadline_incomplete_locks_item(mock_site_context):
    """Expired hard deadline + incomplete item = locked."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is True


@pytest.mark.django_db
def test_expired_hard_deadline_completed_not_locked(mock_site_context):
    """Expired hard deadline + completed item = not locked."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(user, course, topic, is_completed=True) is False


@pytest.mark.django_db
def test_soft_deadline_never_locks(mock_site_context):
    """Soft deadlines never lock, even if expired."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=False,
    )

    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is False


@pytest.mark.django_db
def test_most_permissive_deadline_governs_access(mock_site_context):
    """When one resolved Learner holds multiple hard deadlines -- here, from
    membership of two cohorts in its own organisation, both registered for
    the course -- the latest (most permissive) governs access."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    organisation = OrganisationFactory()

    cohort_a = CohortFactory(organisation=organisation, name="Cohort Lock A")
    cohort_b = CohortFactory(organisation=organisation, name="Cohort Lock B")
    CohortMembershipFactory(
        learner__user=user, learner__organisation=organisation, cohort=cohort_a
    )
    CohortMembershipFactory(
        learner__user=user, learner__organisation=organisation, cohort=cohort_b
    )

    reg_a = CohortCourseRegistrationFactory(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistrationFactory(cohort=cohort_b, collection=course)

    # Cohort A: expired
    CohortDeadlineFactory(
        cohort_course_registration=reg_a,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )
    # Cohort B: not expired yet
    CohortDeadlineFactory(
        cohort_course_registration=reg_b,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is False


@pytest.mark.django_db
def test_no_deadlines_not_locked(mock_site_context):
    """No deadlines means the item is not locked."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()

    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is False


@pytest.mark.django_db
def test_removed_learners_cohort_deadline_does_not_unlock_the_item(mock_site_context):
    """learner_for_course's cohort branch only matches an active membership,
    so a generous deadline held through an organisation the user was removed
    from is never resolved at all -- only the current organisation's expired
    deadline is, which is what locks the item."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    organisation_a = OrganisationFactory()
    organisation_b = OrganisationFactory()
    cohort_a = CohortFactory(organisation=organisation_a, name="Cohort Left")
    cohort_b = CohortFactory(organisation=organisation_b, name="Cohort Current")
    CohortMembershipFactory(
        cohort=cohort_a,
        learner=LearnerFactory(user=user, organisation=organisation_a, is_active=False),
    )
    CohortMembershipFactory(
        cohort=cohort_b,
        learner=LearnerFactory(user=user, organisation=organisation_b),
    )
    CohortDeadlineFactory(
        cohort_course_registration=CohortCourseRegistrationFactory(
            cohort=cohort_a, collection=course
        ),
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )
    CohortDeadlineFactory(
        cohort_course_registration=CohortCourseRegistrationFactory(
            cohort=cohort_b, collection=course
        ),
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is True


@pytest.mark.django_db
def test_a_removed_learners_cohort_contributes_no_deadline(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(user=user, organisation=organisation, is_active=False),
    )
    CohortDeadlineFactory(
        cohort_course_registration=CohortCourseRegistrationFactory(
            cohort=cohort, collection=course
        ),
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )

    assert get_effective_deadlines(user, course, content_item=topic) == []


@pytest.mark.django_db
def test_a_removed_learners_own_registration_still_reaches_their_own_deadlines(
    mock_site_context,
):
    """The individual branch deliberately tolerates an inactive Learner --
    unlike the cohort branch, learner_for_course's fallback to
    latest_registration does not filter on learner.is_active, so a removed
    learner still resolves to their own registration and its deadline."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    removed = LearnerFactory(
        user=user, organisation=OrganisationFactory(), is_active=False
    )
    deadline_dt = timezone.now() + timedelta(days=7)
    LearnerDeadlineFactory(
        learner_course_registration=LearnerCourseRegistrationFactory(
            learner=removed, collection=course
        ),
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == deadline_dt


@pytest.mark.django_db
def test_a_removed_learners_own_cohort_deadline_cannot_unlock_the_item(
    mock_site_context,
):
    """A Learner resolved through the individual fallback may be inactive, and
    they keep their membership rows. is_item_locked_by_deadline takes the most
    permissive hard deadline of everything resolved, so the stale cohort one
    would otherwise unlock content the live expired one locks."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
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
    LearnerDeadlineFactory(
        learner_course_registration=LearnerCourseRegistrationFactory(
            learner=removed, collection=course
        ),
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    result = get_effective_deadlines(user, course, content_item=topic)

    assert [entry.source for entry in result] == ["Individual registration"]
    assert is_item_locked_by_deadline(user, course, topic, is_completed=False) is True
