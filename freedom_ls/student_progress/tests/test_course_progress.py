import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)


@pytest.mark.django_db
def test_course_progress_has_progress_percentage_field(mock_site_context):
    """Test that CourseProgress has a progress_percentage field that defaults to 0."""
    course_progress: CourseProgress = CourseProgressFactory()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_course_progress_progress_percentage_can_be_set(mock_site_context):
    """Test that progress_percentage can be set to a specific value."""
    progress: CourseProgress = CourseProgressFactory(progress_percentage=50)
    progress.refresh_from_db()
    assert progress.progress_percentage == 50


@pytest.mark.django_db
def test_completing_topic_updates_progress_percentage(mock_site_context):
    """Test that completing a topic updates progress_percentage on the related CourseProgress."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    # Complete the topic
    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_form_updates_progress_percentage(mock_site_context):
    """Test that completing a form updates progress_percentage on the related CourseProgress."""
    user = UserFactory()
    course = CourseFactory()
    form = FormFactory(strategy="QUIZ")
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    # Complete the form via complete() method
    fp: FormProgress = FormProgressFactory(user=user, form=form)
    fp.complete()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_course_part_updates_parent_course(mock_site_context):
    """Test that completing an item inside a CoursePart traces up to the parent Course."""
    user = UserFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    ContentCollectionItemFactory(collection_object=part, child_object=topic, order=0)
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_completing_item_in_multiple_courses_updates_all(mock_site_context):
    """Test that completing an item appearing in multiple courses updates all CourseProgress records."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course2 = CourseFactory()

    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(collection_object=course2, child_object=topic, order=0)

    cp1: CourseProgress = CourseProgressFactory(user=user, course=course)
    cp2: CourseProgress = CourseProgressFactory(user=user, course=course2)

    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    cp1.refresh_from_db()
    cp2.refresh_from_db()
    assert cp1.progress_percentage == 100
    assert cp2.progress_percentage == 100


@pytest.mark.django_db
def test_progress_percentage_zero_when_no_items_complete(mock_site_context):
    """Test that progress_percentage is 0 when no items are complete."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    # Start but don't complete
    TopicProgressFactory(user=user, topic=topic)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_completing_item_creates_course_progress_if_missing(mock_site_context):
    """Test that completing an item creates a CourseProgress record if one doesn't exist."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    # No CourseProgress exists yet
    assert CourseProgress.objects.filter(user=user, course=course).count() == 0

    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    tp.save()

    # CourseProgress should be created with correct percentage
    cp = CourseProgress.objects.get(user=user, course=course)
    assert cp.progress_percentage == 100


# A learner has to pass to complete: a quiz they sat and failed is an attempt, not
# an item they are done with, so it must not lift the completion percentage.


def _course_with_scored_quiz(pass_percentage: int = 80):
    """Course holding one two-option quiz that a learner can pass or fail on demand."""
    course = CourseFactory()
    form = FormFactory(strategy="QUIZ", quiz_pass_percentage=pass_percentage)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    right = QuestionOptionFactory(
        question=question, text="4", value="4", order=0, correct=True
    )
    wrong = QuestionOptionFactory(
        question=question, text="3", value="3", order=1, correct=False
    )
    return course, form, question, right, wrong


def _sit_quiz(user, form, question, option):
    """Complete one attempt at `form`, answering `question` with `option`."""
    attempt: FormProgress = FormProgressFactory(user=user, form=form)
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(option)
    attempt.complete()
    return attempt


@pytest.mark.django_db
def test_failed_quiz_does_not_count_toward_progress_percentage(mock_site_context):
    """A quiz sat and failed leaves the course incomplete."""
    user = UserFactory()
    course, form, question, _right, wrong = _course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    _sit_quiz(user, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_passing_a_retry_makes_a_previously_failed_quiz_count(mock_site_context):
    """Failing then passing leaves the learner complete — the latest sitting decides."""
    user = UserFactory()
    course, form, question, right, wrong = _course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    _sit_quiz(user, form, question, wrong)
    _sit_quiz(user, form, question, right)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_failing_a_retry_uncounts_a_previously_passed_quiz(mock_site_context):
    """Passing then failing a retry takes the completion back — the latest sitting decides."""
    user = UserFactory()
    course, form, question, right, wrong = _course_with_scored_quiz()
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    _sit_quiz(user, form, question, right)
    _sit_quiz(user, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_quiz_with_no_pass_mark_counts_toward_progress_percentage(mock_site_context):
    """No pass mark means no bar to clear, so sitting it is completing it."""
    user = UserFactory()
    course, form, question, _right, wrong = _course_with_scored_quiz(
        pass_percentage=None
    )
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    _sit_quiz(user, form, question, wrong)

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 100


@pytest.mark.django_db
def test_partial_completion_gives_correct_percentage(mock_site_context):
    """Test that partial completion gives correct percentage (e.g. 2 of 4 items = 50%)."""
    user = UserFactory()
    course = CourseFactory()
    topics = [TopicFactory() for _ in range(4)]
    for i, topic in enumerate(topics):
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=i
        )

    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    # Complete 2 of 4 topics
    for topic in topics[:2]:
        tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
        tp.complete_time = timezone.now()
        tp.save()

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 50
