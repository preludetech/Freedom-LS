from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.deadline_utils import (
    get_course_deadlines,
    get_effective_deadlines,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCohortDeadlineOverride,
    LearnerCourseRegistration,
    LearnerDeadline,
)
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "factory",
    [
        CohortDeadlineFactory,
        LearnerDeadlineFactory,
        LearnerCohortDeadlineOverrideFactory,
    ],
)
def test_str_names_the_content_item_or_the_whole_course(
    mock_site_context, factory
) -> None:
    topic = TopicFactory(title="Test Topic")

    item_deadline = factory(content_item=topic)
    course_deadline = factory()

    assert "Test Topic" in str(item_deadline)
    assert "Whole course" in str(course_deadline)


@pytest.mark.django_db
def test_create_cohort_deadline_with_content_item(mock_site_context):
    """CohortDeadline can be created pointing to a specific content item."""
    topic = TopicFactory(title="Test Topic")
    cohort_course_reg = CohortCourseRegistrationFactory()

    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: CohortDeadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert deadline.cohort_course_registration == cohort_course_reg
    assert deadline.content_item == topic
    assert deadline.deadline == deadline_dt
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_cohort_deadline_for_whole_course(mock_site_context):
    """CohortDeadline with null content_item applies to the whole course."""
    cohort_course_reg = CohortCourseRegistrationFactory()
    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: CohortDeadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=deadline_dt,
    )

    assert deadline.content_type is None
    assert deadline.object_id is None
    assert deadline.content_item is None


@pytest.mark.django_db
def test_cohort_deadline_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context,
):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic = TopicFactory()
    cohort_course_reg = CohortCourseRegistrationFactory()

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        CohortDeadlineFactory(
            cohort_course_registration=cohort_course_reg,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
        )


@pytest.mark.django_db
def test_cohort_deadline_clean_prevents_duplicate_course_level_deadline(
    mock_site_context,
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    cohort_course_reg = CohortCourseRegistrationFactory()

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
    )

    duplicate = CohortDeadline(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_create_learner_deadline_with_content_item(mock_site_context):
    """LearnerDeadline can be created pointing to a specific content item."""
    topic = TopicFactory()
    learner_course_reg = LearnerCourseRegistrationFactory()

    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: LearnerDeadline = LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert deadline.learner_course_registration == learner_course_reg
    assert deadline.content_item == topic
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_learner_deadline_for_whole_course(mock_site_context):
    """LearnerDeadline with null content_item applies to the whole course."""
    learner_course_reg = LearnerCourseRegistrationFactory()

    deadline: LearnerDeadline = LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
    )

    assert deadline.content_item is None


@pytest.mark.django_db
def test_learner_deadline_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context,
):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic = TopicFactory()
    learner_course_reg = LearnerCourseRegistrationFactory()

    LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        LearnerDeadlineFactory(
            learner_course_registration=learner_course_reg,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
        )


@pytest.mark.django_db
def test_learner_deadline_clean_prevents_duplicate_course_level_deadline(
    mock_site_context,
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    learner_course_reg = LearnerCourseRegistrationFactory()

    LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
    )

    duplicate = LearnerDeadline(
        learner_course_registration=learner_course_reg,
        deadline=timezone.now() + timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_content_item_is_stored_as_a_generic_reference(mock_site_context):
    """`content_item` is a GenericForeignKey: it writes both halves of the pair."""
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override: LearnerCohortDeadlineOverride = LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
    )

    assert override.content_type == ContentType.objects.get_for_model(topic)
    assert override.object_id == topic.pk


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_override(mock_site_context):
    """Cannot create two overrides for the same learner + content item."""
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        LearnerCohortDeadlineOverrideFactory(
            cohort_course_registration=cohort_course_reg,
            learner=membership.learner,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_override(mock_site_context):
    """clean() raises ValidationError for duplicate course-level overrides."""
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
    )

    duplicate = LearnerCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        deadline=timezone.now() + timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_clean_validates_learner_in_cohort(mock_site_context):
    """clean() raises ValidationError if the learner is not a member of the cohort."""
    cohort_course_reg = CohortCourseRegistrationFactory()
    learner = LearnerFactory(organisation=cohort_course_reg.cohort.organisation)

    # learner is NOT in the cohort (no membership created)
    override = LearnerCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        learner=learner,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()


@pytest.mark.django_db
def test_clean_does_not_raise_when_learner_is_unset(mock_site_context):
    """An unset learner means a field-level error already exists (an invalid
    choice in the admin inline); clean() must let that surface rather than
    crashing on the missing relation."""
    override = LearnerCohortDeadlineOverride(
        cohort_course_registration=CohortCourseRegistrationFactory(),
        deadline=timezone.now() + timedelta(days=7),
    )

    override.clean()


@pytest.mark.django_db
def test_clean_does_not_raise_when_the_registration_is_unset(mock_site_context):
    override = LearnerCohortDeadlineOverride(
        learner=LearnerFactory(),
        deadline=timezone.now() + timedelta(days=7),
    )

    override.clean()


# Self-registration through initiate_course_access (the chokepoint for
# self-service course access) keys on Learner: the Learner it creates, its
# idempotence, and reactivation of a removed learner. The backend-branching
# coverage (gated vs free, GET vs POST) is in learner_interface views.
def _initiate_course_access_url(course_slug: str) -> str:
    return reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course_slug}
    )


@pytest.mark.django_db
def test_self_registering_creates_a_learner_on_the_default_organisation(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    default_organisation = get_default_organisation(site)
    learner = Learner.objects.get(user=user, organisation=default_organisation)
    assert learner.is_active is True
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, is_active=True
    ).exists()


@pytest.mark.django_db
def test_self_registering_twice_creates_one_learner_and_one_registration(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)
    url = _initiate_course_access_url(course.slug)

    client.post(url)
    client.post(url)

    default_organisation = get_default_organisation(site)
    assert (
        Learner.objects.filter(user=user, organisation=default_organisation).count()
        == 1
    )
    assert (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, course=course
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_self_registering_reactivates_a_removed_learner(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    default_organisation = get_default_organisation(site)
    LearnerFactory(user=user, organisation=default_organisation, is_active=False)
    client = logged_in_client(user)
    assert is_registered_for_course(user, course) is False

    client.post(_initiate_course_access_url(course.slug))

    learner = Learner.objects.get(user=user, organisation=default_organisation)
    assert learner.is_active is True
    assert is_registered_for_course(user, course) is True


@pytest.mark.django_db
def test_self_registering_reactivates_a_deactivated_registration(
    mock_site_context, site, logged_in_client, course_with_topic
):
    """An admin may deactivate the registration rather than the Learner.
    Re-registering has to restore access: finding the row and leaving it
    inactive dead-ends the learner, since course_home then bounces them
    straight back to the course detail page."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=get_default_organisation(site))
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    client = logged_in_client(user)
    assert is_registered_for_course(user, course) is False

    client.post(_initiate_course_access_url(course.slug))

    assert is_registered_for_course(user, course) is True


@pytest.mark.django_db
def test_self_registering_marks_a_new_registration_as_self_registered(
    mock_site_context, logged_in_client, course_with_topic
) -> None:
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    assert LearnerCourseRegistration.objects.get(
        learner__user=user, course=course
    ).self_registered


@pytest.mark.django_db
def test_reactivating_an_admin_registration_leaves_it_marked_as_not_self_registered(
    mock_site_context, site, logged_in_client, course_with_topic
) -> None:
    course = course_with_topic(access_type="free")
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=get_default_organisation(site))
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    assert not LearnerCourseRegistration.objects.get(
        learner=learner, course=course
    ).self_registered


# Tests for the enrolment models and their Learner relations.


@pytest.mark.django_db
class TestCohortMembershipClean:
    def test_rejects_a_learner_and_cohort_in_different_organisations(
        self, mock_site_context
    ):
        learner = LearnerFactory(organisation=OrganisationFactory())
        cohort = CohortFactory(
            organisation=OrganisationFactory(), name="Year 10 Science"
        )

        membership = CohortMembership(learner=learner, cohort=cohort)

        with pytest.raises(ValidationError):
            membership.clean()

    def test_permits_a_learner_and_cohort_in_the_same_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 10 Maths")

        membership = CohortMembership(learner=learner, cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_learner_is_unset(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory())

        membership = CohortMembership(cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_cohort_is_unset(self, mock_site_context):
        learner = LearnerFactory(organisation=OrganisationFactory())

        membership = CohortMembership(learner=learner)

        membership.clean()


@pytest.mark.django_db
class TestCohortNameUniqueness:
    """Cohort names are unique per organisation, not per site: the same name may
    be used once in each organisation."""

    def test_two_cohorts_with_one_name_in_one_organisation_are_rejected(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        CohortFactory(organisation=organisation, name="Year 10 Science")

        with pytest.raises(IntegrityError):
            CohortFactory(organisation=organisation, name="Year 10 Science")

    def test_the_same_cohort_name_in_two_organisations_is_permitted(
        self, mock_site_context
    ):
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")

        assert Cohort.objects.filter(name="Year 10 Science").count() == 2


@pytest.mark.django_db
class TestLearnerCourseRegistrationUniqueness:
    """One learner per organisation, one registration each -- the same user
    can hold a registration in two organisations because each organisation
    gives them a distinct Learner row."""

    def test_two_registrations_for_one_learner_and_course_are_rejected(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=course)

        with pytest.raises(IntegrityError):
            LearnerCourseRegistrationFactory(learner=learner, course=course)

    def test_one_user_may_register_for_one_course_through_two_organisations(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        learner_a = LearnerFactory(user=user, organisation=OrganisationFactory())
        learner_b = LearnerFactory(user=user, organisation=OrganisationFactory())
        LearnerCourseRegistrationFactory(learner=learner_a, course=course)
        LearnerCourseRegistrationFactory(learner=learner_b, course=course)

        assert (
            LearnerCourseRegistration.objects.filter(
                learner__user=user, course=course
            ).count()
            == 2
        )


@pytest.mark.django_db
class TestDeactivatingALearnerPreservesRecords:
    """Removal is soft and never cascades: every enrolment and progress row a
    removed learner held stays exactly as it was. Only access is suspended."""

    def test_the_course_registration_stays_active(self, mock_site_context):
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner)

        learner.is_active = False
        learner.save()

        registration.refresh_from_db()
        assert registration.is_active is True

    def test_the_cohort_membership_survives(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        membership = CohortMembershipFactory(
            learner=learner, cohort=CohortFactory(organisation=organisation)
        )

        learner.is_active = False
        learner.save()

        assert CohortMembership.objects.filter(pk=membership.pk).exists()

    def test_access_to_the_registered_course_is_suspended(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=course)

        learner.is_active = False
        learner.save()

        assert is_registered_for_course(learner.user, course) is False


# Tests for the Learner model.


@pytest.mark.django_db
class TestLearnerUniqueness:
    """Learner.objects.create, not LearnerFactory: the factory delegates to
    ensure_learner, which is idempotent by design and so can never produce the
    duplicate row these tests need."""

    def test_duplicate_user_and_organisation_is_rejected(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        Learner.objects.create(user=user, organisation=organisation)

        with pytest.raises(IntegrityError):
            Learner.objects.create(user=user, organisation=organisation)

    def test_same_user_may_hold_rows_in_two_organisations(self, mock_site_context):
        user = UserFactory()
        Learner.objects.create(user=user, organisation=OrganisationFactory())
        Learner.objects.create(user=user, organisation=OrganisationFactory())

        assert Learner.objects.filter(user=user).count() == 2


@pytest.mark.django_db
class TestLearnerSite:
    def test_learner_takes_its_site_from_its_organisation(self, mock_site_context):
        organisation = OrganisationFactory()

        learner = Learner.objects.create(user=UserFactory(), organisation=organisation)

        assert learner.site_id == organisation.site_id


# Deletion semantics for the registration and deadline models.
#
# Registrations PROTECT their course; the deadline models SET_NULL their
# content_type on a deleted ContentType and keep reading as a whole-course
# deadline afterward.


def _delete_content_type_for(instance: object) -> None:
    """Delete a model's ContentType row without poisoning the process-wide cache.

    ``ContentType.objects.get_for_model()`` caches the Python object it
    returns; calling ``.delete()`` on that cached instance mutates its ``pk``
    to ``None`` in place, so a later test's ``get_for_model()`` call for the
    same model would hand back an already-"deleted" instance. Deleting
    through a fresh queryset instead leaves that cached instance untouched.
    """
    content_type = ContentType.objects.get_for_model(instance)
    ContentType.objects.filter(pk=content_type.pk).delete()


@pytest.mark.django_db
class TestRegistrationCourseProtect:
    def test_deleting_a_course_with_a_learner_registration_is_blocked(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()

    def test_deleting_a_course_with_a_cohort_registration_is_blocked(
        self, mock_site_context
    ):
        registration = CohortCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()


def _cohort_deadline_on(topic):
    return CohortDeadlineFactory(content_item=topic)


def _learner_deadline_on(topic):
    return LearnerDeadlineFactory(content_item=topic)


def _override_on(topic):
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory(cohort=membership.cohort)
    return LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=registration,
        learner=membership.learner,
        content_item=topic,
    )


DEADLINE_BUILDERS = [
    ("CohortDeadline", _cohort_deadline_on),
    ("LearnerDeadline", _learner_deadline_on),
    ("LearnerCohortDeadlineOverride", _override_on),
]


@pytest.mark.django_db
class TestDeadlineContentTypeSetNull:
    """Losing the content type leaves the row pointing at nothing in particular.

    The FK is SET_NULL rather than CASCADE so the deadline itself survives; what
    matters to the rest of the system is that `content_item` then resolves to
    None, which is how a whole-course deadline is spelled.
    """

    @pytest.mark.parametrize(
        "build_deadline",
        [builder for _, builder in DEADLINE_BUILDERS],
        ids=[name for name, _ in DEADLINE_BUILDERS],
    )
    def test_an_orphaned_deadline_points_at_no_content_item(
        self, mock_site_context, build_deadline
    ):
        topic = TopicFactory()
        deadline = build_deadline(topic)

        _delete_content_type_for(topic)

        deadline.refresh_from_db()
        assert deadline.content_item is None

    @pytest.mark.parametrize(
        "build_deadline",
        [builder for _, builder in DEADLINE_BUILDERS],
        ids=[name for name, _ in DEADLINE_BUILDERS],
    )
    def test_an_orphaned_deadline_still_validates(
        self, mock_site_context, build_deadline
    ):
        """clean() keys on content_type alone, so a half-nulled row is still legal."""
        topic = TopicFactory()
        deadline = build_deadline(topic)

        _delete_content_type_for(topic)
        deadline.refresh_from_db()

        deadline.full_clean()


@pytest.mark.django_db
class TestOrphanedDeadlineResolvesAsWholeCourse:
    """A deadline stripped of its content type is a whole-course deadline.

    ``object_id`` survives the ``SET_NULL``, so the row keeps pointing at a
    content item that no deadline lookup can reach any more. Resolution has to
    read it the same way ``clean()`` and ``__str__`` already do.
    """

    def test_cohort_deadline_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(learner__user=user, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        deadline_dt = timezone.now() + timedelta(days=7)
        CohortDeadlineFactory(
            cohort_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [deadline_dt]

    def test_learner_deadline_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        registration = LearnerCourseRegistrationFactory(
            learner__user=user, course=course
        )
        deadline_dt = timezone.now() + timedelta(days=7)
        LearnerDeadlineFactory(
            learner_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [deadline_dt]

    def test_override_resolves_for_the_whole_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        membership = CohortMembershipFactory(learner__user=user)
        registration = CohortCourseRegistrationFactory(
            cohort=membership.cohort, course=course
        )
        override_dt = timezone.now() + timedelta(days=14)
        LearnerCohortDeadlineOverrideFactory(
            cohort_course_registration=registration,
            learner=membership.learner,
            content_item=topic,
            deadline=override_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_effective_deadlines(user, course)

        assert [effective.deadline for effective in resolved] == [override_dt]

    def test_bulk_resolution_keys_the_orphan_under_the_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        topic = TopicFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(learner__user=user, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        deadline_dt = timezone.now() + timedelta(days=7)
        CohortDeadlineFactory(
            cohort_course_registration=registration,
            content_item=topic,
            deadline=deadline_dt,
        )

        _delete_content_type_for(topic)

        resolved = get_course_deadlines(user, course)

        assert list(resolved) == [(None, None)]
        assert [effective.deadline for effective in resolved[(None, None)]] == [
            deadline_dt
        ]
