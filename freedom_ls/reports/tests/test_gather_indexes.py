"""Tests for the individual query loaders in freedom_ls.reports.indexes.

These cover what the pure tests in test_gather_helpers.py structurally cannot:
the orderings, `select_related` calls and site filters that only exist in SQL,
and the per-loader query counts. A per-loader count says *which* stage
regressed, where the whole-function bound in test_gather.py only says that one
did.
"""

from __future__ import annotations

import io

import pytest
import time_machine
from PIL import Image

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import (
    ActivityFactory,
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
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.validators import MAX_BYTES, MAX_DIMENSION
from freedom_ls.reports.gather import (
    _build_course_section,
    _build_learner_detail,
    build_confusions_by_quiz,
    build_wrong_answers_by_learner_quiz,
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
    load_organisation_logo_data_uri,
    load_progress_index,
    load_quiz_questions,
    load_registrations,
    load_roster,
    load_selected_options_by_pair,
    load_topic_progress_rows,
    resolve_site_name,
)
from freedom_ls.reports.tests.conftest import (
    cohort_progress_record,
    form_progress,
    individual_progress_record,
    topic_progress,
)
from freedom_ls.tests.images import break_png_chunk_crc

pytestmark = pytest.mark.django_db


def _attach(collection: object, child: object, order: int = 0) -> None:
    ContentCollectionItemFactory(
        collection_object=collection, child_object=child, order=order
    )


def _png_bytes(width: int = 20, height: int = 20) -> bytes:
    """A genuine, uncompressed-content PNG, so truncating it corrupts real data."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 20, height: int = 20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(30, 90, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def _gif_bytes(width: int = 20, height: int = 20) -> bytes:
    """A decodable image in a format the logo allowlist does not carry."""
    buf = io.BytesIO()
    Image.new("P", (width, height), color=3).save(buf, format="GIF")
    return buf.getvalue()


def _cohort_registered_for(
    course: Course, *, learner_count: int = 1
) -> tuple[CohortCourseRegistration, list[CourseProgress]]:
    """A cohort registered for `course`, and one record per member.

    Every loader below reads through the record, so a member with no record
    has nothing for them to find.
    """
    cohort = CohortFactory()
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )
    records = []
    for _ in range(learner_count):
        user = UserFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=user)
        records.append(cohort_progress_record(registration, user))
    return registration, records


def _second_record_for(record: CourseProgress) -> CourseProgress:
    """The same learner's own registration for the same course, and its record."""
    return individual_progress_record(
        LearnerCourseRegistrationFactory(
            learner=record.learner, collection=record.course
        )
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
        zeta = CohortMembershipFactory(
            cohort=cohort, learner__user=UserFactory(first_name="Ada", last_name="Zeta")
        )
        alpha = CohortMembershipFactory(
            cohort=cohort, learner__user=UserFactory(first_name="Bo", last_name="Alpha")
        )

        roster = load_roster(cohort, mock_site_context.pk)

        assert roster.learner_ids == [alpha.learner_id, zeta.learner_id]

    def test_the_roster_is_keyed_on_the_learner_and_carries_the_user(
        self, mock_site_context
    ):
        """The key moved to the Learner; the value is still what the report prints."""
        cohort = CohortFactory()
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        membership = CohortMembershipFactory(cohort=cohort, learner__user=user)

        roster = load_roster(cohort, mock_site_context.pk)

        assert roster.learners_by_id == {membership.learner_id: user}

    def test_a_learner_with_no_surname_is_keyed_by_their_email(self, mock_site_context):
        cohort = CohortFactory()
        membership = CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(
                first_name="", last_name="", email="aaa@example.test"
            ),
        )

        roster = load_roster(cohort, mock_site_context.pk)

        assert roster.sort_key_by_id[membership.learner_id] == ("aaa@example.test", "")

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
        course = CourseFactory()
        topic = TopicFactory()
        _attach(course, topic)
        registration, (record, other_record) = _cohort_registered_for(
            course, learner_count=2
        )
        topic_progress(record, topic, complete_time=timezone.now())
        topic_progress(other_record, topic, complete_time=timezone.now())

        rows = load_topic_progress_rows(
            mock_site_context.pk, [registration], [record.learner_id], {topic.id}
        )

        assert [row[0] for row in rows] == [record.learner_id]

    def test_a_row_under_another_registration_is_not_read(self, mock_site_context):
        """The same person, the same topic, their own separate enrolment."""
        course = CourseFactory()
        topic = TopicFactory()
        _attach(course, topic)
        registration, (record,) = _cohort_registered_for(course)
        topic_progress(_second_record_for(record), topic, complete_time=timezone.now())

        rows = load_topic_progress_rows(
            mock_site_context.pk, [registration], [record.learner_id], {topic.id}
        )

        assert rows == []

    def test_rows_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        course = CourseFactory()
        topic = TopicFactory()
        _attach(course, topic)
        registration, (record,) = _cohort_registered_for(course)
        topic_progress(record, topic, complete_time=timezone.now())

        with django_assert_num_queries(1):
            load_topic_progress_rows(
                mock_site_context.pk, [registration], [record.learner_id], {topic.id}
            )


class TestLoadFormProgressRows:
    def test_completed_sittings_arrive_newest_first(self, mock_site_context):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            older = form_progress(
                record, quiz, completed_time=timezone.now(), scores={}
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            newer = form_progress(
                record, quiz, completed_time=timezone.now(), scores={}
            )

        rows = load_form_progress_rows(
            mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
        )

        assert [row.id for row in rows] == [newer.id, older.id]

    def test_an_incomplete_sitting_sorts_after_every_completed_one(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        started = form_progress(record, quiz, completed_time=None)
        done = form_progress(record, quiz, completed_time=timezone.now(), scores={})

        rows = load_form_progress_rows(
            mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
        )

        assert [row.id for row in rows] == [done.id, started.id]

    def test_a_sitting_under_another_registration_is_not_read(self, mock_site_context):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        form_progress(
            _second_record_for(record),
            quiz,
            completed_time=timezone.now(),
            scores={},
        )

        rows = load_form_progress_rows(
            mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
        )

        assert rows == []

    def test_reading_each_rows_form_and_record_issues_no_further_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """select_related down the course_attempt chain keeps the fold query-free."""
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        form_progress(record, quiz, completed_time=timezone.now(), scores={})
        form_progress(record, quiz, completed_time=timezone.now(), scores={})

        with django_assert_num_queries(1):
            rows = load_form_progress_rows(
                mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
            )
            [
                (
                    row.form.quiz_pass_percentage,
                    row.course_attempt.course_progress.learner_id,
                )
                for row in rows
            ]


class TestLoadFirstAttemptIds:
    def test_only_the_earliest_completed_sitting_per_learner_and_quiz_is_returned(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            first = form_progress(
                record, quiz, completed_time=timezone.now(), scores={}
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            form_progress(record, quiz, completed_time=timezone.now(), scores={})

        assert load_first_attempt_ids(
            mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
        ) == {first.id}

    def test_an_earlier_sitting_under_another_registration_is_not_the_first(
        self, mock_site_context
    ):
        """A sitting outside the report's registrations is not in scope at all,
        so it cannot be the first -- the registration filter excludes it before
        the ranking ever sees it."""
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        other_record = _second_record_for(record)
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            form_progress(other_record, quiz, completed_time=timezone.now(), scores={})
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            here = form_progress(record, quiz, completed_time=timezone.now(), scores={})

        assert load_first_attempt_ids(
            mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
        ) == {here.id}

    def test_an_incomplete_sitting_is_never_a_first_attempt(self, mock_site_context):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        form_progress(record, quiz, completed_time=None)

        assert (
            load_first_attempt_ids(
                mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
            )
            == set()
        )

    def test_two_learners_each_contribute_their_own_first_attempt(
        self, mock_site_context
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (first_record, second_record) = _cohort_registered_for(
            course, learner_count=2
        )
        one = form_progress(
            first_record, quiz, completed_time=timezone.now(), scores={}
        )
        two = form_progress(
            second_record, quiz, completed_time=timezone.now(), scores={}
        )

        attempt_ids = load_first_attempt_ids(
            mock_site_context.pk,
            [registration],
            [first_record.learner_id, second_record.learner_id],
            {quiz.id},
        )

        assert attempt_ids == {one.id, two.id}

    def test_one_quiz_placed_in_two_of_the_cohorts_courses_yields_one_first_attempt(
        self, mock_site_context
    ):
        """The tally keys its cohort-wide counts on (learner, form), so a second
        first attempt for the same pair would count that learner twice in the
        confusion percentages."""
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        first_course = CourseFactory(title="First", slug="first")
        second_course = CourseFactory(title="Second", slug="second")
        _attach(first_course, quiz)
        _attach(second_course, quiz)

        registration, (record,) = _cohort_registered_for(first_course)
        second_registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
            cohort=registration.cohort, collection=second_course
        )
        second_record = cohort_progress_record(second_registration, record.learner.user)

        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            earliest = form_progress(
                record, quiz, completed_time=timezone.now(), scores={}
            )
        with time_machine.travel("2026-01-02T00:00:00Z", tick=False):
            form_progress(second_record, quiz, completed_time=timezone.now(), scores={})

        assert load_first_attempt_ids(
            mock_site_context.pk,
            [registration, second_registration],
            [record.learner_id],
            {quiz.id},
        ) == {earliest.id}

    def test_first_attempts_are_read_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        registration, (record,) = _cohort_registered_for(course)
        form_progress(record, quiz, completed_time=timezone.now(), scores={})

        with django_assert_num_queries(1):
            load_first_attempt_ids(
                mock_site_context.pk, [registration], [record.learner_id], {quiz.id}
            )


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
        course = CourseFactory()
        survey = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
        _attach(course, survey)
        survey_page = FormPageFactory(form=survey, order=0)
        survey_question = FormQuestionFactory(form_page=survey_page, order=0)
        survey_option = QuestionOptionFactory(
            question=survey_question, text="Confident", correct=None, order=0
        )
        _registration, (record,) = _cohort_registered_for(course)
        sitting = form_progress(
            record, survey, completed_time=timezone.now(), scores={}
        )
        QuestionAnswerFactory(
            form_progress=sitting, question=survey_question
        ).selected_options.add(survey_option)

        # The question id list carries only quiz questions, and it is that list
        # which keeps survey answers out of the quiz analysis.
        selected = load_selected_options_by_pair(mock_site_context.pk, [sitting.id], [])

        assert selected == {}

    def test_a_quiz_answer_carries_its_selected_options(self, mock_site_context):
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(form_page=page, order=0)
        chosen = QuestionOptionFactory(
            question=question, text="Mars", correct=True, order=0
        )
        _registration, (record,) = _cohort_registered_for(course)
        sitting = form_progress(record, quiz, completed_time=timezone.now(), scores={})
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
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
        page = FormPageFactory(form=quiz, order=0)
        question = FormQuestionFactory(
            form_page=page, type=QuestionType.MULTIPLE_CHOICE, order=0
        )
        option = QuestionOptionFactory(
            question=question, text="Chosen", correct=correct, order=0
        )
        _registration, (record,) = _cohort_registered_for(course)
        sitting = form_progress(record, quiz, completed_time=timezone.now(), scores={})
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
        course = CourseFactory()
        quiz = FormFactory(strategy=FormStrategy.QUIZ)
        _attach(course, quiz)
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
        _registration, records = _cohort_registered_for(course, learner_count=3)
        sittings = []
        for record, chosen in zip(records, (popular, popular, rare), strict=True):
            sitting = form_progress(
                record, quiz, completed_time=timezone.now(), scores={}
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
    course = CourseFactory()
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
    registration, records = _cohort_registered_for(course, learner_count=learner_count)
    for record in records:
        topic_progress(record, topic, complete_time=timezone.now())
        sitting = form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        for question, option in zip(questions, correct_options, strict=True):
            QuestionAnswerFactory(
                form_progress=sitting, question=question
            ).selected_options.add(option)
    return registration.cohort


def _load_everything(cohort, site_id):
    """Every loader run once, exactly as the orchestrator runs them."""
    registrations = load_registrations(cohort, site_id)
    roster = load_roster(cohort, site_id)
    catalogue = build_course_catalogue(registrations)
    progress = load_progress_index(
        site_id, registrations, roster.learner_ids, catalogue
    )
    first_attempt_ids = load_first_attempt_ids(
        site_id, registrations, roster.learner_ids, catalogue.quiz_form_ids
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
        wrong_answers = build_wrong_answers_by_learner_quiz(
            loaded["tallies"], loaded["questions"]
        )
        now = timezone.now()

        with django_assert_num_queries(0):
            details = [
                _build_learner_detail(
                    learner_id,
                    loaded["roster"],
                    loaded["catalogue"],
                    loaded["progress"],
                    wrong_answers,
                    now,
                )
                for learner_id in loaded["roster"].learner_ids
            ]

        assert [detail.quiz_results[0].attempt_count for detail in details] == [1, 1]


def test_pathless_storage_raises_on_path_access(pathless_logo_storage):
    """The storage double itself raises, proven independently of the loader.

    Without this, a later change that quietly stops PathlessFileSystemStorage
    raising on `.path()` would go unnoticed until it stopped catching a real
    S3 break -- the double is only as good as this test says it still is.
    """
    with pytest.raises(NotImplementedError):
        pathless_logo_storage.path("whatever.png")


def test_the_logo_field_reads_through_the_pathless_double(
    mock_site_context, pathless_logo_storage
):
    """The double is bound to the field, not merely configured in settings.

    A FileField keeps the Storage its `storage=` callable returned at import,
    so an override that only reassigns settings.STORAGES leaves the field on
    the real backend and every `.path()` claim below silently proves nothing.
    """
    organisation = OrganisationFactory()

    assert organisation.logo.storage is pathless_logo_storage


class TestLoadOrganisationLogoDataUri:
    def test_reads_a_logo_without_calling_storage_path(
        self, mock_site_context, pathless_logo_storage
    ):
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(_png_bytes()))

        data_uri = load_organisation_logo_data_uri(organisation)

        assert data_uri is not None
        assert data_uri.startswith("data:image/png;base64,")

    def test_an_organisation_with_no_logo_returns_none(
        self, mock_site_context, pathless_logo_storage
    ):
        organisation = OrganisationFactory()

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_missing_file_falls_back_to_none(self, mock_site_context):
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(_png_bytes()))
        organisation.logo.storage.delete(organisation.logo.name)

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_file_that_is_not_an_image_returns_none(self, mock_site_context):
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(b"not an image"))

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_file_over_the_size_cap_returns_none(self, mock_site_context):
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(b"x" * (MAX_BYTES + 1)))

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_bomb_in_the_error_band_returns_none(
        self, mock_site_context, monkeypatch
    ):
        # Image.open() runs its bomb check against header dimensions, so a
        # small image plus a small limit reproduces the bomb case without
        # storing an actual enormous file, mirroring
        # test_decompression_bomb_in_the_error_band_is_rejected in
        # organisations/tests/test_validators.py.
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(_png_bytes(20, 20)))

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_bomb_in_the_warning_band_returns_none(
        self, mock_site_context, monkeypatch
    ):
        """Between MAX_IMAGE_PIXELS and twice it, Pillow only warns.

        A warning does nothing in production unless it is escalated, so this
        band is the one an unvalidated upload actually reaches: the file
        decodes, gets embedded, and WeasyPrint allocates the full bitmap in
        the report worker.
        """
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
        organisation = OrganisationFactory()
        # 144px: over the ceiling, under twice it.
        organisation.logo.save("logo.png", ContentFile(_png_bytes(12, 12)))

        assert load_organisation_logo_data_uri(organisation) is None

    def test_dimensions_over_the_cap_return_none(self, mock_site_context):
        organisation = OrganisationFactory()
        organisation.logo.save(
            "logo.png", ContentFile(_png_bytes(MAX_DIMENSION + 1, 10))
        )

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_decodable_but_disallowed_format_returns_none(self, mock_site_context):
        organisation = OrganisationFactory()
        # A real GIF: Pillow decodes it happily, but it is not one of the
        # formats the upload path allows, so it must not be embedded either.
        organisation.logo.save("logo.gif", ContentFile(_gif_bytes()))

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_jpeg_gets_the_jpeg_mediatype(self, mock_site_context):
        organisation = OrganisationFactory()
        # Named .png despite genuine JPEG bytes: the mediatype must come from
        # decoding the bytes, not from the stored filename's extension.
        organisation.logo.save("logo.png", ContentFile(_jpeg_bytes()))

        data_uri = load_organisation_logo_data_uri(organisation)

        assert data_uri is not None
        assert data_uri.startswith("data:image/jpeg;base64,")

    def test_a_png_with_a_corrupt_chunk_returns_none(self, mock_site_context):
        """A checksum failure degrades to the wordmark rather than killing the render.

        Pillow reports it as a SyntaxError, which is not one of the families
        `check_logo_safety` would otherwise convert -- so an unvalidated object
        that reached storage would take the whole report down with it.
        """
        organisation = OrganisationFactory()
        organisation.logo.save(
            "logo.png", ContentFile(break_png_chunk_crc(_png_bytes(64, 32)))
        )

        assert load_organisation_logo_data_uri(organisation) is None

    def test_an_oversized_object_is_never_opened(
        self, mock_site_context, pathless_logo_storage, monkeypatch
    ):
        """The stored size is what rejects it, before any bytes are fetched.

        S3Storage downloads the whole object the moment the handle is touched,
        so a byte count taken after reading has already paid for the transfer
        -- which is the entire cost the cap exists to avoid.
        """
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(_png_bytes(64, 32)))
        monkeypatch.setattr(pathless_logo_storage, "size", lambda name: MAX_BYTES + 1)
        monkeypatch.setattr(
            pathless_logo_storage,
            "open",
            lambda *args, **kwargs: pytest.fail("the oversized object was fetched"),
        )

        assert load_organisation_logo_data_uri(organisation) is None

    def test_a_truncated_image_body_returns_none(self, mock_site_context):
        organisation = OrganisationFactory()
        truncated = _png_bytes(64, 64)
        truncated = truncated[: len(truncated) * 2 // 3]
        organisation.logo.save("logo.png", ContentFile(truncated))

        assert load_organisation_logo_data_uri(organisation) is None
