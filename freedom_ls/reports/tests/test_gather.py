"""Tests for freedom_ls.reports.gather.gather_cohort_report_data."""

from __future__ import annotations

from uuid import UUID

import pytest
import time_machine

from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy, QuestionType
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.reports.gather import (
    FOOTER_COHORT_MAX_CHARS,
    FOOTER_LINE_MAX_CHARS,
    FOOTER_ORGANISATION_MAX_CHARS,
    WORDMARK_CONDENSED_MAX_CHARS,
    WORDMARK_FULL_MAX_CHARS,
    CompletionStats,
    QuizTallies,
    _abbreviate_quiz_title,
    _build_attention_list,
    _build_learner_row,
    _build_quiz_columns,
    _build_summary_tables,
    _chunk_quiz_columns,
    _completed_items,
    _completion_counts,
    _completion_percentage,
    _completion_statistics,
    _evaluate_at_risk_flags,
    _latest_completion,
    _quiz_result_for,
    _score_attempt,
    _truncate_to_budget,
    _unique_abbreviations,
    _wordmark_size_class,
    build_confusion_block,
    build_wrong_answers_by_learner_quiz,
    gather_cohort_report_data,
    tally_quiz_answers,
)
from freedom_ls.reports.indexes import (
    QuestionIndex,
    SatQuestions,
    build_question_index,
    fold_form_progress_rows,
    fold_topic_progress_rows,
    index_distractors,
    merge_progress_indexes,
)
from freedom_ls.reports.report_data import (
    AtRiskFlag,
    LearnerDetail,
    LearnerRow,
    QuizColumn,
    SelectedOption,
)
from freedom_ls.reports.tests.gather_input_builders import (
    JAN_1,
    JAN_2,
    JAN_3,
    LEARNER_ID,
    OTHER_LEARNER_ID,
    a_catalogue,
    a_learner,
    a_page,
    a_progress_index,
    a_question,
    a_quiz,
    a_roster,
    a_survey,
    a_topic,
    an_attempt,
    an_option,
    attempted,
)
from freedom_ls.reports.tests.helpers import form_progress, topic_progress

# Organisation.name allows 150 characters, and this is one of exactly that
# length, so both the wordmark and the footer budget have to cut it.
LONG_ORG_NAME = (
    "Northside College of Advanced Hydrology and Environmental Science " * 3
)[:150]

# Longer than the footer's second line holds, so the budget has to cut it.
LONG_COHORT_NAME = "Autumn Intake for Advanced Environmental Fieldwork and Survey"

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


def _one_learner_cohort(
    course: Course, *, user: User | None = None, is_active: bool = True
) -> tuple[Cohort, CourseProgress]:
    """A one-member cohort registered for `course`, and that member's record.

    Everything the report reads hangs off the record rather than off the
    person, so a test that wants progress has to have one.
    """
    cohort: Cohort = CohortFactory()
    member = user if user is not None else UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=member)
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    # The record is resolved while the registration is active, because only an
    # active grant resolves; the requested state is applied afterwards.
    record = course_progress_record(course, member)
    CohortCourseRegistration.objects.filter(pk=registration.pk).update(
        is_active=is_active
    )
    return cohort, record


def _build_cohort_with_quiz(*, learner_count: int, question_count: int) -> str:
    """Build a cohort with one course, one quiz, and every learner answering every
    question correctly in a single completed attempt."""
    cohort = CohortFactory()
    course = CourseFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
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
        record = course_progress_record(registration.course, learner)
        attempt = form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": question_count, "max_score": question_count},
        )
        for question, correct_option in questions_and_correct_options:
            answer = QuestionAnswerFactory(form_progress=attempt, question=question)
            answer.selected_options.add(correct_option)

    return str(cohort.id)


@pytest.mark.django_db
def test_gather_returns_expected_shape_for_small_cohort(mock_site_context):
    course = CourseFactory(title="Astronomy")

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

    cohort, record = _one_learner_cohort(
        course, user=UserFactory(first_name="Ada", last_name="Lovelace")
    )
    now = timezone.now()
    topic_progress(record, topic, complete_time=now)
    attempt = form_progress(
        record, quiz, completed_time=now, scores={"score": 1, "max_score": 1}
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


@pytest.mark.django_db
def test_summary_rows_are_keyed_on_the_learner_not_the_user(mock_site_context):
    """The id the report emits is the Learner's, which is what the anchors use."""
    course = CourseFactory()
    _attach(course, TopicFactory())
    cohort, record = _one_learner_cohort(course)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.courses[0].learner_rows[0].learner_id == record.learner_id
    assert data.learners[0].learner_id == record.learner_id


@pytest.mark.django_db
def test_completion_percentage_ignores_stale_course_progress_field(mock_site_context):
    course = CourseFactory()
    topic = TopicFactory()
    _attach(course, topic)
    cohort, record = _one_learner_cohort(course)
    record.progress_percentage = 87
    record.save(update_fields=["progress_percentage"])

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].learner_rows[0]
    assert row.completion_percentage == 0


def _cohort_with_two_question_quiz(*, pass_percentage: int | None = 50):
    """Cohort with one course holding a two-question quiz. Returns the pieces a test
    needs to have a learner sit it."""
    course = CourseFactory()
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

    cohort, record = _one_learner_cohort(course)
    return cohort, record, quiz, questions


@pytest.mark.django_db
def test_a_question_left_blank_reaches_the_wrong_answer_detail(mock_site_context):
    """A blank question stores no answer row, but the learner still got it wrong."""
    cohort, record, quiz, questions = _cohort_with_two_question_quiz()
    (answered, correct_option), (blank, _) = questions
    attempt = form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 1, "max_score": 2}
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=answered)
    answer.selected_options.add(correct_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    wrong = data.learners[0].wrong_answers[0].answers
    assert [entry.question_text for entry in wrong] == [blank.question]
    assert wrong[0].selected_options == []


@pytest.mark.django_db
def test_an_option_chosen_on_more_than_one_sitting_is_counted_once_per_sitting(
    mock_site_context,
):
    """Retakes are what make the count worth printing: three wrong sittings on one
    question read the same until you can see two of them were the same choice."""
    course = CourseFactory()
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
    cohort, record = _one_learner_cohort(course)

    for option in (venus, mercury, venus):
        attempt = form_progress(
            record,
            quiz,
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


@pytest.mark.django_db
def test_a_correct_tick_inside_a_wrong_multi_select_answer_is_marked_correct(
    mock_site_context,
):
    """Ticking both right options plus a distractor scores the question wrong.

    The learner's two right ticks still have to read as right, or the report
    contradicts its own correct-answer column on the same row.
    """
    course = CourseFactory()
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
    cohort, record = _one_learner_cohort(course)
    attempt = form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 0, "max_score": 1}
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.set([option_a, option_b, option_c])

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    wrong_answer = data.learners[0].wrong_answers[0].answers[0]
    assert {
        option.text: option.correct for option in wrong_answer.selected_options
    } == {"A": True, "B": True, "C": False}


@pytest.mark.django_db
def test_confusion_denominator_counts_learners_who_left_a_question_blank(
    mock_site_context,
):
    """A learner who sat the quiz and skipped the question is a respondent who got it wrong."""
    cohort, record, quiz, questions = _cohort_with_two_question_quiz()
    (answered, correct_option), (blank, _) = questions
    attempt = form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 1, "max_score": 2}
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=answered)
    answer.selected_options.add(correct_option)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    confusion = data.courses[0].confusions_by_quiz[quiz.id].questions[0]
    assert confusion.question_text == blank.question
    assert confusion.respondent_count == 1
    assert confusion.wrong_count == 1


@pytest.mark.django_db
def test_failed_quiz_does_not_count_toward_report_completion_percentage(
    mock_site_context,
):
    """The report's completion figures follow the same pass-to-complete rule as the course."""
    cohort, record, quiz, _questions = _cohort_with_two_question_quiz(
        pass_percentage=80
    )
    form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 0, "max_score": 2}
    )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.courses[0].learner_rows[0].completion_percentage == 0


@pytest.mark.django_db
def test_passing_a_retry_restores_the_report_completion_percentage(mock_site_context):
    """The latest completed sitting decides, so a passing retry counts the quiz as done."""
    cohort, record, quiz, _questions = _cohort_with_two_question_quiz(
        pass_percentage=80
    )
    with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 2},
        )
    with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert data.courses[0].learner_rows[0].completion_percentage == 100


@pytest.mark.django_db
def test_latest_attempt_score_used_across_three_attempts_at_different_times(
    mock_site_context,
):
    course = CourseFactory()
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    _attach(course, quiz)
    cohort, record = _one_learner_cohort(course)

    with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
    with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 1},
        )
    with time_machine.travel("2026-01-03T00:00:00Z", tick=False):
        latest = form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].learner_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.attempt_count == 3
    assert quiz_result.completed_at == latest.completed_time
    assert quiz_result.passed is False


@pytest.mark.django_db
def test_null_quiz_pass_percentage_yields_no_passed_verdict(mock_site_context):
    course = CourseFactory()
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=None)
    _attach(course, quiz)
    cohort, record = _one_learner_cohort(course)
    form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 1, "max_score": 1}
    )

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    quiz_result = data.courses[0].learner_rows[0].quiz_cells[quiz.id]
    assert quiz_result is not None
    assert quiz_result.passed is None


@pytest.mark.django_db
def test_learner_with_no_progress_rows_is_zero_percent_with_no_activity(
    mock_site_context,
):
    course = CourseFactory()
    _attach(course, TopicFactory())
    cohort, _record = _one_learner_cohort(course)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    row = data.courses[0].learner_rows[0]
    detail = data.learners[0]
    assert row.completion_percentage == 0
    assert detail.has_any_progress is False
    assert detail.has_reportable_activity is False


@pytest.mark.django_db
def test_learner_who_opened_an_item_without_completing_it_has_nothing_to_report(
    mock_site_context,
):
    """The two flags disagree for this learner, and the detail section relies on it.

    Opening a topic writes a TopicProgress row, so `has_any_progress` is True and
    the no-recorded-activity at-risk rule stays silent -- but there is no
    completion, quiz result or wrong answer to print.
    """
    course = CourseFactory()
    topic = TopicFactory()
    _attach(course, topic)
    cohort, record = _one_learner_cohort(course)
    topic_progress(record, topic, complete_time=None)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    detail = data.learners[0]
    assert detail.completion_percentage == 0
    assert detail.has_any_progress is True
    assert detail.has_reportable_activity is False


@pytest.mark.django_db
def test_learner_with_activity_on_one_course_still_appears_in_other_course(
    mock_site_context,
):
    cohort = CohortFactory()
    user = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=user)

    active_course = CourseFactory()
    active_registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=active_course
    )
    topic_done = TopicFactory()
    _attach(active_course, topic_done)
    topic_progress(
        course_progress_record(active_registration.course, user),
        topic_done,
        complete_time=timezone.now(),
    )

    quiet_course = CourseFactory(title="Untouched Course")
    quiet_registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=quiet_course
    )
    _attach(quiet_course, TopicFactory())
    course_progress_record(quiet_registration.course, user)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    sections_by_title = {section.title: section for section in data.courses}
    quiet_section = sections_by_title["Untouched Course"]
    assert len(quiet_section.learner_rows) == 1
    assert quiet_section.learner_rows[0].completion_percentage == 0


@pytest.mark.django_db
def test_inactive_registration_produces_course_section_marked_inactive(
    mock_site_context,
):
    course = CourseFactory()
    _attach(course, TopicFactory())
    cohort, _record = _one_learner_cohort(course, is_active=False)

    data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

    assert len(data.courses) == 1
    assert data.courses[0].is_active is False


@pytest.mark.django_db
def test_correct_none_option_selected_counts_as_distractor(mock_site_context):
    course = CourseFactory()
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
    cohort, record = _one_learner_cohort(course)

    attempt = form_progress(
        record, quiz, completed_time=timezone.now(), scores={"score": 0, "max_score": 1}
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
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
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
        attempt = form_progress(
            course_progress_record(registration.course, learner),
            quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 1},
        )
        answer = QuestionAnswerFactory(form_progress=attempt, question=question)
        answer.selected_options.add(wrong_option if i < wrong_count else correct_option)

    return str(cohort.id), quiz.id


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_gathering_one_site_excludes_data_from_another_site(mock_site_context):
    other_site = SiteFactory()

    course_a = CourseFactory(title="Site A Course")
    topic_a = TopicFactory(title="Site A Topic")
    _attach(course_a, topic_a)
    cohort_a, record_a = _one_learner_cohort(
        course_a, user=UserFactory(first_name="Site", last_name="Alpha")
    )
    topic_progress(record_a, topic_a, complete_time=timezone.now())

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
    registration_b = CohortCourseRegistrationFactory(
        cohort=cohort_b, course=course_b, site=other_site
    )
    topic_b = TopicFactory(title="Site B Topic", site=other_site)
    placement_b = ContentCollectionItemFactory(
        collection_object=course_b, child_object=topic_b, order=0, site=other_site
    )
    # Built row by row rather than through the topic_progress helper: the
    # ambient site is still site A here, so the helper's placement lookup would
    # not see site B's collection item.
    TopicProgressFactory(
        course_progress=ensure_course_progress_record(
            # _base_manager: the ambient site is still site A, so the
            # site-aware manager would not find site B's learner.
            Learner._base_manager.get(
                user=learner_b, organisation=cohort_b.organisation
            ),
            course_b,
            registration_b,
        ),
        topic=topic_b,
        collection_item=placement_b,
        complete_time=timezone.now(),
        site=other_site,
    )

    data = gather_cohort_report_data(str(cohort_a.id), mock_site_context.pk)

    assert [learner.full_name for learner in data.learners] == ["Site Alpha"]
    assert [section.title for section in data.courses] == ["Site A Course"]


def _build_cohort_with_quiz_titles(titles: list[str]) -> str:
    """One cohort, one learner, one course carrying a quiz per title, in order."""
    course = CourseFactory()
    for order, title in enumerate(titles):
        quiz = FormFactory(title=title, strategy=FormStrategy.QUIZ)
        _attach(course, quiz, order=order)
    cohort, _record = _one_learner_cohort(course)
    return str(cohort.id)


@pytest.mark.django_db
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
        course = CourseFactory()
        _attach(course, TopicFactory())
        cohort, _record = _one_learner_cohort(course)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        tables = data.courses[0].summary_tables
        assert len(tables) == 1
        assert tables[0].quizzes == []
        assert len(tables[0].rows) == 1


@pytest.mark.django_db
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


@pytest.mark.django_db
class TestLearnerOrdering:
    def _build_cohort_with_surnames(self, surnames: list[str]) -> str:
        cohort = CohortFactory()
        course = CourseFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        _attach(course, TopicFactory())
        for surname in surnames:
            user = UserFactory(first_name="Sam", last_name=surname)
            CohortMembershipFactory(cohort=cohort, learner__user=user)
            course_progress_record(registration.course, user)
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

        assert [row.learner_id for row in data.courses[0].learner_rows] == [
            detail.learner_id for detail in data.learners
        ]

    def test_summary_table_rows_follow_the_same_order(self, mock_site_context):
        cohort_id = self._build_cohort_with_surnames(["Okonkwo", "Abara"])

        data = gather_cohort_report_data(cohort_id, mock_site_context.pk)

        table = data.courses[0].summary_tables[0]
        assert [row.learner_id for row in table.rows] == [
            detail.learner_id for detail in data.learners
        ]


@pytest.mark.django_db
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


@pytest.mark.django_db
class TestWrongAnswersCarryQuizTitles:
    def test_wrong_answers_are_a_list_of_titled_quizzes_in_course_order(
        self, mock_site_context
    ):
        course = CourseFactory()
        quizzes_and_wrong_options = []
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
            quizzes_and_wrong_options.append((quiz, question, wrong_option))

        cohort, record = _one_learner_cohort(course)
        for quiz, question, wrong_option in quizzes_and_wrong_options:
            attempt = form_progress(
                record,
                quiz,
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
        course = CourseFactory()
        _attach(course, TopicFactory())
        cohort, _record = _one_learner_cohort(course)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.learners[0].wrong_answers == []


@pytest.mark.django_db
def test_query_count_is_constant_across_learner_and_question_scale(
    mock_site_context, django_assert_max_num_queries
):
    small_cohort_id = _build_cohort_with_quiz(learner_count=2, question_count=2)
    with django_assert_max_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(small_cohort_id, mock_site_context.pk)

    large_cohort_id = _build_cohort_with_quiz(learner_count=6, question_count=6)
    with django_assert_max_num_queries(GATHER_QUERY_BOUND):
        gather_cohort_report_data(large_cohort_id, mock_site_context.pk)


@pytest.mark.django_db
class TestQuizAttempts:
    def test_attempts_are_chronological_and_agree_with_the_latest_figures(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)
        cohort, record = _one_learner_cohort(course)

        for day, score in enumerate((0, 1, 2), start=1):
            with time_machine.travel(f"2026-01-0{day}T00:00:00Z", tick=False):
                form_progress(
                    record,
                    quiz,
                    completed_time=timezone.now(),
                    scores={"score": score, "max_score": 2},
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
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)
        cohort, record = _one_learner_cohort(course)
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 1},
        )
        form_progress(record, quiz, completed_time=None, scores={})

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.learners[0].quiz_results[0]
        assert len(result.attempts) == 1
        assert result.attempt_count == 1


@pytest.mark.django_db
class TestFlagSeverity:
    def test_rules_carry_their_declared_severity(self, mock_site_context):
        course = CourseFactory()
        _attach(course, TopicFactory())
        cohort, _record = _one_learner_cohort(course)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        flags = {flag.rule_id: flag.severity for flag in data.learners[0].flags}
        assert flags["no_activity"] == "error"


@pytest.mark.django_db
class TestOrganisationBrand:
    def test_the_cohorts_organisation_is_carried_onto_the_report(
        self, mock_site_context
    ):
        cohort = CohortFactory(
            organisation=OrganisationFactory(name="Northside College")
        )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation.name == "Northside College"

    def test_a_short_name_is_carried_whole_into_every_slot(self, mock_site_context):
        cohort = CohortFactory(
            organisation=OrganisationFactory(name="Northside College")
        )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation.wordmark_name == "Northside College"
        assert data.organisation.footer_name == "Northside College"
        assert data.organisation.wordmark_size_class == "full"

    def test_a_long_name_is_kept_in_full_and_cut_for_each_slot(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory(name=LONG_ORG_NAME))

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation.name == LONG_ORG_NAME
        assert len(data.organisation.wordmark_name) <= WORDMARK_CONDENSED_MAX_CHARS
        assert len(data.organisation.footer_name) <= FOOTER_ORGANISATION_MAX_CHARS
        assert len(data.organisation.wordmark_name) > len(data.organisation.footer_name)

    def test_a_long_name_is_set_at_the_condensed_size(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory(name=LONG_ORG_NAME))

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation.wordmark_size_class == "condensed"

    def test_an_organisation_without_a_logo_has_no_data_uri(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.organisation.logo_data_uri is None


@pytest.mark.django_db
class TestFooterCohortName:
    def test_a_short_cohort_name_is_carried_whole_into_the_footer(
        self, mock_site_context
    ):
        cohort = CohortFactory(name="Cohort A")

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.footer_cohort_name == "Cohort A"

    def test_a_long_cohort_name_is_kept_in_full_and_cut_for_the_footer(
        self, mock_site_context
    ):
        cohort = CohortFactory(name=LONG_COHORT_NAME)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.cohort_name == LONG_COHORT_NAME
        assert len(data.footer_cohort_name) <= FOOTER_COHORT_MAX_CHARS
        assert data.footer_cohort_name.endswith("…")


@pytest.mark.django_db
class TestPoweredByAttribution:
    def test_an_ordinary_organisation_carries_the_platform_mark(
        self, mock_site_context
    ):
        cohort = CohortFactory(organisation=OrganisationFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.show_powered_by is True

    def test_the_sites_own_house_organisation_does_not(self, mock_site_context):
        cohort = CohortFactory(organisation=get_default_organisation(mock_site_context))

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        assert data.show_powered_by is False


@pytest.mark.django_db
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
    course = CourseFactory()

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

    cohort, record = _one_learner_cohort(course)
    now = timezone.now()
    quiz_attempt = form_progress(
        record, quiz, completed_time=now, scores={"score": 0, "max_score": 1}
    )
    QuestionAnswerFactory(
        form_progress=quiz_attempt, question=quiz_question
    ).selected_options.add(distractor)

    survey_attempt = form_progress(
        record, survey, completed_time=now, scores={"Confidence": 3}
    )
    QuestionAnswerFactory(
        form_progress=survey_attempt, question=survey_question
    ).selected_options.add(survey_option)

    return cohort


@pytest.mark.django_db
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


@pytest.mark.django_db
class TestQuizWithNoQuestions:
    def test_a_completed_sitting_reports_no_percentage_or_verdict(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
        _attach(course, quiz)
        FormPageFactory(form=quiz, order=0)
        cohort, record = _one_learner_cohort(course)
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 0, "max_score": 0},
        )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.learners[0].quiz_results[0]
        assert result.latest_percentage is None
        assert result.passed is None


def _two_records_for_one_course(course):
    """A cohort member who is also registered for `course` individually.

    Two grants are two enrolments, so this person holds two course progress
    records for one course. Returns (cohort, cohort record, individual record).
    """
    cohort = CohortFactory()
    membership = CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
    cohort_registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    individual_registration = LearnerCourseRegistrationFactory(
        learner=membership.learner, course=course
    )
    return (
        cohort,
        course_progress_record(cohort_registration.course, membership.learner.user),
        ensure_course_progress_record(
            membership.learner, course, individual_registration
        ),
    )


@pytest.mark.django_db
class TestScopedToOneCourseProgressRecord:
    """The failure mode is not an arbitrary record but every record merging.

    A learner holding two records for one course does the same course twice,
    and the cohort's report has to answer for the cohort's record alone --
    every figure on it, not merely the completion count.
    """

    def test_the_latest_attempt_is_the_latest_within_this_record(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=80)
        _attach(course, quiz)
        cohort, cohort_record, individual_record = _two_records_for_one_course(course)

        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            form_progress(
                cohort_record,
                quiz,
                completed_time=timezone.now(),
                scores={"score": 0, "max_score": 2},
            )
        # Newer and passing, so it would take the cell outright if the two
        # records were read as one.
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            form_progress(
                individual_record,
                quiz,
                completed_time=timezone.now(),
                scores={"score": 2, "max_score": 2},
            )

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        result = data.courses[0].learner_rows[0].quiz_cells[quiz.id]
        assert result is not None
        assert result.attempt_count == 1
        assert result.passed is False

    def test_the_first_attempt_is_the_first_within_this_record(self, mock_site_context):
        """The confusion tally counts first attempts, and "first" is per record."""
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
        )
        QuestionOptionFactory(question=question, text="Right", correct=True, order=0)
        chosen_alone = QuestionOptionFactory(
            question=question, text="Chosen alone", correct=False, order=1
        )
        chosen_with_the_cohort = QuestionOptionFactory(
            question=question, text="Chosen with the cohort", correct=False, order=2
        )
        cohort, cohort_record, individual_record = _two_records_for_one_course(course)

        # Earlier, so a first-attempt rule keyed on the person alone takes it.
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            alone = form_progress(
                individual_record,
                quiz,
                completed_time=timezone.now(),
                scores={"score": 0, "max_score": 1},
            )
            QuestionAnswerFactory(
                form_progress=alone, question=question
            ).selected_options.add(chosen_alone)
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            with_the_cohort = form_progress(
                cohort_record,
                quiz,
                completed_time=timezone.now(),
                scores={"score": 0, "max_score": 1},
            )
            QuestionAnswerFactory(
                form_progress=with_the_cohort, question=question
            ).selected_options.add(chosen_with_the_cohort)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        confusion = data.courses[0].confusions_by_quiz[quiz.id].questions[0]
        assert confusion.respondent_count == 1
        assert confusion.distractors == [("Chosen with the cohort", 1)]

    def test_completions_are_not_unioned_across_two_records(self, mock_site_context):
        course = CourseFactory()
        done_alone = TopicFactory(title="Done alone")
        done_with_the_cohort = TopicFactory(title="Done with the cohort")
        _attach(course, done_alone, order=0)
        _attach(course, done_with_the_cohort, order=1)
        cohort, cohort_record, individual_record = _two_records_for_one_course(course)
        now = timezone.now()
        topic_progress(individual_record, done_alone, complete_time=now)
        topic_progress(cohort_record, done_with_the_cohort, complete_time=now)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        row = data.courses[0].learner_rows[0]
        assert (row.completed_item_count, row.total_item_count) == (1, 2)
        assert [item.title for item in data.learners[0].completed_items] == [
            "Done with the cohort"
        ]

    def test_a_fresh_record_with_no_activity_is_not_activity(self, mock_site_context):
        """Every registered learner holds a record from day one.

        A `has_any_progress` keyed on the record existing would report the
        whole cohort as active and silence the no-recorded-activity flag for
        every one of them.
        """
        cohort = CohortFactory()
        user = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=user)
        course = CourseFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        _attach(course, TopicFactory())
        course_progress_record(registration.course, user)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)

        detail = data.learners[0]
        assert detail.has_any_progress is False
        assert [flag.rule_id for flag in detail.flags] == ["no_activity"]


# Tests of the query-free helpers in freedom_ls.reports.gather.
#
# No `django_db` marker on anything below this point, deliberately. pytest-django
# blocks database access in unmarked tests, so every test here doubles as proof
# that the helper it covers issues no queries -- the guarantee the whole-function
# query bound above cannot give per function.
#
# Inputs come from `gather_input_builders`, which hands back real but unsaved
# model instances. See its docstring for why unsaved is enough.
def _a_column(title: str = "A Quiz") -> QuizColumn:
    return QuizColumn(
        form_id=a_quiz(title).id, title=title, abbreviation="AQ", pass_percentage=50
    )


def _a_learner_row(
    *,
    learner_id: UUID = LEARNER_ID,
    completion: int = 0,
    columns: list[QuizColumn] | None = None,
) -> LearnerRow:
    """A row carrying an (empty) cell for each of `columns`, as gather builds it."""
    return LearnerRow(
        learner_id=learner_id,
        full_name="A Learner",
        completion_percentage=completion,
        completed_item_count=0,
        total_item_count=0,
        last_completed_title=None,
        last_completed_at=None,
        quiz_cells={column.form_id: None for column in columns or []},
    )


def _a_detail(
    *, completion: int = 0, flags: list[AtRiskFlag] | None = None
) -> LearnerDetail:
    return LearnerDetail(
        learner_id=LEARNER_ID,
        full_name="A Learner",
        sort_key=("Learner", "A"),
        completion_percentage=completion,
        completed_item_count=0,
        total_item_count=0,
        last_completed_title=None,
        last_completed_at=None,
        has_any_progress=False,
        completed_items=[],
        quiz_results=[],
        wrong_answers=[],
        report_generated_at=JAN_1,
        flags=flags if flags is not None else [],
    )


def _a_question_index(*questions_and_options) -> QuestionIndex:
    """Build a QuestionIndex from (question, options) pairs, as the loader would."""
    questions = [question for question, _ in questions_and_options]
    options = {question.id: opts for question, opts in questions_and_options}
    return build_question_index(questions, options)


class TestAbbreviateQuizTitle:
    def test_a_trailing_number_is_kept_whole(self) -> None:
        assert _abbreviate_quiz_title("Hydrology Quiz 12") == "HQ12"

    def test_a_title_without_a_number_uses_word_initials(self) -> None:
        assert _abbreviate_quiz_title("Orbit Quiz") == "OQ"

    def test_a_single_word_title_is_truncated_to_four_letters(self) -> None:
        assert _abbreviate_quiz_title("Orbits") == "ORBI"

    def test_a_single_word_title_with_a_number_keeps_its_initial(self) -> None:
        assert _abbreviate_quiz_title("Orbits 3") == "O3"

    def test_a_title_of_only_a_number_returns_that_number(self) -> None:
        assert _abbreviate_quiz_title("7") == "7"

    def test_an_empty_title_returns_an_empty_string(self) -> None:
        assert _abbreviate_quiz_title("") == ""

    def test_only_the_first_four_words_contribute_initials(self) -> None:
        assert _abbreviate_quiz_title("Alpha Beta Gamma Delta Epsilon") == "ABGD"

    def test_repeated_whitespace_between_words_is_ignored(self) -> None:
        assert _abbreviate_quiz_title("Orbit   Quiz") == "OQ"


class TestUniqueAbbreviations:
    def test_distinct_titles_keep_their_own_abbreviations(self) -> None:
        assert _unique_abbreviations(["Orbit Quiz", "Stellar Test"]) == ["OQ", "ST"]

    def test_a_colliding_abbreviation_is_suffixed(self) -> None:
        assert _unique_abbreviations(["Orbit Quiz", "Optics Quiz"]) == ["OQ", "OQ-2"]

    def test_a_third_collision_takes_the_next_suffix(self) -> None:
        titles = ["Orbit Quiz", "Optics Quiz", "Optical Quiz"]

        assert _unique_abbreviations(titles) == ["OQ", "OQ-2", "OQ-3"]

    def test_an_empty_title_list_yields_no_abbreviations(self) -> None:
        assert _unique_abbreviations([]) == []


class TestWordmarkSizeClass:
    def test_a_short_name_is_full_size(self) -> None:
        assert _wordmark_size_class("Northside College") == "full"

    def test_a_name_exactly_at_the_full_threshold_is_full_size(self) -> None:
        name = "N" * WORDMARK_FULL_MAX_CHARS

        assert _wordmark_size_class(name) == "full"

    def test_a_name_one_character_past_the_full_threshold_is_condensed(self) -> None:
        name = "N" * (WORDMARK_FULL_MAX_CHARS + 1)

        assert _wordmark_size_class(name) == "condensed"

    def test_a_name_past_the_condensed_threshold_is_still_condensed(self) -> None:
        name = "N" * (WORDMARK_CONDENSED_MAX_CHARS + 50)

        assert _wordmark_size_class(name) == "condensed"

    def test_an_empty_name_is_full_size(self) -> None:
        assert _wordmark_size_class("") == "full"


class TestTruncateToBudget:
    def test_text_under_the_budget_is_returned_unchanged(self) -> None:
        assert _truncate_to_budget("Orbit College", max_chars=20) == "Orbit College"

    def test_text_exactly_at_the_budget_is_unchanged_with_no_ellipsis(self) -> None:
        text = "N" * 10

        assert _truncate_to_budget(text, max_chars=10) == text

    def test_text_one_character_over_the_budget_is_truncated_with_an_ellipsis(
        self,
    ) -> None:
        text = "N" * 11

        result = _truncate_to_budget(text, max_chars=10)

        assert result == "N" * 9 + "…"
        assert len(result) <= 10

    def test_the_truncated_result_never_exceeds_the_budget(self) -> None:
        text = "N" * 200

        result = _truncate_to_budget(text, max_chars=10)

        assert len(result) <= 10

    def test_three_periods_are_not_appended(self) -> None:
        text = "N" * 200

        result = _truncate_to_budget(text, max_chars=10)

        assert "..." not in result

    def test_a_cut_landing_on_a_space_does_not_leave_a_dangling_space(self) -> None:
        result = _truncate_to_budget("Alpha Beta", max_chars=7)

        assert result == "Alpha…"

    def test_an_empty_string_returns_an_empty_string(self) -> None:
        assert _truncate_to_budget("", max_chars=10) == ""

    def test_a_budget_of_one_does_not_exceed_one_character(self) -> None:
        result = _truncate_to_budget("Northside College", max_chars=1)

        assert len(result) <= 1

    def test_the_wordmark_and_footer_budgets_produce_different_lengths(self) -> None:
        name = "N" * 150

        wordmark_result = _truncate_to_budget(name, WORDMARK_CONDENSED_MAX_CHARS)
        footer_result = _truncate_to_budget(name, FOOTER_ORGANISATION_MAX_CHARS)

        assert len(wordmark_result) <= WORDMARK_CONDENSED_MAX_CHARS
        assert len(footer_result) <= FOOTER_ORGANISATION_MAX_CHARS
        assert len(wordmark_result) != len(footer_result)


class TestFooterIdentityBudgets:
    """The two footer lines against the width the margin box actually has.

    Stated symbolically rather than as literals so that retuning a budget
    against a real render cannot quietly push a line past what it fits in.
    """

    def test_the_organisation_line_fits_the_margin_box(self) -> None:
        assert FOOTER_ORGANISATION_MAX_CHARS <= FOOTER_LINE_MAX_CHARS

    def test_the_cohort_line_fits_the_margin_box(self) -> None:
        assert FOOTER_COHORT_MAX_CHARS <= FOOTER_LINE_MAX_CHARS


class TestChunkQuizColumns:
    def test_no_quizzes_still_yields_one_empty_group(self) -> None:
        assert _chunk_quiz_columns([], 10) == [[]]

    def test_fewer_quizzes_than_the_budget_yields_one_group(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(3)]

        assert _chunk_quiz_columns(columns, 10) == [columns]

    def test_exactly_the_budget_yields_one_group(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(10)]

        assert _chunk_quiz_columns(columns, 10) == [columns]

    def test_one_over_the_budget_splits_into_two_groups(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(11)]

        assert [len(chunk) for chunk in _chunk_quiz_columns(columns, 10)] == [10, 1]

    def test_sixteen_quizzes_at_a_budget_of_eleven_split_eleven_and_five(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(16)]

        assert [len(chunk) for chunk in _chunk_quiz_columns(columns, 11)] == [11, 5]

    def test_every_quiz_appears_once_and_in_column_order(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(16)]

        chunks = _chunk_quiz_columns(columns, 11)

        assert [column for chunk in chunks for column in chunk] == columns


class TestCompletionPercentage:
    def test_a_part_completed_course_rounds_to_whole_percent(self) -> None:
        assert _completion_percentage(1, 3) == 33

    def test_a_course_with_no_items_is_zero_rather_than_a_division_error(self) -> None:
        assert _completion_percentage(0, 0) == 0


class TestCompletionCounts:
    def test_the_total_counts_every_item_whether_completed_or_not(self) -> None:
        items = [a_topic(), a_quiz()]

        assert _completion_counts(items, LEARNER_ID, a_progress_index()) == (0, 2)

    def test_a_completed_topic_counts_toward_the_completed_total(self) -> None:
        topic = a_topic()
        progress = a_progress_index(
            completed_topic_ids_by_learner={LEARNER_ID: {topic.id}}
        )

        assert _completion_counts([topic], LEARNER_ID, progress) == (1, 1)

    def test_a_completed_form_counts_toward_the_completed_total(self) -> None:
        quiz = a_quiz()
        progress = a_progress_index(
            completed_form_ids_by_learner={LEARNER_ID: {quiz.id}}
        )

        assert _completion_counts([quiz], LEARNER_ID, progress) == (1, 1)

    def test_another_learners_completions_are_not_counted(self) -> None:
        topic = a_topic()
        progress = a_progress_index(
            completed_topic_ids_by_learner={OTHER_LEARNER_ID: {topic.id}}
        )

        assert _completion_counts([topic], LEARNER_ID, progress) == (0, 1)

    def test_an_empty_item_list_is_zero_of_zero(self) -> None:
        assert _completion_counts([], LEARNER_ID, a_progress_index()) == (0, 0)


class TestLatestCompletion:
    def test_the_most_recent_completion_wins(self) -> None:
        early, late = a_topic("Early"), a_topic("Late")
        progress = a_progress_index(
            topic_complete_time={
                (LEARNER_ID, early.id): JAN_1,
                (LEARNER_ID, late.id): JAN_2,
            }
        )

        assert _latest_completion([early, late], LEARNER_ID, progress) == (
            "Late",
            JAN_2,
        )

    def test_a_topic_and_a_form_compete_on_timestamp_alone(self) -> None:
        topic = a_topic("Stars")
        quiz = a_quiz("Astronomy Quiz")
        attempt = an_attempt(quiz, completed_time=JAN_1)
        progress = a_progress_index(
            topic_complete_time={(LEARNER_ID, topic.id): JAN_2},
            latest_by_learner_form={(LEARNER_ID, quiz.id): attempt},
            completed_attempts_by_learner_form={(LEARNER_ID, quiz.id): [attempt]},
        )

        assert _latest_completion([topic, quiz], LEARNER_ID, progress) == (
            "Stars",
            JAN_2,
        )

    def test_a_form_with_no_completed_attempt_is_ignored(self) -> None:
        quiz = a_quiz("Astronomy Quiz")
        started = an_attempt(quiz, completed_time=None)
        progress = a_progress_index(
            latest_by_learner_form={(LEARNER_ID, quiz.id): started}
        )

        assert _latest_completion([quiz], LEARNER_ID, progress) == (None, None)

    def test_a_learner_with_no_completions_has_no_title_and_no_time(self) -> None:
        assert _latest_completion([a_topic()], LEARNER_ID, a_progress_index()) == (
            None,
            None,
        )


class TestCompletedItems:
    def test_an_uncompleted_topic_is_absent(self) -> None:
        assert _completed_items([a_topic()], LEARNER_ID, a_progress_index()) == []

    def test_a_completed_topic_is_not_marked_as_a_quiz(self) -> None:
        topic = a_topic("Stars")
        progress = a_progress_index(topic_complete_time={(LEARNER_ID, topic.id): JAN_1})

        completed = _completed_items([topic], LEARNER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [("Stars", False)]

    def test_a_quiz_form_is_marked_as_a_quiz(self) -> None:
        quiz = a_quiz("Astronomy Quiz")
        progress = attempted(quiz, [an_attempt(quiz, completed_time=JAN_1)])

        completed = _completed_items([quiz], LEARNER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [
            ("Astronomy Quiz", True)
        ]

    def test_a_survey_form_is_not_marked_as_a_quiz(self) -> None:
        survey = a_survey("Confidence Survey")
        progress = attempted(survey, [an_attempt(survey, completed_time=JAN_1)])

        completed = _completed_items([survey], LEARNER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [
            ("Confidence Survey", False)
        ]

    def test_items_are_returned_in_the_order_the_course_lists_them(self) -> None:
        first, second = a_topic("First"), a_topic("Second")
        progress = a_progress_index(
            topic_complete_time={
                (LEARNER_ID, first.id): JAN_2,
                (LEARNER_ID, second.id): JAN_1,
            }
        )

        completed = _completed_items([first, second], LEARNER_ID, progress)

        assert [item.title for item in completed] == ["First", "Second"]


class TestScoreAttempt:
    def test_an_incomplete_sitting_scores_nothing(self) -> None:
        quiz = a_quiz()

        assert _score_attempt(an_attempt(quiz, completed_time=None), quiz) == (
            None,
            None,
            None,
            None,
        )

    def test_a_passing_sitting_reports_its_score_and_verdict(self) -> None:
        quiz = a_quiz(pass_percentage=50)
        attempt = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 3, "max_score": 4}
        )

        assert _score_attempt(attempt, quiz) == (3, 4, 75, True)

    def test_a_failing_sitting_reports_a_false_verdict(self) -> None:
        quiz = a_quiz(pass_percentage=80)
        attempt = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 4}
        )

        assert _score_attempt(attempt, quiz) == (1, 4, 25, False)

    def test_a_quiz_with_no_pass_mark_has_no_verdict(self) -> None:
        quiz = a_quiz(pass_percentage=None)
        attempt = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 2, "max_score": 4}
        )

        assert _score_attempt(attempt, quiz) == (2, 4, 50, None)

    def test_a_quiz_with_no_questions_reports_no_percentage(self) -> None:
        quiz = a_quiz(pass_percentage=50)
        attempt = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 0}
        )

        assert _score_attempt(attempt, quiz) == (0, 0, None, None)


class TestQuizResultFor:
    def test_a_quiz_never_attempted_returns_none(self) -> None:
        quiz = a_quiz()

        assert _quiz_result_for(LEARNER_ID, quiz, a_progress_index().forms) is None

    def test_attempts_are_numbered_from_one_in_list_order(self) -> None:
        quiz = a_quiz(pass_percentage=50)
        attempts = [
            an_attempt(quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 2}),
            an_attempt(quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 2}),
            an_attempt(quiz, completed_time=JAN_3, scores={"score": 2, "max_score": 2}),
        ]
        progress = attempted(quiz, attempts)

        result = _quiz_result_for(LEARNER_ID, quiz, progress.forms)

        assert result is not None
        assert [attempt.attempt_number for attempt in result.attempts] == [1, 2, 3]
        assert [attempt.percentage for attempt in result.attempts] == [0, 50, 100]

    def test_the_latest_figures_agree_with_the_final_attempt(self) -> None:
        quiz = a_quiz(pass_percentage=50)
        attempts = [
            an_attempt(quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 2}),
            an_attempt(quiz, completed_time=JAN_2, scores={"score": 2, "max_score": 2}),
        ]
        progress = attempted(quiz, attempts)

        result = _quiz_result_for(LEARNER_ID, quiz, progress.forms)

        assert result is not None
        assert result.latest_percentage == result.attempts[-1].percentage
        assert result.passed == result.attempts[-1].passed
        assert result.completed_at == result.attempts[-1].completed_at

    def test_the_attempt_count_matches_the_attempt_list(self) -> None:
        quiz = a_quiz()
        attempts = [
            an_attempt(quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}),
            an_attempt(quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 1}),
        ]

        result = _quiz_result_for(LEARNER_ID, quiz, attempted(quiz, attempts).forms)

        assert result is not None
        assert result.attempt_count == len(result.attempts) == 2


class TestFoldTopicProgressRows:
    def test_a_row_with_no_complete_time_still_marks_the_learner_active(self) -> None:
        topic = a_topic()

        index = fold_topic_progress_rows([(LEARNER_ID, topic.id, None)])

        assert index.learner_ids_seen == {LEARNER_ID}
        assert index.completed_topic_ids_by_learner.get(LEARNER_ID, set()) == set()

    def test_a_completed_topic_is_indexed_against_its_learner(self) -> None:
        topic = a_topic()

        index = fold_topic_progress_rows([(LEARNER_ID, topic.id, JAN_1)])

        assert index.completed_topic_ids_by_learner[LEARNER_ID] == {topic.id}
        assert index.complete_time[(LEARNER_ID, topic.id)] == JAN_1


class TestFoldFormProgressRows:
    """The fold's contract is that rows arrive newest-completed first.

    That ordering is the loader's responsibility and is asserted in
    test_gather_indexes.py; here the rows are simply handed over in it.
    """

    def test_the_first_row_for_a_pair_becomes_the_latest_progress(self) -> None:
        quiz = a_quiz()
        newest = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 1}
        )
        oldest = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}
        )

        index = fold_form_progress_rows([newest, oldest])

        assert index.latest_by_learner_form[(LEARNER_ID, quiz.id)] is newest

    def test_attempts_are_returned_oldest_first(self) -> None:
        quiz = a_quiz()
        newest = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 1}
        )
        oldest = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}
        )

        index = fold_form_progress_rows([newest, oldest])

        assert index.completed_attempts_by_learner_form[(LEARNER_ID, quiz.id)] == [
            oldest,
            newest,
        ]

    def test_the_completed_attempt_ids_stay_newest_first(self) -> None:
        """They drive the sat-pair walk, and so the order of a learner's wrong answers."""
        quiz = a_quiz()
        newest = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 1}
        )
        oldest = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}
        )

        index = fold_form_progress_rows([newest, oldest])

        assert index.completed_attempt_ids == [newest.id, oldest.id]

    def test_an_incomplete_sitting_is_not_an_attempt(self) -> None:
        quiz = a_quiz()
        done = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}
        )
        started = an_attempt(quiz, completed_time=None)

        index = fold_form_progress_rows([done, started])

        assert index.completed_attempts_by_learner_form[(LEARNER_ID, quiz.id)] == [done]

    def test_a_failed_latest_attempt_does_not_complete_the_form(self) -> None:
        quiz = a_quiz(pass_percentage=80)
        failed_retry = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 0, "max_score": 2}
        )
        passed_first = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 2, "max_score": 2}
        )

        index = fold_form_progress_rows([failed_retry, passed_first])

        assert index.completed_form_ids_by_learner.get(LEARNER_ID, set()) == set()

    def test_a_passed_latest_attempt_completes_the_form(self) -> None:
        quiz = a_quiz(pass_percentage=80)
        passed_retry = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 2, "max_score": 2}
        )
        failed_first = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 2}
        )

        index = fold_form_progress_rows([passed_retry, failed_first])

        assert index.completed_form_ids_by_learner[LEARNER_ID] == {quiz.id}

    def test_a_survey_is_completed_by_any_sitting(self) -> None:
        survey = a_survey()
        sitting = an_attempt(survey, completed_time=JAN_1, scores={"Confidence": 3})

        index = fold_form_progress_rows([sitting])

        assert index.completed_form_ids_by_learner[LEARNER_ID] == {survey.id}

    def test_every_sitting_resolves_to_its_learner_and_form(self) -> None:
        survey = a_survey()
        sitting = an_attempt(survey, completed_time=JAN_1, scores={"Confidence": 3})

        index = fold_form_progress_rows([sitting])

        assert index.learner_form_by_attempt_id[sitting.id] == (LEARNER_ID, survey.id)


class TestMergeProgressIndexes:
    def test_a_learner_seen_only_in_form_progress_still_counts_as_active(self) -> None:
        quiz = a_quiz()
        forms = fold_form_progress_rows([an_attempt(quiz, completed_time=None)])

        merged = merge_progress_indexes(fold_topic_progress_rows([]), forms)

        assert merged.learner_ids_with_any_progress == {LEARNER_ID}

    def test_a_learner_seen_only_in_topic_progress_still_counts_as_active(self) -> None:
        topics = fold_topic_progress_rows([(OTHER_LEARNER_ID, a_topic().id, None)])

        merged = merge_progress_indexes(topics, fold_form_progress_rows([]))

        assert merged.learner_ids_with_any_progress == {OTHER_LEARNER_ID}


class TestBuildQuestionIndex:
    def test_questions_are_numbered_from_one_within_each_form(self) -> None:
        quiz = a_quiz()
        page = a_page(quiz)
        first = a_question(quiz, text="First", order=0, page=page)
        second = a_question(quiz, text="Second", order=1, page=page)

        index = _a_question_index((first, []), (second, []))

        assert index.number_by_id[first.id] == 1
        assert index.number_by_id[second.id] == 2

    def test_numbering_restarts_for_a_second_form(self) -> None:
        first_quiz, second_quiz = a_quiz("One"), a_quiz("Two")
        first = a_question(first_quiz, text="First")
        second = a_question(second_quiz, text="Second")

        index = _a_question_index((first, []), (second, []))

        assert index.number_by_id[first.id] == 1
        assert index.number_by_id[second.id] == 1

    def test_only_options_marked_correct_reach_the_correct_texts(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        options = [
            an_option(question, "Mars", correct=True),
            an_option(question, "Sun", correct=False),
            an_option(question, "Unset", correct=None),
        ]

        index = _a_question_index((question, options))

        assert index.correct_option_texts[question.id] == ["Mars"]

    def test_questions_are_grouped_by_their_form(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)

        index = _a_question_index((question, []))

        assert index.by_form[quiz.id] == [question]


class TestIndexDistractors:
    def test_a_row_for_an_unknown_question_is_dropped(self) -> None:
        quiz = a_quiz()
        known = a_question(quiz)
        index = _a_question_index((known, []))
        rows = [
            {
                "question_id": a_question(quiz).id,
                "id": known.id,
                "text": "Stray",
                "times_selected": 3,
            }
        ]

        assert index_distractors(rows, index) == {}

    def test_a_free_text_questions_row_is_dropped(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz, question_type=QuestionType.SHORT_TEXT)
        index = _a_question_index((question, []))
        rows = [
            {
                "question_id": question.id,
                "id": question.id,
                "text": "Anything",
                "times_selected": 2,
            }
        ]

        assert index_distractors(rows, index) == {}

    def test_rows_keep_the_most_selected_first_order_they_arrive_in(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))
        rows = [
            {
                "question_id": question.id,
                "id": question.id,
                "text": "Popular",
                "times_selected": 5,
            },
            {
                "question_id": question.id,
                "id": question.id,
                "text": "Rare",
                "times_selected": 1,
            },
        ]

        assert index_distractors(rows, index)[question.id] == [
            ("Popular", 5),
            ("Rare", 1),
        ]


class TestTallyQuizAnswers:
    def test_an_option_is_counted_once_per_wrong_attempt_it_was_chosen_in(self) -> None:
        """The count the report prints is attempts-chosen-in, not options-chosen.

        A sitting cannot select one option twice, so an option reaching two only
        by being chosen again on a later sitting is what separates a settled
        misconception from a one-off guess.
        """
        quiz = a_quiz()
        question = a_question(quiz)
        venus = an_option(question, "Venus", correct=False)
        mercury = an_option(question, "Mercury", correct=False)
        older = an_attempt(quiz, completed_time=JAN_1)
        newer = an_attempt(quiz, completed_time=JAN_2)
        sat = SatQuestions(
            # Newest sitting first, as fold_form_progress_rows leaves them.
            pairs=[(newer.id, question), (older.id, question)],
            selected_options_by_pair={
                (newer.id, question.id): [venus],
                (older.id, question.id): [venus, mercury],
            },
            correctness={
                (newer.id, question.id): False,
                (older.id, question.id): False,
            },
        )
        forms = a_progress_index(
            learner_form_by_attempt_id={
                newer.id: (LEARNER_ID, quiz.id),
                older.id: (LEARNER_ID, quiz.id),
            }
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(LEARNER_ID, quiz.id, question.id)]
        assert list(counts.items()) == [(("Venus", False), 2), (("Mercury", False), 1)]

    def test_a_correct_sittings_selections_are_not_counted(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        mars = an_option(question, "Mars", correct=True)
        attempt = an_attempt(quiz, completed_time=JAN_1)
        sat = SatQuestions(
            pairs=[(attempt.id, question)],
            selected_options_by_pair={(attempt.id, question.id): [mars]},
            correctness={(attempt.id, question.id): True},
        )
        forms = a_progress_index(
            learner_form_by_attempt_id={attempt.id: (LEARNER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        assert (LEARNER_ID, quiz.id, question.id) not in tallies.wrong_selected_counts

    def test_a_correct_option_ticked_on_a_wrong_sitting_keeps_its_correctness(
        self,
    ) -> None:
        """Multi-select is why a correct option can sit inside a wrong answer.

        Ticking every correct option plus one distractor scores the question
        wrong, so the learner's correct ticks have to stay distinguishable from
        the tick that cost them the mark.
        """
        quiz = a_quiz()
        question = a_question(quiz)
        right = an_option(question, "Mars", correct=True)
        wrong = an_option(question, "Sun", correct=False)
        attempt = an_attempt(quiz, completed_time=JAN_1)
        sat = SatQuestions(
            pairs=[(attempt.id, question)],
            selected_options_by_pair={(attempt.id, question.id): [right, wrong]},
            correctness={(attempt.id, question.id): False},
        )
        forms = a_progress_index(
            learner_form_by_attempt_id={attempt.id: (LEARNER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(LEARNER_ID, quiz.id, question.id)]
        assert list(counts.items()) == [(("Mars", True), 1), (("Sun", False), 1)]

    def test_an_option_with_no_verdict_is_tallied_as_neither(self) -> None:
        """`correct` is nullable, and None is not True -- it is also not False.

        The same nullable-field subtlety load_distractor_rows guards against with
        `.exclude(correct=True)`: an unmarked option must never be painted as a
        correct tick, and must not claim to be a known mistake either.
        """
        quiz = a_quiz()
        question = a_question(quiz)
        unmarked = an_option(question, "Pluto", correct=None)
        attempt = an_attempt(quiz, completed_time=JAN_1)
        sat = SatQuestions(
            pairs=[(attempt.id, question)],
            selected_options_by_pair={(attempt.id, question.id): [unmarked]},
            correctness={(attempt.id, question.id): False},
        )
        forms = a_progress_index(
            learner_form_by_attempt_id={attempt.id: (LEARNER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(LEARNER_ID, quiz.id, question.id)]
        assert list(counts.items()) == [(("Pluto", None), 1)]


class TestBuildWrongAnswersByUserQuiz:
    def test_answers_are_ordered_by_question_number(self) -> None:
        quiz = a_quiz()
        page = a_page(quiz)
        first = a_question(quiz, text="First", order=0, page=page)
        second = a_question(quiz, text="Second", order=1, page=page)
        index = _a_question_index((first, []), (second, []))
        tallies = QuizTallies(
            wrong_counts={
                (LEARNER_ID, quiz.id, second.id): 1,
                (LEARNER_ID, quiz.id, first.id): 1,
            },
            wrong_selected_counts={
                (LEARNER_ID, quiz.id, second.id): {},
                (LEARNER_ID, quiz.id, first.id): {},
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        built = build_wrong_answers_by_learner_quiz(tallies, index)

        assert [answer.question_number for answer in built[LEARNER_ID][quiz.id]] == [
            1,
            2,
        ]

    def test_each_answer_carries_its_questions_correct_option_texts(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        options = [an_option(question, "Mars", correct=True)]
        index = _a_question_index((question, options))
        tallies = QuizTallies(
            wrong_counts={(LEARNER_ID, quiz.id, question.id): 2},
            wrong_selected_counts={
                (LEARNER_ID, quiz.id, question.id): {("Sun", False): 2}
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        answer = build_wrong_answers_by_learner_quiz(tallies, index)[LEARNER_ID][
            quiz.id
        ][0]

        assert answer.times_wrong == 2
        assert answer.selected_options == [SelectedOption("Sun", False, 2)]
        assert answer.correct_option_texts == ["Mars"]

    def test_selected_options_carry_each_options_own_correctness(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        options = [an_option(question, "Mars", correct=True)]
        index = _a_question_index((question, options))
        tallies = QuizTallies(
            wrong_counts={(LEARNER_ID, quiz.id, question.id): 1},
            wrong_selected_counts={
                (LEARNER_ID, quiz.id, question.id): {
                    ("Mars", True): 1,
                    ("Sun", False): 1,
                    ("Pluto", None): 1,
                }
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        answer = build_wrong_answers_by_learner_quiz(tallies, index)[LEARNER_ID][
            quiz.id
        ][0]

        assert answer.selected_options == [
            SelectedOption("Mars", True, 1),
            SelectedOption("Sun", False, 1),
            SelectedOption("Pluto", None, 1),
        ]

    def test_one_learners_wrong_answers_do_not_reach_another(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))
        tallies = QuizTallies(
            wrong_counts={(LEARNER_ID, quiz.id, question.id): 1},
            wrong_selected_counts={(LEARNER_ID, quiz.id, question.id): {}},
            respondent_counts={},
            wrong_counts_first={},
        )

        built = build_wrong_answers_by_learner_quiz(tallies, index)

        assert OTHER_LEARNER_ID not in built


class TestBuildConfusionBlock:
    def _tallies(self, *, wrong: dict, respondents: dict) -> QuizTallies:
        return QuizTallies(
            wrong_counts={},
            wrong_selected_counts={},
            respondent_counts=respondents,
            wrong_counts_first=wrong,
        )

    def test_a_question_nobody_got_wrong_is_absent(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))

        block = build_confusion_block(
            quiz.id, index, self._tallies(wrong={}, respondents={question.id: 5}), {}
        )

        assert block.questions == []
        assert block.total == 0

    def test_questions_are_ordered_by_error_rate(self) -> None:
        quiz = a_quiz()
        page = a_page(quiz)
        mild = a_question(quiz, text="Mild", order=0, page=page)
        severe = a_question(quiz, text="Severe", order=1, page=page)
        index = _a_question_index((mild, []), (severe, []))
        tallies = self._tallies(
            wrong={mild.id: 1, severe.id: 9},
            respondents={mild.id: 10, severe.id: 10},
        )

        block = build_confusion_block(quiz.id, index, tallies, {})

        assert [question.question_text for question in block.questions] == [
            "Severe",
            "Mild",
        ]

    def test_the_percentage_is_hidden_below_the_respondent_threshold(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))
        tallies = self._tallies(wrong={question.id: 3}, respondents={question.id: 9})

        confusion = build_confusion_block(quiz.id, index, tallies, {}).questions[0]

        assert confusion.show_percentage is False
        assert confusion.wrong_percentage is None
        assert confusion.wrong_count == 3

    def test_the_percentage_is_shown_at_the_respondent_threshold(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))
        tallies = self._tallies(wrong={question.id: 5}, respondents={question.id: 10})

        confusion = build_confusion_block(quiz.id, index, tallies, {}).questions[0]

        assert confusion.show_percentage is True
        assert confusion.wrong_percentage == 50

    def test_a_free_text_question_is_never_a_confusion(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz, question_type=QuestionType.SHORT_TEXT)
        index = _a_question_index((question, []))
        tallies = self._tallies(wrong={question.id: 4}, respondents={question.id: 10})

        assert build_confusion_block(quiz.id, index, tallies, {}).questions == []

    def test_at_most_ten_questions_are_shown_but_the_total_counts_them_all(
        self,
    ) -> None:
        quiz = a_quiz()
        page = a_page(quiz)
        questions = [
            a_question(quiz, text=f"Q{index}", order=index, page=page)
            for index in range(12)
        ]
        index = _a_question_index(*((question, []) for question in questions))
        tallies = self._tallies(
            wrong={question.id: 1 for question in questions},
            respondents={question.id: 10 for question in questions},
        )

        block = build_confusion_block(quiz.id, index, tallies, {})

        assert block.shown == 10
        assert block.total == 12

    def test_a_question_carries_its_distractors(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        index = _a_question_index((question, []))
        tallies = self._tallies(wrong={question.id: 4}, respondents={question.id: 10})

        block = build_confusion_block(
            quiz.id, index, tallies, {question.id: [("Sun", 4)]}
        )

        assert block.questions[0].distractors == [("Sun", 4)]


class TestBuildQuizColumns:
    def test_only_quiz_strategy_forms_become_columns(self) -> None:
        items = [a_topic(), a_survey("Confidence Survey"), a_quiz("Orbit Quiz")]

        columns = _build_quiz_columns(items)

        assert [column.title for column in columns] == ["Orbit Quiz"]

    def test_columns_carry_the_forms_pass_percentage(self) -> None:
        columns = _build_quiz_columns([a_quiz("Orbit Quiz", pass_percentage=65)])

        assert columns[0].pass_percentage == 65

    def test_columns_follow_course_item_order_and_are_abbreviated(self) -> None:
        items = [a_quiz("Orbit Quiz"), a_quiz("Optics Quiz")]

        columns = _build_quiz_columns(items)

        assert [column.abbreviation for column in columns] == ["OQ", "OQ-2"]


class TestBuildLearnerRow:
    def test_the_row_reports_the_learners_completion_over_the_courses_items(
        self,
    ) -> None:
        learner = a_learner(first_name="Ada", last_name="Lovelace")
        topic, quiz = a_topic("Stars"), a_quiz("Orbit Quiz")
        progress = a_progress_index(
            completed_topic_ids_by_learner={LEARNER_ID: {topic.id}},
            topic_complete_time={(LEARNER_ID, topic.id): JAN_1},
        )

        row = _build_learner_row(
            LEARNER_ID,
            [topic, quiz],
            [],
            a_roster((LEARNER_ID, learner)),
            a_catalogue(course_items={a_quiz().id: [topic, quiz]}),
            progress,
        )

        assert row.full_name == "Ada Lovelace"
        assert (row.completed_item_count, row.total_item_count) == (1, 2)
        assert row.completion_percentage == 50
        assert row.last_completed_title == "Stars"

    def test_a_quiz_the_learner_never_sat_gets_an_empty_cell(self) -> None:
        learner = a_learner()
        quiz = a_quiz("Orbit Quiz")
        column = QuizColumn(
            form_id=quiz.id, title="Orbit Quiz", abbreviation="OQ", pass_percentage=50
        )

        row = _build_learner_row(
            LEARNER_ID,
            [quiz],
            [column],
            a_roster((LEARNER_ID, learner)),
            a_catalogue(course_items={a_quiz().id: [quiz]}),
            a_progress_index(),
        )

        assert row.quiz_cells == {quiz.id: None}


class TestBuildSummaryTables:
    def test_a_course_with_no_quizzes_yields_one_table_that_still_has_rows(
        self,
    ) -> None:
        rows = [_a_learner_row()]

        tables = _build_summary_tables([], rows, 10)

        assert len(tables) == 1
        assert tables[0].quizzes == []
        assert len(tables[0].rows) == 1

    def test_only_the_first_table_of_a_split_is_not_continued(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(16)]
        rows = [_a_learner_row(columns=columns)]

        tables = _build_summary_tables(columns, rows, 11)

        assert [table.continued for table in tables] == [False, True]

    def test_each_row_carries_one_cell_per_quiz_in_its_table(self) -> None:
        columns = [_a_column(f"Quiz {index}") for index in range(3)]
        rows = [_a_learner_row(columns=columns)]

        tables = _build_summary_tables(columns, rows, 2)

        assert [len(table.rows[0].cells) for table in tables] == [2, 1]


class TestEvaluateAtRiskFlags:
    def test_a_learner_with_no_activity_is_flagged(self) -> None:
        flags = _evaluate_at_risk_flags(_a_detail())

        assert [flag.rule_id for flag in flags] == ["no_activity"]

    def test_a_flag_carries_its_rules_label_and_severity(self) -> None:
        flag = _evaluate_at_risk_flags(_a_detail())[0]

        assert flag.label == "No recorded activity"
        assert flag.severity == "error"
        assert flag.reason


class TestBuildAttentionList:
    def _flagged(self, completion: int) -> LearnerDetail:
        flag = AtRiskFlag(
            rule_id="no_activity", label="No activity", reason="none", severity="error"
        )
        return _a_detail(completion=completion, flags=[flag])

    def test_only_flagged_learners_are_listed(self) -> None:
        listed = _build_attention_list([self._flagged(10), _a_detail(completion=50)])

        assert listed.total == 1
        assert listed.learners[0].completion_percentage == 10

    def test_learners_are_ordered_least_complete_first(self) -> None:
        listed = _build_attention_list(
            [self._flagged(80), self._flagged(10), self._flagged(45)]
        )

        assert [learner.completion_percentage for learner in listed.learners] == [
            10,
            45,
            80,
        ]

    def test_at_most_twelve_are_shown_but_the_total_counts_them_all(self) -> None:
        listed = _build_attention_list([self._flagged(index) for index in range(15)])

        assert listed.shown == 12
        assert listed.total == 15


class TestCompletionStatistics:
    def test_a_cohort_with_no_learners_reports_zeroes(self) -> None:
        assert _completion_statistics([]) == CompletionStats(0, 0, 0)

    def test_the_median_of_an_even_number_of_learners_is_rounded(self) -> None:
        details = [_a_detail(completion=value) for value in (10, 20, 30, 45)]

        assert _completion_statistics(details).median_completion == 25

    def test_not_started_counts_only_zero_percent_learners(self) -> None:
        details = [_a_detail(completion=value) for value in (0, 0, 1, 100)]

        assert _completion_statistics(details).not_started_count == 2

    def test_complete_counts_only_fully_finished_learners(self) -> None:
        details = [_a_detail(completion=value) for value in (0, 99, 100, 100)]

        assert _completion_statistics(details).complete_count == 2


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Voltage Quiz 01", "VQ01"),
        ("Hydrology Quiz 12", "HQ12"),
        ("Ratios Quiz 10", "RQ10"),
    ],
)
def test_quiz_numbers_survive_abbreviation_intact(title: str, expected: str) -> None:
    """A dropped digit would both lose the number and invite column collisions."""
    assert _abbreviate_quiz_title(title) == expected
