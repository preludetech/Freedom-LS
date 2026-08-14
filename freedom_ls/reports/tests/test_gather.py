"""Tests for freedom_ls.reports.gather.gather_cohort_report_data."""

from __future__ import annotations

import pytest
import time_machine

from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import FormStrategy, QuestionType
from freedom_ls.reports.gather import gather_cohort_report_data
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)

pytestmark = pytest.mark.django_db

# Established empirically: the number of queries gather_cohort_report_data
# issues for one course with one quiz, regardless of how many students or
# questions it has. See test_query_count_is_constant_across_student_and_question_scale.
GATHER_QUERY_BOUND = 12


def _attach(
    collection: object, child: object, order: int = 0
) -> ContentCollectionItemFactory:
    return ContentCollectionItemFactory(
        collection_object=collection, child_object=child, order=order
    )


def _build_cohort_with_quiz(*, student_count: int, question_count: int) -> str:
    """Build a cohort with one course, one quiz, and every student answering every
    question correctly in a single completed attempt."""
    cohort = CohortFactory()
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)

    questions_and_correct_options = []
    for i in range(question_count):
        question = FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=i
        )
        correct_option = QuestionOptionFactory(
            question=question, text="Right", correct=True, order=0
        )
        QuestionOptionFactory(question=question, text="Wrong", correct=False, order=1)
        questions_and_correct_options.append((question, correct_option))

    for _ in range(student_count):
        student = UserFactory()
        CohortMembershipFactory(cohort=cohort, user=student)
        attempt = FormProgressFactory(
            user=student,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": question_count, "max_score": question_count},
        )
        for question, correct_option in questions_and_correct_options:
            answer = QuestionAnswerFactory(form_progress=attempt, question=question)
            answer.selected_options.add(correct_option)

    return str(cohort.id)


def test_gather_returns_expected_shape_for_small_cohort(mock_site_context):
    cohort = CohortFactory()
    student = UserFactory(first_name="Ada", last_name="Lovelace")
    CohortMembershipFactory(cohort=cohort, user=student)

    course = CourseFactory(title="Astronomy")
    CohortCourseRegistrationFactory(cohort=cohort, collection=course, is_active=True)

    topic = TopicFactory(title="Stars")
    _attach(course, topic, order=0)

    quiz = FormFactory(
        title="Astronomy Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=50
    )
    _attach(course, quiz, order=1)
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(
        form_page=page,
        type=QuestionType.CHECKBOXES,
        question="Which are planets?",
        order=0,
    )
    correct_option = QuestionOptionFactory(
        question=question, text="Mars", correct=True, order=0
    )
    QuestionOptionFactory(question=question, text="Sun", correct=False, order=1)

    now = timezone.now()
    TopicProgressFactory(user=student, topic=topic, complete_time=now)
    attempt = FormProgressFactory(
        user=student, form=quiz, completed_time=now, scores={"score": 1, "max_score": 1}
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(correct_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.cohort_name == cohort.name
    assert data.cohort_size == 1
    assert len(data.courses) == 1

    course_section = data.courses[0]
    assert course_section.title == "Astronomy"
    assert course_section.is_active is True
    assert len(course_section.quizzes) == 1
    assert course_section.quizzes[0].title == "Astronomy Quiz"
    assert len(course_section.student_rows) == 1

    row = course_section.student_rows[0]
    assert row.full_name == "Ada Lovelace"
    assert row.completion_percentage == 100

    quiz_cell = row.quiz_cells[quiz.id]
    assert quiz_cell is not None
    assert quiz_cell.passed is True
    assert quiz_cell.attempt_count == 1

    assert len(data.students) == 1
    assert data.students[0].has_any_progress is True


def test_completion_percentage_ignores_stale_course_progress_field(mock_site_context):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic)
    CourseProgressFactory(user=student, course=course, progress_percentage=87)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].student_rows[0]
    assert row.completion_percentage == 0


def test_latest_attempt_score_used_across_three_attempts_at_different_times(
    mock_site_context,
):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    _attach(course, quiz)

    with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
        FormProgressFactory(
            user=student,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
    with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
        FormProgressFactory(
            user=student,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 1},
        )
    with time_machine.travel("2026-01-03T00:00:00Z", tick=False):
        latest = FormProgressFactory(
            user=student,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].student_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.attempt_count == 3
    assert quiz_result.completed_at == latest.completed_time
    assert quiz_result.passed is False


def test_null_quiz_pass_percentage_yields_no_passed_verdict(mock_site_context):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=None)
    _attach(course, quiz)
    FormProgressFactory(
        user=student,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].student_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.passed is None


def test_student_with_no_progress_rows_is_zero_percent_with_no_activity(
    mock_site_context,
):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].student_rows[0]
    detail = data.students[0]
    assert row.completion_percentage == 0
    assert detail.has_any_progress is False


def test_student_with_activity_on_one_course_still_appears_in_other_course(
    mock_site_context,
):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)

    active_course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=active_course)
    topic_done = TopicFactory()
    _attach(active_course, topic_done)
    TopicProgressFactory(user=student, topic=topic_done, complete_time=timezone.now())

    quiet_course = CourseFactory(title="Untouched Course")
    CohortCourseRegistrationFactory(cohort=cohort, collection=quiet_course)
    topic_untouched = TopicFactory()
    _attach(quiet_course, topic_untouched)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    sections_by_title = {section.title: section for section in data.courses}
    quiet_section = sections_by_title["Untouched Course"]
    assert len(quiet_section.student_rows) == 1
    assert quiet_section.student_rows[0].completion_percentage == 0


def test_inactive_registration_produces_course_section_marked_inactive(
    mock_site_context,
):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course, is_active=False)
    topic = TopicFactory()
    _attach(course, topic)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert len(data.courses) == 1
    assert data.courses[0].is_active is False


def test_correct_none_option_selected_counts_as_distractor(mock_site_context):
    cohort = CohortFactory()
    student = UserFactory()
    CohortMembershipFactory(cohort=cohort, user=student)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ)
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(
        form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
    )
    QuestionOptionFactory(question=question, text="Right", correct=True, order=0)
    undecided_option = QuestionOptionFactory(
        question=question, text="Undecided", correct=None, order=1
    )

    attempt = FormProgressFactory(
        user=student,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(undecided_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    confusion_block = data.courses[0].confusions_by_quiz[quiz.id]
    distractor_texts = [
        text
        for confusion in confusion_block.questions
        for text, _ in confusion.distractors
    ]
    assert "Undecided" in distractor_texts


def test_gathering_one_site_excludes_data_from_another_site(mock_site_context):
    other_site = SiteFactory()

    cohort_a = CohortFactory(name="Isolation Cohort A")
    student_a = UserFactory(first_name="Site", last_name="Alpha")
    CohortMembershipFactory(cohort=cohort_a, user=student_a)
    course_a = CourseFactory(title="Site A Course")
    CohortCourseRegistrationFactory(cohort=cohort_a, collection=course_a)
    topic_a = TopicFactory(title="Site A Topic")
    _attach(course_a, topic_a)
    TopicProgressFactory(user=student_a, topic=topic_a, complete_time=timezone.now())

    cohort_b = CohortFactory(name="Isolation Cohort B", site=other_site)
    student_b = UserFactory(first_name="Site", last_name="Beta", site=other_site)
    CohortMembershipFactory(cohort=cohort_b, user=student_b, site=other_site)
    course_b = CourseFactory(title="Site B Course", site=other_site)
    CohortCourseRegistrationFactory(
        cohort=cohort_b, collection=course_b, site=other_site
    )
    topic_b = TopicFactory(title="Site B Topic", site=other_site)
    ContentCollectionItemFactory(
        collection_object=course_b, child_object=topic_b, order=0, site=other_site
    )
    TopicProgressFactory(
        user=student_b, topic=topic_b, complete_time=timezone.now(), site=other_site
    )

    data = gather_cohort_report_data(str(cohort_a.id), mock_site_context.pk)

    assert [student.full_name for student in data.students] == ["Site Alpha"]
    assert [section.title for section in data.courses] == ["Site A Course"]


def test_query_count_is_constant_across_student_and_question_scale(
    mock_site_context, django_assert_num_queries
):
    small_cohort_id = _build_cohort_with_quiz(student_count=2, question_count=2)
    with django_assert_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(small_cohort_id, mock_site_context.pk)

    large_cohort_id = _build_cohort_with_quiz(student_count=6, question_count=6)
    with django_assert_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(large_cohort_id, mock_site_context.pk)
