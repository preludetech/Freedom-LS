from datetime import datetime, timedelta

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.content_engine.models.question_sections import FormQuestionTopic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision.factories import (
    RevisionReviewFactory,
    RevisionScheduleFactory,
)
from freedom_ls.revision.queries import (
    bank_questions,
    bank_sections,
    course_has_revision_questions,
    due_questions,
    last_reviewed_at,
    next_ready_at,
    question_sections,
    ready_count,
    section_first_placement,
    weak_sections,
)
from freedom_ls.revision.tests.helpers import (
    complete_form,
    finish_topic,
    place_form,
    place_part_with_topics,
    place_topic,
    question_testing_part,
    question_testing_topic,
)


@pytest.mark.django_db
def test_completion_with_no_signal_still_banks_the_sections_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, item = place_topic(course)
    question = question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    TopicProgress.objects.bulk_create(
        [
            TopicProgressFactory.build(
                course_progress=record,
                topic=topic,
                collection_item=item,
                complete_time=timezone.now(),
            )
        ]
    )

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_a_question_dropped_from_its_file_is_not_banked(mock_site_context) -> None:
    course = CourseFactory()
    topic, item = place_topic(course)
    question = question_testing_topic(topic)
    FormQuestion.objects.filter(pk=question.pk).update(
        dropped_from_source_at=timezone.now()
    )
    user = UserFactory()
    record = course_progress_record(course, user)
    TopicProgress.objects.bulk_create(
        [
            TopicProgressFactory.build(
                course_progress=record,
                topic=topic,
                collection_item=item,
                complete_time=timezone.now(),
            )
        ]
    )

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_unfinished_topic_banks_nothing(mock_site_context) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course)
    question_testing_topic(topic)
    record = course_progress_record(course, UserFactory())

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_part_with_one_nested_placement_unfinished_banks_nothing(
    mock_site_context,
) -> None:
    course = CourseFactory()
    part, (first, _second) = place_part_with_topics(course, 2)
    question_testing_part(part)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, first)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_part_with_every_nested_placement_finished_banks_its_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    part, (first, second) = place_part_with_topics(course, 2)
    question = question_testing_part(part)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, first)
    finish_topic(record, second)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_part_with_nothing_nested_banks_nothing(mock_site_context) -> None:
    course = CourseFactory()
    part, _topics = place_part_with_topics(course, 0)
    question_testing_part(part)
    record = course_progress_record(course, UserFactory())

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_topic_placed_in_two_courses_gives_each_course_its_own_bank(
    mock_site_context,
) -> None:
    topic = TopicFactory()
    finished_course = CourseFactory()
    finished_course.items.create(child=topic, order=0)
    open_course = CourseFactory()
    open_course.items.create(child=topic, order=0)
    question_testing_topic(topic)
    user = UserFactory()
    finish_topic(course_progress_record(finished_course, user), topic)
    open_record = course_progress_record(open_course, user)

    banked = list(bank_questions(open_record))

    assert banked == []


@pytest.mark.django_db
def test_topic_finished_in_its_own_course_banks_there(mock_site_context) -> None:
    topic = TopicFactory()
    finished_course = CourseFactory()
    finished_course.items.create(child=topic, order=0)
    other_course = CourseFactory()
    other_course.items.create(child=topic, order=0)
    question = question_testing_topic(topic)
    record = course_progress_record(finished_course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_free_text_question_is_not_banked(mock_site_context) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course)
    page = FormPageFactory()
    free_text = FormQuestionFactory(form_page=page, type="free_text")
    FormQuestionTopic.objects.create(question=free_text, topic=topic)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_whose_options_are_all_unmarked_is_not_banked(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course)
    question = FormQuestionFactory(form_page=FormPageFactory(), type="multiple_choice")
    QuestionOptionFactory(question=question, correct=None)
    QuestionOptionFactory(question=question, correct=None)
    FormQuestionTopic.objects.create(question=question, topic=topic)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_naming_one_finished_and_one_unfinished_section_is_not_banked(
    mock_site_context,
) -> None:
    course = CourseFactory()
    finished, _item = place_topic(course, order=0)
    unfinished, _other_item = place_topic(course, order=1)
    question = question_testing_topic(finished)
    FormQuestionTopic.objects.create(question=question, topic=unfinished)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, finished)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_of_a_quiz_placed_in_the_course_is_not_banked_before_the_quiz_is_completed(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course, order=0)
    quiz = place_form(course, order=1)
    question_testing_topic(topic, form=quiz)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_of_a_quiz_placed_in_the_course_is_banked_once_the_quiz_is_completed(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course, order=0)
    quiz = place_form(course, order=1)
    question = question_testing_topic(topic, form=quiz)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)
    complete_form(record, quiz)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_question_of_a_form_placed_in_no_course_needs_no_completion(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _item = place_topic(course)
    bank_form = FormFactory()
    question = question_testing_topic(topic, form=bank_form)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_question_scheduled_for_later_is_not_ready(mock_site_context) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    RevisionScheduleFactory(user=user, question=question, due=now + timedelta(days=3))

    assert ready_count(user, record, now, limit=41) == 0


@pytest.mark.django_db
def test_question_without_a_schedule_and_one_that_is_due_are_ready(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    unscheduled = question_testing_topic(topic)
    due = question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    RevisionScheduleFactory(user=user, question=due, due=now - timedelta(days=1))

    assert {q.pk for q in due_questions(user, record, now)} == {
        unscheduled.pk,
        due.pk,
    }


@pytest.mark.django_db
def test_due_questions_follow_course_order(mock_site_context) -> None:
    course = CourseFactory()
    first, _ = place_topic(course, order=0)
    second, _ = place_topic(course, order=1)
    later_question = question_testing_topic(second)
    earlier_question = question_testing_topic(first)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, first)
    finish_topic(record, second)

    questions = due_questions(user, record, timezone.now())

    assert [q.pk for q in questions] == [earlier_question.pk, later_question.pk]


def _banked_question_with_schedule(
    topic: Topic,
    user: User,
    *,
    now: datetime,
    due: datetime,
    stability: float,
) -> FormQuestion:
    question = question_testing_topic(topic)
    RevisionScheduleFactory(
        user=user,
        question=question,
        state=2,
        stability=stability,
        difficulty=5.0,
        due=due,
        last_review=now - timedelta(days=10),
    )
    return question


@pytest.mark.django_db
def test_due_question_with_lower_retrievability_comes_first(mock_site_context) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    # Same age since review, so the lower stability has decayed further.
    sturdy = _banked_question_with_schedule(
        topic, user, now=now, due=now - timedelta(days=1), stability=50.0
    )
    fading = _banked_question_with_schedule(
        topic, user, now=now, due=now - timedelta(days=1), stability=2.0
    )

    questions = due_questions(user, record, now)

    assert [q.pk for q in questions] == [fading.pk, sturdy.pk]


@pytest.mark.django_db
def test_due_reviewed_questions_come_before_never_reviewed_ones(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    never_reviewed = question_testing_topic(topic)
    reviewed = _banked_question_with_schedule(
        topic, user, now=now, due=now - timedelta(days=1), stability=5.0
    )

    questions = due_questions(user, record, now)

    assert [q.pk for q in questions] == [reviewed.pk, never_reviewed.pk]


@pytest.mark.django_db
def test_never_reviewed_questions_follow_course_order_after_reviewed_ones(
    mock_site_context,
) -> None:
    course = CourseFactory()
    first, _ = place_topic(course, order=0)
    second, _ = place_topic(course, order=1)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, first)
    finish_topic(record, second)
    now = timezone.now()
    later = question_testing_topic(second)
    earlier = question_testing_topic(first)

    questions = due_questions(user, record, now)

    assert [q.pk for q in questions] == [earlier.pk, later.pk]


@pytest.mark.django_db
def test_question_not_yet_due_is_not_in_due_questions(mock_site_context) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    _banked_question_with_schedule(
        topic, user, now=now, due=now + timedelta(days=3), stability=5.0
    )

    assert due_questions(user, record, now) == []


@pytest.mark.django_db
def test_ready_count_stops_at_the_limit(mock_site_context) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    for _ in range(5):
        question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)

    assert ready_count(user, record, timezone.now(), limit=3) == 3


@pytest.mark.django_db
def test_ready_count_runs_one_query(
    mock_site_context, django_assert_max_num_queries
) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    for _ in range(5):
        question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    now = timezone.now()
    bank_questions(record)  # memoises the placed sections on the record

    with django_assert_max_num_queries(1):
        ready_count(user, record, now, limit=41)


@pytest.mark.django_db
def test_part_section_opens_at_its_first_nested_placement(mock_site_context) -> None:
    course = CourseFactory()
    part, topics = place_part_with_topics(course, 2)

    placement = section_first_placement(course, part)

    assert placement is not None
    assert placement.child == topics[0]


@pytest.mark.django_db
def test_topic_section_opens_at_its_own_placement(mock_site_context) -> None:
    course = CourseFactory()
    topic, item = place_topic(course)

    assert section_first_placement(course, topic) == item


@pytest.mark.django_db
def test_question_sections_lists_only_placed_sections_in_course_order(
    mock_site_context,
) -> None:
    course = CourseFactory()
    first, _ = place_topic(course, order=0)
    second, _ = place_topic(course, order=1)
    unplaced = TopicFactory()
    question = question_testing_topic(second)
    for topic in (first, unplaced):
        FormQuestionTopic.objects.create(question=question, topic=topic)
    record = course_progress_record(course, UserFactory())

    sections = question_sections(record, question)

    assert sections == [first, second]


@pytest.mark.django_db
def test_bank_sections_lists_only_sections_with_bank_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    with_questions, _ = place_topic(course, order=0)
    without_questions, _ = place_topic(course, order=1)
    question_testing_topic(with_questions)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, with_questions)
    finish_topic(record, without_questions)

    sections = bank_sections(record)

    assert sections == [with_questions]


@pytest.mark.django_db
def test_bank_sections_are_in_course_order(mock_site_context) -> None:
    course = CourseFactory()
    second, _ = place_topic(course, order=1)
    first, _ = place_topic(course, order=0)
    question_testing_topic(second)
    question_testing_topic(first)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, first)
    finish_topic(record, second)

    sections = bank_sections(record)

    assert sections == [first, second]


@pytest.mark.django_db
def test_due_questions_for_a_section_hold_only_that_sections_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    wanted, _ = place_topic(course, order=0)
    other, _ = place_topic(course, order=1)
    question = question_testing_topic(wanted)
    question_testing_topic(other)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, wanted)
    finish_topic(record, other)

    due = due_questions(user, record, timezone.now(), wanted)

    assert due == [question]


@pytest.mark.django_db
def test_ready_count_for_a_section_counts_only_that_sections_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    wanted, _ = place_topic(course, order=0)
    other, _ = place_topic(course, order=1)
    question_testing_topic(wanted)
    question_testing_topic(other)
    question_testing_topic(other)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, wanted)
    finish_topic(record, other)

    count = ready_count(user, record, timezone.now(), limit=10, section=wanted)

    assert count == 1


def _review_answers(
    user, course, question, *, wrong: int, right: int, ago_hours: int
) -> None:
    """`wrong` wrong reviews, then `right` right ones, the newest `ago_hours` old."""
    now = timezone.now()
    for index in range(wrong + right):
        RevisionReviewFactory(
            user=user,
            course=course,
            question=question,
            was_correct=index >= wrong,
            reviewed_at=now - timedelta(hours=ago_hours + (wrong + right - index)),
        )


def _finished_topic_with_question() -> tuple[
    Course, User, CourseProgress, Topic, FormQuestion
]:
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    user: User = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return course, user, record, topic, question


@pytest.mark.django_db
def test_section_below_the_minimum_sample_is_not_weak(
    mock_site_context, settings
) -> None:
    settings.REVISION_WEAK_WINDOW = 10
    settings.REVISION_WEAK_MIN_REVIEWS = 5
    settings.REVISION_WEAK_MISS_RATE = 0.4
    course, user, record, _topic, question = _finished_topic_with_question()
    _review_answers(user, course, question, wrong=4, right=0, ago_hours=0)

    assert weak_sections(user, record) == set()


@pytest.mark.django_db
def test_section_at_the_miss_rate_is_weak(mock_site_context, settings) -> None:
    settings.REVISION_WEAK_WINDOW = 10
    settings.REVISION_WEAK_MIN_REVIEWS = 5
    settings.REVISION_WEAK_MISS_RATE = 0.4
    course, user, record, topic, question = _finished_topic_with_question()
    _review_answers(user, course, question, wrong=2, right=3, ago_hours=0)

    assert weak_sections(user, record) == {topic.pk}


@pytest.mark.django_db
def test_section_below_the_miss_rate_is_not_weak(mock_site_context, settings) -> None:
    settings.REVISION_WEAK_WINDOW = 10
    settings.REVISION_WEAK_MIN_REVIEWS = 5
    settings.REVISION_WEAK_MISS_RATE = 0.4
    course, user, record, _topic, question = _finished_topic_with_question()
    _review_answers(user, course, question, wrong=1, right=4, ago_hours=0)

    assert weak_sections(user, record) == set()


@pytest.mark.django_db
def test_wrong_review_older_than_the_window_does_not_count(
    mock_site_context, settings
) -> None:
    settings.REVISION_WEAK_WINDOW = 3
    settings.REVISION_WEAK_MIN_REVIEWS = 3
    settings.REVISION_WEAK_MISS_RATE = 0.4
    course, user, record, _topic, question = _finished_topic_with_question()
    _review_answers(user, course, question, wrong=3, right=3, ago_hours=0)

    assert weak_sections(user, record) == set()


@pytest.mark.django_db
def test_next_ready_at_is_the_earliest_due_after_now(mock_site_context) -> None:
    _course, user, record, topic, question = _finished_topic_with_question()
    later = question_testing_topic(topic)
    now = timezone.now()
    soon = now + timedelta(days=2)
    RevisionScheduleFactory(user=user, question=question, due=soon)
    RevisionScheduleFactory(user=user, question=later, due=now + timedelta(days=9))

    assert next_ready_at(user, record, now) == soon


@pytest.mark.django_db
def test_next_ready_at_ignores_a_schedule_already_due(mock_site_context) -> None:
    _, user, record, _topic, question = _finished_topic_with_question()
    now = timezone.now()
    RevisionScheduleFactory(user=user, question=question, due=now - timedelta(days=1))

    assert next_ready_at(user, record, now) is None


@pytest.mark.django_db
def test_course_has_revision_questions_before_any_section_is_finished(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    question_testing_topic(topic)

    assert course_has_revision_questions(course) is True


@pytest.mark.django_db
def test_course_without_questions_naming_its_sections_has_none(
    mock_site_context,
) -> None:
    course = CourseFactory()
    place_topic(course)
    question_testing_topic(TopicFactory())

    assert course_has_revision_questions(course) is False


@pytest.mark.django_db
def test_last_reviewed_at_is_the_latest_review_in_the_course(mock_site_context) -> None:
    course, user, _record, _topic, question = _finished_topic_with_question()
    now = timezone.now()
    RevisionReviewFactory(
        user=user, course=course, question=question, reviewed_at=now - timedelta(days=5)
    )
    RevisionReviewFactory(
        user=user, course=course, question=question, reviewed_at=now - timedelta(days=2)
    )
    RevisionReviewFactory(user=user, question=question, reviewed_at=now)

    assert last_reviewed_at(user, course) == now - timedelta(days=2)


@pytest.mark.django_db
def test_last_reviewed_at_is_none_without_reviews(mock_site_context) -> None:
    course, user, *_ = _finished_topic_with_question()

    assert last_reviewed_at(user, course) is None
