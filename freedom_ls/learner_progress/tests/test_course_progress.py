import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress


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


# A learner has to pass to complete: a quiz they sat and failed is an attempt, not
# an item they are done with, so it must not lift the completion percentage.


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
