from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ActivityFactory,
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, Topic
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.utils import calculate_course_progress_percentage


@pytest.mark.django_db
def test_completing_topic_updates_progress_percentage(mock_site_context):
    """Test that completing a topic updates progress_percentage on its record."""
    course = CourseFactory()
    topic = TopicFactory()
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=0
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    tp: TopicProgress = TopicProgressFactory(
        course_progress=course_progress, collection_item=collection_item, topic=topic
    )
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_form_updates_progress_percentage(mock_site_context):
    """Test that completing a form updates progress_percentage on its record."""
    course = CourseFactory()
    form = FormFactory(strategy="QUIZ")
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=form, order=0
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    fp: FormProgress = CourseFormAttemptFactory(
        course_progress=course_progress,
        collection_item=collection_item,
        form=form,
    ).form_progress
    fp.complete()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_course_part_counts_toward_the_course(mock_site_context):
    """An item inside a CoursePart still counts toward its course's percentage."""
    course = CourseFactory()
    part = CoursePartFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    collection_item = ContentCollectionItemFactory(
        collection_object=part, child_object=topic, order=0
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    tp: TopicProgress = TopicProgressFactory(
        course_progress=course_progress, collection_item=collection_item, topic=topic
    )
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_a_topic_in_one_course_leaves_the_other_at_zero(mock_site_context):
    """One topic placed in two courses is completed independently in each."""
    topic = TopicFactory()
    course = CourseFactory()
    other_course = CourseFactory()
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=other_course, child_object=topic, order=0
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)
    other_progress: CourseProgress = CourseProgressFactory(course=other_course)

    tp: TopicProgress = TopicProgressFactory(
        course_progress=course_progress, collection_item=collection_item, topic=topic
    )
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    other_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100
    assert other_progress.progress_percentage == 0


@pytest.mark.django_db
def test_organisations_hold_their_own_percentage_for_one_learner(mock_site_context):
    """One person studying the same course through two organisations progresses
    through each separately -- one organisation's completions never count
    toward the other's percentage."""
    user = UserFactory()
    course = CourseFactory()
    collection_items = [
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=index
        )
        for index in range(4)
    ]
    first: CourseProgress = CourseProgressFactory(
        learner=LearnerFactory(user=user), course=course
    )
    second: CourseProgress = CourseProgressFactory(
        learner=LearnerFactory(user=user), course=course
    )

    _complete_topic(first, collection_items[0])
    _complete_topic(second, collection_items[1])
    _complete_topic(second, collection_items[2])

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.progress_percentage == 25
    assert second.progress_percentage == 50


def _complete_topic(record, collection_item) -> None:
    """Record and complete one topic within one course progress record."""
    tp: TopicProgress = TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item,
        topic=collection_item.child,
    )
    tp.complete_time = timezone.now()
    tp.save()


@pytest.mark.django_db
def test_completing_an_item_mints_no_further_record(mock_site_context):
    """Records come from registrations; a completion never creates one."""
    course = CourseFactory()
    topic = TopicFactory()
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=0
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    tp: TopicProgress = TopicProgressFactory(
        course_progress=course_progress, collection_item=collection_item, topic=topic
    )
    tp.complete_time = timezone.now()
    tp.save()

    assert CourseProgress.objects.count() == 1


@pytest.mark.django_db
def test_failed_quiz_does_not_count_toward_progress_percentage(
    mock_site_context, course_with_scored_quiz, sit_quiz
):
    """A quiz sat and failed leaves the course incomplete."""
    course, form, question, _right, wrong = course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    sit_quiz(course_progress, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_passing_a_retry_makes_a_previously_failed_quiz_count(
    mock_site_context, course_with_scored_quiz, sit_quiz
):
    """Failing then passing leaves the learner complete — the latest sitting decides."""
    course, form, question, right, wrong = course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    sit_quiz(course_progress, form, question, wrong)
    sit_quiz(course_progress, form, question, right)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_failing_a_retry_uncounts_a_previously_passed_quiz(
    mock_site_context, course_with_scored_quiz, sit_quiz
):
    """Passing then failing a retry takes the completion back — the latest sitting decides."""
    course, form, question, right, wrong = course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    sit_quiz(course_progress, form, question, right)
    sit_quiz(course_progress, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_quiz_with_no_pass_mark_counts_toward_progress_percentage(
    mock_site_context, course_with_scored_quiz, sit_quiz
):
    """No pass mark means no bar to clear, so sitting it is completing it."""
    course, form, question, _right, wrong = course_with_scored_quiz(
        pass_percentage=None
    )
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    sit_quiz(course_progress, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_one_of_two_placements_credits_only_that_placement(
    mock_site_context,
):
    """One topic placed twice is two items to complete.

    The course outline is keyed on the placement, so crediting the content
    would show the second position as untouched while the percentage already
    counted it.
    """
    course = CourseFactory()
    topic = TopicFactory()
    first_placement = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=0
    )
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=1)
    course_progress: CourseProgress = CourseProgressFactory(course=course)

    tp: TopicProgress = TopicProgressFactory(
        course_progress=course_progress,
        collection_item=first_placement,
        topic=topic,
    )
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 50


@pytest.mark.django_db
def test_course_with_no_children_returns_zero_percent(mock_site_context):
    """Course with no children should return 0% progress."""
    course: Course = CourseFactory()
    percentage = calculate_course_progress_percentage(course, set())
    assert percentage == 0


@pytest.mark.parametrize(
    ("completed", "total", "expected"),
    [
        (0, 1, 0),
        (1, 1, 100),
        (1, 2, 50),
        (1, 3, 33),
        (2, 3, 67),
        (3, 4, 75),
        (1, 4, 25),
    ],
    ids=[
        "0_of_1_is_0",
        "1_of_1_is_100",
        "1_of_2_is_50",
        "1_of_3_is_33",
        "2_of_3_is_67",
        "3_of_4_is_75",
        "1_of_4_is_25",
    ],
)
@pytest.mark.django_db
def test_progress_percentage_for_n_of_m(mock_site_context, completed, total, expected):
    """Hard-coded oracles for completed/total → percentage. Oracles written down, not derived."""
    course: Course = CourseFactory()
    placements = [
        course.items.create(child=TopicFactory(title=f"Topic {i}"), order=i)
        for i in range(total)
    ]
    completed_item_ids = {item.id for item in placements[:completed]}

    percentage = calculate_course_progress_percentage(course, completed_item_ids)

    assert percentage == expected


@pytest.mark.django_db
def test_course_with_mixed_content(mock_site_context):
    """Course with mixed content types (Topic + Form) should calculate correctly."""
    course: Course = CourseFactory()
    topic: Topic = TopicFactory()
    test_form: Form = FormFactory()
    topic_item = course.items.create(child=topic, order=0)
    course.items.create(child=test_form, order=1)

    # Only topic completed
    percentage = calculate_course_progress_percentage(course, {topic_item.id})
    assert percentage == 50


@pytest.mark.django_db
def test_course_with_course_part_children(mock_site_context):
    """An item nested in a CoursePart still counts towards the course total."""
    course: Course = CourseFactory()
    part: CoursePart = CoursePartFactory(title="Part 1")

    topic1: Topic = TopicFactory(title="Topic 1")
    topic2: Topic = TopicFactory(title="Topic 2")
    item1 = part.items.create(child=topic1, order=0)
    part.items.create(child=topic2, order=1)

    course.items.create(child=part, order=0)

    percentage = calculate_course_progress_percentage(course, {item1.id})

    assert percentage == 50


@pytest.mark.django_db
def test_course_with_mixed_direct_and_part_children(mock_site_context):
    """Course with both direct items and items inside CourseParts."""
    course: Course = CourseFactory()
    direct_topic: Topic = TopicFactory(title="Direct Topic")
    direct_item = course.items.create(child=direct_topic, order=0)

    part: CoursePart = CoursePartFactory(title="Part 1")
    part_topic1: Topic = TopicFactory(title="Part Topic 1")
    part_topic2: Topic = TopicFactory(title="Part Topic 2")
    part_item1 = part.items.create(child=part_topic1, order=0)
    part.items.create(child=part_topic2, order=1)
    course.items.create(child=part, order=1)

    percentage = calculate_course_progress_percentage(
        course, {direct_item.id, part_item1.id}
    )
    assert percentage == 67


@pytest.mark.django_db
def test_one_topic_placed_twice_counts_as_two_items(mock_site_context):
    """Each placement of a twice-placed topic is completed on its own.

    The course outline reads the placement, so a content-keyed percentage would
    credit both positions for one completion and disagree with what the learner
    can see.
    """
    course: Course = CourseFactory()
    topic: Topic = TopicFactory(title="Placed twice")
    other: Topic = TopicFactory(title="Placed once")
    first_placement = course.items.create(child=topic, order=0)
    course.items.create(child=other, order=1)
    course.items.create(child=topic, order=2)

    percentage = calculate_course_progress_percentage(course, {first_placement.id})

    assert percentage == 33


@pytest.mark.django_db
def test_a_placed_activity_is_excluded_from_the_count(mock_site_context):
    """Activities are placeable but have no completion, so they are not counted."""
    course: Course = CourseFactory()
    topic_item = course.items.create(child=TopicFactory(title="Topic"), order=0)
    course.items.create(child=ActivityFactory(title="Activity"), order=1)

    percentage = calculate_course_progress_percentage(course, {topic_item.id})

    assert percentage == 100


# The uniqueness, check and PROTECT guarantees CourseProgress now carries.
#
# These shapes are net-new: the previous unique_together on (user, course) made
# "two records for one learner and one course" impossible to express at all.


def _cohort_grant(learner, course):
    """An active cohort registration for `course` with `learner` a member."""
    cohort = CohortFactory(organisation=learner.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return CohortCourseRegistrationFactory(cohort=cohort, course=course)


@pytest.mark.django_db
class TestUniquenessPerRegistration:
    def test_second_record_for_one_learner_registration_is_rejected(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory()
        CourseProgressFactory(
            learner=registration.learner,
            course=registration.course,
            learner_registration=registration,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=registration.learner,
                course=registration.course,
                learner_registration=registration,
            )

    def test_second_record_for_one_cohort_registration_is_rejected(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=learner,
                course=course,
                learner_registration=None,
                cohort_registration=registration,
            )

    def test_many_cohort_granted_records_for_one_learner_coexist(
        self, mock_site_context
    ):
        """They all share a null learner_registration, and NULLs are distinct."""
        learner = LearnerFactory()
        first = _cohort_grant(learner, CourseFactory())
        second = _cohort_grant(learner, CourseFactory())

        CourseProgressFactory(
            learner=learner,
            course=first.course,
            learner_registration=None,
            cohort_registration=first,
        )
        CourseProgressFactory(
            learner=learner,
            course=second.course,
            learner_registration=None,
            cohort_registration=second,
        )

        assert CourseProgress.objects.filter(learner=learner).count() == 2

    def test_many_individually_granted_records_for_one_learner_coexist(
        self, mock_site_context
    ):
        """The mirror image: they all share a null cohort_registration."""
        learner = LearnerFactory()
        first = LearnerCourseRegistrationFactory(learner=learner)
        second = LearnerCourseRegistrationFactory(learner=learner)

        CourseProgressFactory(
            learner=learner, course=first.course, learner_registration=first
        )
        CourseProgressFactory(
            learner=learner, course=second.course, learner_registration=second
        )

        assert CourseProgress.objects.filter(learner=learner).count() == 2

    def test_one_learner_and_course_may_hold_one_record_per_grant(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort_registration = _cohort_grant(learner, course)
        learner_registration = LearnerCourseRegistrationFactory(
            learner=learner, course=course
        )

        CourseProgressFactory(
            learner=learner, course=course, learner_registration=learner_registration
        )
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=cohort_registration,
        )

        assert (
            CourseProgress.objects.filter(learner=learner, course=course).count() == 2
        )


@pytest.mark.django_db
class TestExactlyOneGrant:
    def test_a_record_naming_both_grants_is_rejected(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort_registration = _cohort_grant(learner, course)
        learner_registration = LearnerCourseRegistrationFactory(
            learner=learner, course=course
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=learner,
                course=course,
                learner_registration=learner_registration,
                cohort_registration=cohort_registration,
            )

    def test_a_record_naming_no_grant_is_rejected(self, mock_site_context):
        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(learner_registration=None, cohort_registration=None)


@pytest.mark.django_db
class TestGrantIsProtected:
    def test_deleting_a_learner_registration_that_granted_a_record_is_blocked(
        self, mock_site_context
    ):
        record = CourseProgressFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            record.learner_registration.delete()

    def test_deleting_a_cohort_registration_that_granted_a_record_is_blocked(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.delete()

    def test_deactivating_a_registration_leaves_the_record_alone(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        registration = record.learner_registration

        registration.is_active = False
        registration.save()

        record.refresh_from_db()
        assert record.learner_registration_id == registration.id


@pytest.mark.django_db
class TestCleanGuardsThePairing:
    def test_a_registration_for_another_course_is_rejected(self, mock_site_context):
        record = CourseProgressFactory()
        record.course = CourseFactory()

        with pytest.raises(ValidationError, match="for this course"):
            record.full_clean()

    def test_a_registration_belonging_to_another_learner_is_rejected(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        other = LearnerCourseRegistrationFactory(course=record.course)
        record.learner_registration = other

        with pytest.raises(ValidationError, match="belong to this learner"):
            record.full_clean()

    def test_a_cohort_granted_record_survives_the_learner_leaving_the_cohort(
        self, mock_site_context
    ):
        """An unconditional membership check would make this row unsaveable."""
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        record = CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )
        CohortMembership.objects.filter(
            cohort=registration.cohort, learner=learner
        ).delete()

        record.full_clean()

        assert record.cohort_registration_id == registration.id

    def test_a_new_cohort_granted_record_needs_a_membership(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort = CohortFactory(organisation=learner.organisation)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        record = CourseProgress(
            site=course.site,
            learner=learner,
            course=course,
            cohort_registration=registration,
        )

        with pytest.raises(ValidationError, match="not a member"):
            record.full_clean()

    def test_a_cohort_in_another_organisation_is_rejected(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort = CohortFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        record = CourseProgress(
            site=course.site,
            learner=learner,
            course=course,
            cohort_registration=registration,
        )

        with pytest.raises(ValidationError, match="same organisation"):
            record.full_clean()
