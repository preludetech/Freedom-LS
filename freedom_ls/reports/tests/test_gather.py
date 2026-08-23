"""Tests for freedom_ls.reports.gather.gather_cohort_report_data."""

from __future__ import annotations

from uuid import UUID

import pytest
import time_machine

from django.test import override_settings
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
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.gather import gather_cohort_report_data

pytestmark = pytest.mark.django_db

# Established empirically: the number of queries gather_cohort_report_data
# issues for one course with one quiz, regardless of how many learners or
# questions it has. See test_query_count_is_constant_across_learner_and_question_scale.
GATHER_QUERY_BOUND = 12


def _attach(
    collection: object, child: object, order: int = 0
) -> ContentCollectionItemFactory:
    return ContentCollectionItemFactory(
        collection_object=collection, child_object=child, order=order
    )


def _build_cohort_with_quiz(*, learner_count: int, question_count: int) -> str:
    """Build a cohort with one course, one quiz, and every learner answering every
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

    for _ in range(learner_count):
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        attempt = FormProgressFactory(
            user=learner,
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
    learner = UserFactory(first_name="Ada", last_name="Lovelace")
    CohortMembershipFactory(cohort=cohort, learner__user=learner)

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
    TopicProgressFactory(user=learner, topic=topic, complete_time=now)
    attempt = FormProgressFactory(
        user=learner, form=quiz, completed_time=now, scores={"score": 1, "max_score": 1}
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
    assert len(course_section.learner_rows) == 1

    row = course_section.learner_rows[0]
    assert row.full_name == "Ada Lovelace"
    assert row.completion_percentage == 100

    quiz_cell = row.quiz_cells[quiz.id]
    assert quiz_cell is not None
    assert quiz_cell.passed is True
    assert quiz_cell.attempt_count == 1

    assert len(data.learners) == 1
    assert data.learners[0].has_any_progress is True


def test_completion_percentage_ignores_stale_course_progress_field(mock_site_context):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic)
    CourseProgressFactory(user=learner, course=course, progress_percentage=87)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].learner_rows[0]
    assert row.completion_percentage == 0


def _cohort_with_two_question_quiz(*, pass_percentage: int | None = 50):
    """Cohort with one course holding a two-question quiz. Returns the pieces a test
    needs to have a learner sit it."""
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(
        title="Two Question Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=pass_percentage,
    )
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)

    questions = []
    for i in range(2):
        question = FormQuestionFactory(
            form_page=page,
            type=QuestionType.MULTIPLE_CHOICE,
            question=f"Question {i + 1}?",
            order=i,
        )
        correct_option = QuestionOptionFactory(
            question=question, text="Right", correct=True, order=0
        )
        QuestionOptionFactory(question=question, text="Wrong", correct=False, order=1)
        questions.append((question, correct_option))

    return cohort, learner, quiz, questions


def test_a_question_left_blank_reaches_the_wrong_answer_detail(mock_site_context):
    """A blank question stores no answer row, but the learner still got it wrong."""
    cohort, learner, quiz, questions = _cohort_with_two_question_quiz()
    (answered, correct_option), (blank, _) = questions
    attempt = FormProgressFactory(
        user=learner,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=answered)
    answer.selected_options.add(correct_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    wrong = data.learners[0].wrong_answers[0].answers
    assert [entry.question_text for entry in wrong] == [blank.question]
    assert wrong[0].selected_options == []


def test_an_option_chosen_on_more_than_one_sitting_is_counted_once_per_sitting(
    mock_site_context,
):
    """Retakes are what make the count worth printing: three wrong sittings on one
    question read the same until you can see two of them were the same choice."""
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ)
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(
        form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
    )
    QuestionOptionFactory(question=question, text="Mars", correct=True, order=0)
    venus = QuestionOptionFactory(
        question=question, text="Venus", correct=False, order=1
    )
    mercury = QuestionOptionFactory(
        question=question, text="Mercury", correct=False, order=2
    )

    for option in (venus, mercury, venus):
        attempt = FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
        QuestionAnswerFactory(
            form_progress=attempt, question=question
        ).selected_options.add(option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    answer = data.learners[0].wrong_answers[0].answers[0]
    assert answer.times_wrong == 3
    assert {option.text: option.count for option in answer.selected_options} == {
        "Venus": 2,
        "Mercury": 1,
    }


def test_a_correct_tick_inside_a_wrong_multi_select_answer_is_marked_correct(
    mock_site_context,
):
    """Ticking both right options plus a distractor scores the question wrong.

    The learner's two right ticks still have to read as right, or the report
    contradicts its own correct-answer column on the same row.
    """
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ)
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(
        form_page=page, type=QuestionType.CHECKBOXES, order=0
    )
    option_a = QuestionOptionFactory(question=question, text="A", correct=True, order=0)
    option_b = QuestionOptionFactory(question=question, text="B", correct=True, order=1)
    option_c = QuestionOptionFactory(
        question=question, text="C", correct=False, order=2
    )
    attempt = FormProgressFactory(
        user=learner,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.set([option_a, option_b, option_c])

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    wrong_answer = data.learners[0].wrong_answers[0].answers[0]
    assert {
        option.text: option.correct for option in wrong_answer.selected_options
    } == {"A": True, "B": True, "C": False}


def test_confusion_denominator_counts_learners_who_left_a_question_blank(
    mock_site_context,
):
    """A learner who sat the quiz and skipped the question is a respondent who got it wrong."""
    cohort, learner, quiz, questions = _cohort_with_two_question_quiz()
    (answered, correct_option), (blank, _) = questions
    attempt = FormProgressFactory(
        user=learner,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=answered)
    answer.selected_options.add(correct_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    confusion = data.courses[0].confusions_by_quiz[quiz.id].questions[0]
    assert confusion.question_text == blank.question
    assert confusion.respondent_count == 1
    assert confusion.wrong_count == 1


def test_failed_quiz_does_not_count_toward_report_completion_percentage(
    mock_site_context,
):
    """The report's completion figures follow the same pass-to-complete rule as the course."""
    cohort, learner, quiz, _questions = _cohort_with_two_question_quiz(
        pass_percentage=80
    )
    FormProgressFactory(
        user=learner,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 2},
    )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.courses[0].learner_rows[0].completion_percentage == 0


def test_passing_a_retry_restores_the_report_completion_percentage(mock_site_context):
    """The latest completed sitting decides, so a passing retry counts the quiz as done."""
    cohort, learner, quiz, _questions = _cohort_with_two_question_quiz(
        pass_percentage=80
    )
    with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 2},
        )
    with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.courses[0].learner_rows[0].completion_percentage == 100


def test_latest_attempt_score_used_across_three_attempts_at_different_times(
    mock_site_context,
):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    _attach(course, quiz)

    with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
    with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 1},
        )
    with time_machine.travel("2026-01-03T00:00:00Z", tick=False):
        latest = FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].learner_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.attempt_count == 3
    assert quiz_result.completed_at == latest.completed_time
    assert quiz_result.passed is False


def test_null_quiz_pass_percentage_yields_no_passed_verdict(mock_site_context):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=None)
    _attach(course, quiz)
    FormProgressFactory(
        user=learner,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].learner_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.passed is None


def test_learner_with_no_progress_rows_is_zero_percent_with_no_activity(
    mock_site_context,
):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].learner_rows[0]
    detail = data.learners[0]
    assert row.completion_percentage == 0
    assert detail.has_any_progress is False
    assert detail.has_reportable_activity is False


def test_learner_who_opened_an_item_without_completing_it_has_nothing_to_report(
    mock_site_context,
):
    """The two flags disagree for this learner, and the detail section relies on it.

    Opening a topic writes a TopicProgress row, so `has_any_progress` is True and
    the no-recorded-activity at-risk rule stays silent -- but there is no
    completion, quiz result or wrong answer to print.
    """
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic)
    TopicProgressFactory(user=learner, topic=topic, complete_time=None)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    detail = data.learners[0]
    assert detail.completion_percentage == 0
    assert detail.has_any_progress is True
    assert detail.has_reportable_activity is False


def test_learner_with_activity_on_one_course_still_appears_in_other_course(
    mock_site_context,
):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)

    active_course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=active_course)
    topic_done = TopicFactory()
    _attach(active_course, topic_done)
    TopicProgressFactory(user=learner, topic=topic_done, complete_time=timezone.now())

    quiet_course = CourseFactory(title="Untouched Course")
    CohortCourseRegistrationFactory(cohort=cohort, collection=quiet_course)
    topic_untouched = TopicFactory()
    _attach(quiet_course, topic_untouched)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    sections_by_title = {section.title: section for section in data.courses}
    quiet_section = sections_by_title["Untouched Course"]
    assert len(quiet_section.learner_rows) == 1
    assert quiet_section.learner_rows[0].completion_percentage == 0


def test_inactive_registration_produces_course_section_marked_inactive(
    mock_site_context,
):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course, is_active=False)
    topic = TopicFactory()
    _attach(course, topic)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert len(data.courses) == 1
    assert data.courses[0].is_active is False


def test_correct_none_option_selected_counts_as_distractor(mock_site_context):
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
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
        user=learner,
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


def _build_quiz_with_wrong_answers(
    *, respondent_count: int, wrong_count: int
) -> tuple[str, UUID]:
    """One quiz, one question; the first `wrong_count` first-attempt learners answer
    wrong, the rest answer correctly. Returns (cohort_id, quiz_id)."""
    cohort = CohortFactory()
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ)
    _attach(course, quiz)
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(
        form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
    )
    correct_option = QuestionOptionFactory(
        question=question, text="Right", correct=True, order=0
    )
    wrong_option = QuestionOptionFactory(
        question=question, text="Wrong", correct=False, order=1
    )

    for i in range(respondent_count):
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        attempt = FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
        answer = QuestionAnswerFactory(form_progress=attempt, question=question)
        answer.selected_options.add(wrong_option if i < wrong_count else correct_option)

    return str(cohort.id), quiz.id


def test_confusion_shows_plain_counts_below_respondent_threshold(mock_site_context):
    cohort_id, quiz_id = _build_quiz_with_wrong_answers(
        respondent_count=9, wrong_count=3
    )

    data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

    confusion = data.courses[0].confusions_by_quiz[quiz_id].questions[0]
    assert confusion.respondent_count == 9
    assert confusion.wrong_count == 3
    assert confusion.show_percentage is False
    assert confusion.wrong_percentage is None


def test_confusion_shows_percentage_at_respondent_threshold(mock_site_context):
    cohort_id, quiz_id = _build_quiz_with_wrong_answers(
        respondent_count=10, wrong_count=3
    )

    data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

    confusion = data.courses[0].confusions_by_quiz[quiz_id].questions[0]
    assert confusion.respondent_count == 10
    assert confusion.wrong_count == 3
    assert confusion.show_percentage is True
    assert confusion.wrong_percentage == 30


def test_gathering_one_site_excludes_data_from_another_site(mock_site_context):
    other_site = SiteFactory()

    cohort_a = CohortFactory(name="Isolation Cohort A")
    learner_a = UserFactory(first_name="Site", last_name="Alpha")
    CohortMembershipFactory(cohort=cohort_a, learner__user=learner_a)
    course_a = CourseFactory(title="Site A Course")
    CohortCourseRegistrationFactory(cohort=cohort_a, collection=course_a)
    topic_a = TopicFactory(title="Site A Topic")
    _attach(course_a, topic_a)
    TopicProgressFactory(user=learner_a, topic=topic_a, complete_time=timezone.now())

    # organisation too: CohortFactory's SubFactory does not inherit an
    # explicit site=, so without this the cohort would sit on site B while its
    # organisation sat on site A.
    cohort_b = CohortFactory(
        name="Isolation Cohort B",
        site=other_site,
        organisation=OrganisationFactory(site=other_site),
    )
    learner_b = UserFactory(first_name="Site", last_name="Beta", site=other_site)
    CohortMembershipFactory(cohort=cohort_b, learner__user=learner_b, site=other_site)
    course_b = CourseFactory(title="Site B Course", site=other_site)
    CohortCourseRegistrationFactory(
        cohort=cohort_b, collection=course_b, site=other_site
    )
    topic_b = TopicFactory(title="Site B Topic", site=other_site)
    ContentCollectionItemFactory(
        collection_object=course_b, child_object=topic_b, order=0, site=other_site
    )
    TopicProgressFactory(
        user=learner_b, topic=topic_b, complete_time=timezone.now(), site=other_site
    )

    data = gather_cohort_report_data(str(cohort_a.id), mock_site_context.pk)

    assert [learner.full_name for learner in data.learners] == ["Site Alpha"]
    assert [section.title for section in data.courses] == ["Site A Course"]


def _build_cohort_with_quiz_titles(titles: list[str]) -> str:
    """One cohort, one learner, one course carrying a quiz per title, in order."""
    cohort = CohortFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    for order, title in enumerate(titles):
        quiz = FormFactory(title=title, strategy=FormStrategy.QUIZ)
        _attach(course, quiz, order=order)
    return str(cohort.id)


class TestSummaryTableSplitting:
    @override_settings(REPORTS_MAX_QUIZ_COLUMNS=10)
    def test_a_ten_column_budget_splits_an_eleven_quiz_course(self, mock_site_context):
        """Ten is the shipped budget, measured on rendered A4 landscape pages: at
        eleven quiz columns the "Last item completed" column is squeezed below the
        width one item title needs and its text runs into "When".
        """
        cohort_id = _build_cohort_with_quiz_titles(
            [f"Course Quiz {index:02d}" for index in range(1, 12)]
        )

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        tables = data.courses[0].summary_tables
        assert [len(table.quizzes) for table in tables] == [10, 1]

    @override_settings(REPORTS_MAX_QUIZ_COLUMNS=11)
    def test_every_quiz_appears_in_exactly_one_summary_table(self, mock_site_context):
        cohort_id = _build_cohort_with_quiz_titles(
            [f"Course Quiz {index:02d}" for index in range(1, 17)]
        )

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        section = data.courses[0]
        placed = [
            quiz.form_id for table in section.summary_tables for quiz in table.quizzes
        ]
        assert placed == [quiz.form_id for quiz in section.quizzes]
        assert len(placed) == len(set(placed))

    def test_course_with_no_quizzes_still_yields_one_table(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        _attach(course, TopicFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        tables = data.courses[0].summary_tables
        assert len(tables) == 1
        assert tables[0].quizzes == []
        assert len(tables[0].rows) == 1


class TestQuizAbbreviations:
    def test_abbreviations_reach_the_columns_in_course_order(self, mock_site_context):
        """That the abbreviations are wired to the columns at all, and per course.

        How a single title is shortened is settled in test_gather_helpers.py;
        what only the whole gather can show is that the result lands on
        CourseSection.quizzes, in the order the course lists its quizzes.
        """
        cohort_id = _build_cohort_with_quiz_titles(
            ["Voltage Quiz 01", "Hydrology Quiz 12", "Ratios Quiz 10"]
        )

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        abbreviations = [quiz.abbreviation for quiz in data.courses[0].quizzes]
        assert abbreviations == ["VQ01", "HQ12", "RQ10"]


class TestLearnerOrdering:
    def _build_cohort_with_surnames(self, surnames: list[str]) -> str:
        cohort = CohortFactory()
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        _attach(course, TopicFactory())
        for surname in surnames:
            CohortMembershipFactory(
                cohort=cohort,
                learner__user=UserFactory(first_name="Sam", last_name=surname),
            )
        return str(cohort.id)

    def test_summary_rows_are_alphabetical_by_surname(self, mock_site_context):
        cohort_id = self._build_cohort_with_surnames(
            ["Okonkwo", "Abara", "Nakamura", "Bergstrom"]
        )

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        names = [row.full_name for row in data.courses[0].learner_rows]
        assert names == [
            "Sam Abara",
            "Sam Bergstrom",
            "Sam Nakamura",
            "Sam Okonkwo",
        ]

    def test_summary_row_order_matches_learner_detail_order(self, mock_site_context):
        cohort_id = self._build_cohort_with_surnames(
            ["Okonkwo", "Abara", "Nakamura", "Bergstrom"]
        )

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        assert [row.user_id for row in data.courses[0].learner_rows] == [
            detail.user_id for detail in data.learners
        ]

    def test_summary_table_rows_follow_the_same_order(self, mock_site_context):
        cohort_id = self._build_cohort_with_surnames(["Okonkwo", "Abara"])

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        table = data.courses[0].summary_tables[0]
        assert [row.user_id for row in table.rows] == [
            detail.user_id for detail in data.learners
        ]


class TestRequestedByName:
    def test_requested_by_name_reaches_the_report_data(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())

        data = gather_cohort_report_data(
            str(cohort.id), mock_site_context.pk, requested_by_name="Ada Lovelace"
        )

        assert data.requested_by_name == "Ada Lovelace"

    def test_requested_by_name_defaults_to_empty(self, mock_site_context):
        cohort = CohortFactory()

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.requested_by_name == ""


class TestWrongAnswersCarryQuizTitles:
    def test_wrong_answers_are_a_list_of_titled_quizzes_in_course_order(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)

        for order, title in enumerate(["Voltage Quiz 01", "Erosion Quiz 02"]):
            quiz = FormFactory(title=title, strategy=FormStrategy.QUIZ)
            _attach(course, quiz, order=order)
            page = FormPageFactory(form=quiz, order=0)
            question = FormQuestionFactory(
                form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
            )
            QuestionOptionFactory(
                question=question, text="Right", correct=True, order=0
            )
            wrong_option = QuestionOptionFactory(
                question=question, text="Wrong", correct=False, order=1
            )
            attempt = FormProgressFactory(
                user=learner,
                form=quiz,
                completed_time=timezone.now(),
                scores={"score": 0, "max_score": 1},
            )
            answer = QuestionAnswerFactory(form_progress=attempt, question=question)
            answer.selected_options.add(wrong_option)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        detail = data.learners[0]
        assert [block.title for block in detail.wrong_answers] == [
            "Voltage Quiz 01",
            "Erosion Quiz 02",
        ]
        assert all(block.answers for block in detail.wrong_answers)

    def test_learner_without_wrong_answers_has_an_empty_list(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        _attach(course, TopicFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.learners[0].wrong_answers == []


def test_query_count_is_constant_across_learner_and_question_scale(
    mock_site_context, django_assert_num_queries
):
    small_cohort_id = _build_cohort_with_quiz(learner_count=2, question_count=2)
    with django_assert_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(small_cohort_id, mock_site_context.pk)

    large_cohort_id = _build_cohort_with_quiz(learner_count=6, question_count=6)
    with django_assert_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(large_cohort_id, mock_site_context.pk)


class TestQuizAttempts:
    def test_attempts_are_chronological_and_agree_with_the_latest_figures(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)

        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            FormProgressFactory(
                user=learner,
                form=quiz,
                completed_time=timezone.now(),
                scores={"score": 0, "max_score": 2},
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            FormProgressFactory(
                user=learner,
                form=quiz,
                completed_time=timezone.now(),
                scores={"score": 1, "max_score": 2},
            )
        with time_machine.travel("2026-01-03T00:00:00Z", tick=False):
            FormProgressFactory(
                user=learner,
                form=quiz,
                completed_time=timezone.now(),
                scores={"score": 2, "max_score": 2},
            )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.learners[0].quiz_results[0]
        assert [attempt.attempt_number for attempt in result.attempts] == [1, 2, 3]
        assert [attempt.percentage for attempt in result.attempts] == [0, 50, 100]
        # The two views of the same rows cannot disagree.
        assert len(result.attempts) == result.attempt_count
        assert result.attempts[-1].percentage == result.latest_percentage
        assert result.attempts[-1].passed == result.passed
        assert result.attempts[-1].completed_at == result.completed_at

    def test_an_incomplete_sitting_is_not_an_attempt(self, mock_site_context):
        cohort = CohortFactory()
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 1},
        )
        FormProgressFactory(user=learner, form=quiz, completed_time=None, scores={})

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.learners[0].quiz_results[0]
        assert len(result.attempts) == 1
        assert result.attempt_count == 1


class TestFlagSeverity:
    def test_rules_carry_their_declared_severity(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        _attach(course, TopicFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        flags = {flag.rule_id: flag.severity for flag in data.learners[0].flags}
        assert flags["no_activity"] == "error"


class TestOrganisationName:
    def test_the_cohorts_organisation_is_carried_onto_the_report(
        self, mock_site_context
    ):
        cohort = CohortFactory(
            organisation=OrganisationFactory(name="Northside College")
        )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation_name == "Northside College"


class TestSiteName:
    def test_header_title_is_preferred_over_the_site_name(self, mock_site_context):
        cohort = CohortFactory()

        with override_settings(HEADER_TITLE="Bright Academy"):
            data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.site_name == "Bright Academy"

    def test_falls_back_to_the_site_row_when_no_header_title_is_set(
        self, mock_site_context
    ):
        cohort = CohortFactory()

        with override_settings(HEADER_TITLE=None):
            data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.site_name == mock_site_context.name


@pytest.fixture
def cohort_with_a_quiz_and_a_survey(mock_site_context):
    """One course holding a quiz and a survey, both completed by the same learner.

    A survey's questions never reach the quiz analysis, so its answers are the
    case that distinguishes "every answer in the cohort" from "every quiz answer".
    """
    cohort = CohortFactory()
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    quiz = FormFactory(
        title="Astronomy Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=50
    )
    _attach(course, quiz, order=0)
    quiz_page = FormPageFactory(form=quiz, order=0)
    quiz_question = FormQuestionFactory(
        form_page=quiz_page,
        type=QuestionType.MULTIPLE_CHOICE,
        question="Which planet is red?",
        order=0,
    )
    QuestionOptionFactory(question=quiz_question, text="Mars", correct=True, order=0)
    distractor = QuestionOptionFactory(
        question=quiz_question, text="Venus", correct=False, order=1
    )

    survey = FormFactory(
        title="Confidence Survey", strategy=FormStrategy.CATEGORY_VALUE_SUM
    )
    _attach(course, survey, order=1)
    survey_page = FormPageFactory(form=survey, order=0)
    survey_question = FormQuestionFactory(
        form_page=survey_page,
        type=QuestionType.MULTIPLE_CHOICE,
        question="How confident do you feel?",
        order=0,
    )
    survey_option = QuestionOptionFactory(
        question=survey_question, text="Very confident", correct=None, order=0
    )

    now = timezone.now()
    quiz_attempt = FormProgressFactory(
        user=learner, form=quiz, completed_time=now, scores={"score": 0, "max_score": 1}
    )
    QuestionAnswerFactory(
        form_progress=quiz_attempt, question=quiz_question
    ).selected_options.add(distractor)

    survey_attempt = FormProgressFactory(
        user=learner, form=survey, completed_time=now, scores={"Confidence": 3}
    )
    QuestionAnswerFactory(
        form_progress=survey_attempt, question=survey_question
    ).selected_options.add(survey_option)

    return cohort


class TestSurveysAlongsideQuizzes:
    def test_a_completed_survey_does_not_stop_the_report_being_gathered(
        self, cohort_with_a_quiz_and_a_survey, mock_site_context
    ):
        data = gather_cohort_report_data(
            str(cohort_with_a_quiz_and_a_survey.id), mock_site_context.pk
        )

        assert [quiz.title for quiz in data.courses[0].quizzes] == ["Astronomy Quiz"]

    def test_a_survey_question_is_absent_from_the_confusion_tally(
        self, cohort_with_a_quiz_and_a_survey, mock_site_context
    ):
        data = gather_cohort_report_data(
            str(cohort_with_a_quiz_and_a_survey.id), mock_site_context.pk
        )

        confusions = data.courses[0].confusions_by_quiz
        assert [
            question.question_text
            for block in confusions.values()
            for question in block.questions
        ] == ["Which planet is red?"]

    def test_a_survey_answer_is_never_reported_as_a_wrong_answer(
        self, cohort_with_a_quiz_and_a_survey, mock_site_context
    ):
        data = gather_cohort_report_data(
            str(cohort_with_a_quiz_and_a_survey.id), mock_site_context.pk
        )

        wrong_answers = data.learners[0].wrong_answers
        assert [block.title for block in wrong_answers] == ["Astronomy Quiz"]

    def test_a_completed_survey_counts_toward_course_completion(
        self, cohort_with_a_quiz_and_a_survey, mock_site_context
    ):
        """The survey has no pass mark, so completing it is enough — unlike the quiz
        this learner failed, which is why the count is 1 of 2 rather than 2."""
        data = gather_cohort_report_data(
            str(cohort_with_a_quiz_and_a_survey.id), mock_site_context.pk
        )

        row = data.courses[0].learner_rows[0]
        assert row.completed_item_count == 1
        assert row.total_item_count == 2


class TestQuizWithNoQuestions:
    def test_a_completed_sitting_reports_no_percentage_or_verdict(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)
        FormPageFactory(form=quiz, order=0)
        FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 0},
        )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.learners[0].quiz_results[0]
        assert result.latest_percentage is None
        assert result.passed is None
