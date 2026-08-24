"""Tests for the individual query loaders in freedom_ls.reports.indexes.

These cover what the pure tests in test_gather_helpers.py structurally cannot:
the orderings, `select_related` calls and site filters that only exist in SQL,
and the per-loader query counts. A per-loader count says *which* stage
regressed, where the whole-function bound in test_gather.py only says that one
did.
"""

from __future__ import annotations

import pytest
import time_machine

from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import (
    ActivityFactory,
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy, QuestionType
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.reports.gather import (
    _build_course_section,
    _build_learner_detail,
    build_confusions_by_quiz,
    build_wrong_answers_by_user_quiz,
    tally_quiz_answers,
)
from freedom_ls.reports.indexes import (
    ReportTooLargeError,
    build_course_catalogue,
    build_question_index,
    build_sat_questions,
    index_distractors,
    load_distractor_rows,
    load_first_attempt_ids,
    load_form_progress_rows,
    load_progress_index,
    load_quiz_questions,
    load_registrations,
    load_roster,
    load_selected_options_by_pair,
    load_topic_progress_rows,
    resolve_site_name,
)

pytestmark = pytest.mark.django_db


def _attach(collection: object, child: object, order: int = 0) -> None:
    ContentCollectionItemFactory(
        collection_object=collection, child_object=child, order=order
    )


class TestLoadRegistrations:
    def test_active_registrations_come_before_inactive_ones(self, mock_site_context):
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=CourseFactory(title="A Retired"), is_active=False
        )
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=CourseFactory(title="Z Running"), is_active=True
        )

        registrations = load_registrations(cohort, mock_site_context.pk)

        assert [reg.collection.title for reg in registrations] == [
            "Z Running",
            "A Retired",
        ]

    def test_registrations_are_ordered_by_course_title_within_a_group(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=CourseFactory(title="Beta")
        )
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=CourseFactory(title="Alpha")
        )

        registrations = load_registrations(cohort, mock_site_context.pk)

        assert [reg.collection.title for reg in registrations] == ["Alpha", "Beta"]

    def test_a_registration_on_another_site_is_excluded(self, mock_site_context):
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=CourseFactory())
        other_site = SiteFactory(name="Other", domain="other.test")

        assert load_registrations(cohort, other_site.pk) == []

    def test_registrations_and_their_courses_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=CourseFactory())
        CohortCourseRegistrationFactory(cohort=cohort, collection=CourseFactory())

        with django_assert_num_queries(1):
            registrations = load_registrations(cohort, mock_site_context.pk)
            # select_related, so reading the course title adds nothing.
            [reg.collection.title for reg in registrations]


class TestLoadRoster:
    def test_learners_are_ordered_by_surname(self, mock_site_context):
        cohort = CohortFactory()
        zeta = UserFactory(first_name="Ada", last_name="Zeta")
        alpha = UserFactory(first_name="Bo", last_name="Alpha")
        CohortMembershipFactory(cohort=cohort, learner__user=zeta)
        CohortMembershipFactory(cohort=cohort, learner__user=alpha)

        roster = load_roster(cohort, mock_site_context.pk)

        assert roster.learner_ids == [alpha.id, zeta.id]

    def test_a_learner_with_no_surname_is_keyed_by_their_email(self, mock_site_context):
        cohort = CohortFactory()
        unnamed = UserFactory(first_name="", last_name="", email="aaa@example.test")
        CohortMembershipFactory(cohort=cohort, learner__user=unnamed)

        roster = load_roster(cohort, mock_site_context.pk)

        assert roster.sort_key_by_id[unnamed.id] == ("aaa@example.test", "")

    @override_settings(REPORTS_MAX_LEARNERS=1)
    def test_a_cohort_over_the_limit_is_refused(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())

        with pytest.raises(ReportTooLargeError, match="exceeding"):
            load_roster(cohort, mock_site_context.pk)

    @override_settings(REPORTS_MAX_LEARNERS=2)
    def test_a_cohort_exactly_at_the_limit_is_allowed(self, mock_site_context):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())

        assert len(load_roster(cohort, mock_site_context.pk).learner_ids) == 2

    def test_members_and_their_users_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())

        with django_assert_num_queries(1):
            roster = load_roster(cohort, mock_site_context.pk)
            [user.display_name for user in roster.learners_by_id.values()]


class TestBuildCourseCatalogue:
    def test_an_activity_is_excluded_from_the_item_list(self, mock_site_context):
        cohort = CohortFactory()
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        topic = TopicFactory()
        _attach(course, topic, order=0)
        _attach(course, ActivityFactory(), order=1)

        catalogue = build_course_catalogue(
            load_registrations(cohort, mock_site_context.pk)
        )

        assert catalogue.all_items == [topic]

    def test_a_survey_is_a_form_but_not_a_quiz(self, mock_site_context):
        cohort = CohortFactory()
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        survey = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
        _attach(course, survey)

        catalogue = build_course_catalogue(
            load_registrations(cohort, mock_site_context.pk)
        )

        assert catalogue.form_ids == {survey.id}
        assert catalogue.quiz_form_ids == set()

    def test_quizzes_are_ordered_by_their_position_in_the_course(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        first = FormFactory(title="First", strategy=FormStrategy.QUIZ)
        second = FormFactory(title="Second", strategy=FormStrategy.QUIZ)
        _attach(course, first, order=0)
        _attach(course, second, order=1)

        catalogue = build_course_catalogue(
            load_registrations(cohort, mock_site_context.pk)
        )

        assert catalogue.ordered_quiz_form_ids == [first.id, second.id]


class TestLoadTopicProgressRows:
    def test_only_the_named_learners_rows_are_read(self, mock_site_context):
        learner, other = UserFactory(), UserFactory()
        topic = TopicFactory()
        TopicProgressFactory(user=learner, topic=topic, complete_time=timezone.now())
        TopicProgressFactory(user=other, topic=topic, complete_time=timezone.now())

        rows = load_topic_progress_rows(mock_site_context.pk, [learner.id], {topic.id})

        assert [row[0] for row in rows] == [learner.id]

    def test_rows_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        learner = UserFactory()
        topic = TopicFactory()
        TopicProgressFactory(user=learner, topic=topic, complete_time=timezone.now())

        with django_assert_num_queries(1):
            load_topic_progress_rows(mock_site_context.pk, [learner.id], {topic.id})


class TestLoadFormProgressRows:
    def test_completed_sittings_arrive_newest_first(self, mock_site_context):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            older = FormProgressFactory(
                user=learner, form=quiz, completed_time=timezone.now(), scores={}
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            newer = FormProgressFactory(
                user=learner, form=quiz, completed_time=timezone.now(), scores={}
            )

        rows = load_form_progress_rows(mock_site_context.pk, [learner.id], {quiz.id})

        assert [row.id for row in rows] == [newer.id, older.id]

    def test_an_incomplete_sitting_sorts_after_every_completed_one(
        self, mock_site_context
    ):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        started = FormProgressFactory(user=learner, form=quiz, completed_time=None)
        done = FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )

        rows = load_form_progress_rows(mock_site_context.pk, [learner.id], {quiz.id})

        assert [row.id for row in rows] == [done.id, started.id]

    def test_reading_each_rows_form_issues_no_further_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """select_related("form") is what keeps the pure stage query-free."""
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )
        FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )

        with django_assert_num_queries(1):
            rows = load_form_progress_rows(
                mock_site_context.pk, [learner.id], {quiz.id}
            )
            [row.form.quiz_pass_percentage for row in rows]


class TestLoadFirstAttemptIds:
    def test_only_the_earliest_completed_sitting_per_learner_and_quiz_is_returned(
        self, mock_site_context
    ):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            first = FormProgressFactory(
                user=learner, form=quiz, completed_time=timezone.now(), scores={}
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            FormProgressFactory(
                user=learner, form=quiz, completed_time=timezone.now(), scores={}
            )

        assert load_first_attempt_ids(
            mock_site_context.pk, [learner.id], {quiz.id}
        ) == {first.id}

    def test_an_incomplete_sitting_is_never_a_first_attempt(self, mock_site_context):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        FormProgressFactory(user=learner, form=quiz, completed_time=None)

        assert (
            load_first_attempt_ids(mock_site_context.pk, [learner.id], {quiz.id})
            == set()
        )

    def test_two_learners_each_contribute_their_own_first_attempt(
        self, mock_site_context
    ):
        first_learner, second_learner = UserFactory(), UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        one = FormProgressFactory(
            user=first_learner, form=quiz, completed_time=timezone.now(), scores={}
        )
        two = FormProgressFactory(
            user=second_learner, form=quiz, completed_time=timezone.now(), scores={}
        )

        attempt_ids = load_first_attempt_ids(
            mock_site_context.pk, [first_learner.id, second_learner.id], {quiz.id}
        )

        assert attempt_ids == {one.id, two.id}

    def test_first_attempts_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )

        with django_assert_num_queries(1):
            load_first_attempt_ids(mock_site_context.pk, [learner.id], {quiz.id})


class TestLoadQuizQuestions:
    def test_questions_are_ordered_by_page_then_position(self, mock_site_context):
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        second_page = FormPageFactory(form=quiz, order=1)
        first_page = FormPageFactory(form=quiz, order=0)
        on_second = FormQuestionFactory(form_page=second_page, question="C", order=0)
        second_on_first = FormQuestionFactory(
            form_page=first_page, question="B", order=1
        )
        first_on_first = FormQuestionFactory(
            form_page=first_page, question="A", order=0
        )

        questions, _ = load_quiz_questions(mock_site_context.pk, {quiz.id})

        assert [question.id for question in questions] == [
            first_on_first.id,
            second_on_first.id,
            on_second.id,
        ]

    def test_the_options_map_is_drained_without_a_further_query(
        self, mock_site_context, django_assert_num_queries
    ):
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(form_page=page, order=0)
        QuestionOptionFactory(question=question, text="Mars", correct=True, order=0)

        # One for the questions, one for the prefetched options.
        with django_assert_num_queries(2):
            _, options = load_quiz_questions(mock_site_context.pk, {quiz.id})
            [option.text for option in options[question.id]]

    def test_a_question_on_another_site_is_excluded(self, mock_site_context):
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        page = FormPageFactory(form=quiz, order=0)
        FormQuestionFactory(form_page=page, order=0)
        other_site = SiteFactory(name="Other", domain="other.test")

        questions, _ = load_quiz_questions(other_site.pk, {quiz.id})

        assert questions == []


class TestLoadSelectedOptionsByPair:
    def test_a_survey_answer_is_excluded(self, mock_site_context):
        learner = UserFactory()
        survey = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
        survey_page = FormPageFactory(form=survey, order=0)
        survey_question = FormQuestionFactory(form_page=survey_page, order=0)
        survey_option = QuestionOptionFactory(
            question=survey_question, text="Confident", correct=None, order=0
        )
        sitting = FormProgressFactory(
            user=learner, form=survey, completed_time=timezone.now(), scores={}
        )
        QuestionAnswerFactory(
            form_progress=sitting, question=survey_question
        ).selected_options.add(survey_option)

        # The question id list carries only quiz questions, and it is that list
        # which keeps survey answers out of the quiz analysis.
        selected = load_selected_options_by_pair(mock_site_context.pk, [sitting.id], [])

        assert selected == {}

    def test_a_quiz_answer_carries_its_selected_options(self, mock_site_context):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(form_page=page, order=0)
        chosen = QuestionOptionFactory(
            question=question, text="Mars", correct=True, order=0
        )
        sitting = FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )
        QuestionAnswerFactory(
            form_progress=sitting, question=question
        ).selected_options.add(chosen)

        selected = load_selected_options_by_pair(
            mock_site_context.pk, [sitting.id], [question.id]
        )

        assert [option.text for option in selected[(sitting.id, question.id)]] == [
            "Mars"
        ]


class TestLoadDistractorRows:
    def _quiz_with_a_wrong_selection(self, *, correct: bool | None):
        learner = UserFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
        )
        option = QuestionOptionFactory(
            question=question, text="Chosen", correct=correct, order=0
        )
        sitting = FormProgressFactory(
            user=learner, form=quiz, completed_time=timezone.now(), scores={}
        )
        QuestionAnswerFactory(
            form_progress=sitting, question=question
        ).selected_options.add(option)
        return question, sitting

    def test_an_option_marked_correct_is_never_a_distractor(self, mock_site_context):
        question, sitting = self._quiz_with_a_wrong_selection(correct=True)

        rows = load_distractor_rows(mock_site_context.pk, [question.id], {sitting.id})

        assert rows == []

    def test_an_option_with_no_verdict_is_still_a_distractor(self, mock_site_context):
        """`correct` is nullable, and None must not read as 'not wrong'."""
        question, sitting = self._quiz_with_a_wrong_selection(correct=None)

        rows = load_distractor_rows(mock_site_context.pk, [question.id], {sitting.id})

        assert [(row["text"], row["times_selected"]) for row in rows] == [("Chosen", 1)]

    def test_a_selection_outside_the_first_attempts_is_not_counted(
        self, mock_site_context
    ):
        question, _ = self._quiz_with_a_wrong_selection(correct=False)

        rows = load_distractor_rows(mock_site_context.pk, [question.id], set())

        assert rows == []

    def test_distractors_are_ordered_most_selected_first(self, mock_site_context):
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
        )
        popular = QuestionOptionFactory(
            question=question, text="Popular", correct=False, order=0
        )
        rare = QuestionOptionFactory(
            question=question, text="Rare", correct=False, order=1
        )
        sittings = []
        for chosen in (popular, popular, rare):
            sitting = FormProgressFactory(
                user=UserFactory(),
                form=quiz,
                completed_time=timezone.now(),
                scores={},
            )
            QuestionAnswerFactory(
                form_progress=sitting, question=question
            ).selected_options.add(chosen)
            sittings.append(sitting)

        rows = load_distractor_rows(
            mock_site_context.pk, [question.id], {s.id for s in sittings}
        )

        assert [(row["text"], row["times_selected"]) for row in rows] == [
            ("Popular", 2),
            ("Rare", 1),
        ]


class TestResolveSiteName:
    def test_the_header_title_is_preferred_and_issues_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        with (
            override_settings(HEADER_TITLE="Bright Academy"),
            django_assert_num_queries(0),
        ):
            assert resolve_site_name(mock_site_context.pk) == "Bright Academy"

    def test_the_site_row_is_read_when_no_header_title_is_set(
        self, mock_site_context, django_assert_num_queries
    ):
        with override_settings(HEADER_TITLE=None), django_assert_num_queries(1):
            assert resolve_site_name(mock_site_context.pk) == mock_site_context.name


def _cohort_with_one_completed_quiz(*, learner_count: int):
    """One course, one topic and one two-question quiz every learner has sat."""
    cohort = CohortFactory()
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)
    topic = TopicFactory()
    _attach(course, topic, order=0)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    _attach(course, quiz, order=1)
    page = FormPageFactory(form=quiz, order=0)
    questions = [
        FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=index
        )
        for index in range(2)
    ]
    correct_options = [
        QuestionOptionFactory(question=question, text="Right", correct=True, order=0)
        for question in questions
    ]
    for _ in range(learner_count):
        learner = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=learner)
        TopicProgressFactory(user=learner, topic=topic, complete_time=timezone.now())
        sitting = FormProgressFactory(
            user=learner,
            form=quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        for question, option in zip(questions, correct_options, strict=True):
            QuestionAnswerFactory(
                form_progress=sitting, question=question
            ).selected_options.add(option)
    return cohort


def _load_everything(cohort, site_id):
    """Every loader run once, exactly as the orchestrator runs them."""
    registrations = load_registrations(cohort, site_id)
    roster = load_roster(cohort, site_id)
    catalogue = build_course_catalogue(registrations)
    progress = load_progress_index(site_id, roster.learner_ids, catalogue)
    first_attempt_ids = load_first_attempt_ids(
        site_id, roster.learner_ids, catalogue.quiz_form_ids
    )
    questions = build_question_index(
        *load_quiz_questions(site_id, catalogue.quiz_form_ids)
    )
    sat = build_sat_questions(
        questions,
        progress.forms,
        load_selected_options_by_pair(
            site_id, progress.forms.completed_attempt_ids, questions.question_ids
        ),
    )
    distractors = index_distractors(
        load_distractor_rows(site_id, questions.question_ids, first_attempt_ids),
        questions,
    )
    tallies = tally_quiz_answers(sat, progress.forms, first_attempt_ids)
    return {
        "registrations": registrations,
        "roster": roster,
        "catalogue": catalogue,
        "progress": progress,
        "questions": questions,
        "tallies": tallies,
        "distractors": distractors,
    }


class TestTheAssemblyStageIssuesNoQueriesOnRealRows:
    """The gap the pure tests structurally cannot cover.

    Hand-built instances arrive with their FK cache already populated, so a
    lost `select_related` would leave every pure test passing while production
    lazy-loaded once per row. These drive the same assembly over rows that came
    out of a real queryset.
    """

    def test_building_course_sections_from_loaded_rows_issues_no_queries(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = _cohort_with_one_completed_quiz(learner_count=2)
        loaded = _load_everything(cohort, mock_site_context.pk)
        confusions = build_confusions_by_quiz(
            loaded["catalogue"].quiz_form_ids,
            loaded["questions"],
            loaded["tallies"],
            loaded["distractors"],
        )

        with django_assert_num_queries(0):
            sections = [
                _build_course_section(
                    reg,
                    loaded["roster"],
                    loaded["catalogue"],
                    loaded["progress"],
                    confusions,
                    10,
                )
                for reg in loaded["registrations"]
            ]

        assert [row.completion_percentage for row in sections[0].learner_rows] == [
            100,
            100,
        ]

    def test_building_learner_details_from_loaded_rows_issues_no_queries(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = _cohort_with_one_completed_quiz(learner_count=2)
        loaded = _load_everything(cohort, mock_site_context.pk)
        wrong_answers = build_wrong_answers_by_user_quiz(
            loaded["tallies"], loaded["questions"]
        )
        now = timezone.now()

        with django_assert_num_queries(0):
            details = [
                _build_learner_detail(
                    user_id,
                    loaded["roster"],
                    loaded["catalogue"],
                    loaded["progress"],
                    wrong_answers,
                    now,
                )
                for user_id in loaded["roster"].learner_ids
            ]

        assert [detail.quiz_results[0].attempt_count for detail in details] == [1, 1]
