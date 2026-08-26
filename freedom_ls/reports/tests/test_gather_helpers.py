"""Tests for the individual query-free helpers in freedom_ls.reports.gather.

No `django_db` marker anywhere in this file, deliberately. pytest-django blocks
database access in unmarked tests, so every test here doubles as proof that the
helper it covers issues no queries -- the guarantee the single whole-function
query bound in test_gather.py cannot give per function.

Inputs come from `gather_input_builders`, which hands back real but unsaved
model instances. See its docstring for why unsaved is enough.
"""

from __future__ import annotations

import pytest

from freedom_ls.form_engine.models import QuestionType
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
    build_wrong_answers_by_user_quiz,
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
    OTHER_USER_ID,
    USER_ID,
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


def _a_column(title: str = "A Quiz") -> QuizColumn:
    return QuizColumn(
        form_id=a_quiz(title).id, title=title, abbreviation="AQ", pass_percentage=50
    )


def _a_learner_row(
    *,
    user_id: int = USER_ID,
    completion: int = 0,
    columns: list[QuizColumn] | None = None,
) -> LearnerRow:
    """A row carrying an (empty) cell for each of `columns`, as gather builds it."""
    return LearnerRow(
        user_id=user_id,
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
        user_id=USER_ID,
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

    def test_the_cohort_line_fits_the_margin_box_alongside_its_label(self) -> None:
        second_line = FOOTER_COHORT_MAX_CHARS + len(" · Cohort progress report")

        assert second_line <= FOOTER_LINE_MAX_CHARS


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

        assert _completion_counts(items, USER_ID, a_progress_index()) == (0, 2)

    def test_a_completed_topic_counts_toward_the_completed_total(self) -> None:
        topic = a_topic()
        progress = a_progress_index(completed_topic_ids_by_user={USER_ID: {topic.id}})

        assert _completion_counts([topic], USER_ID, progress) == (1, 1)

    def test_a_completed_form_counts_toward_the_completed_total(self) -> None:
        quiz = a_quiz()
        progress = a_progress_index(completed_form_ids_by_user={USER_ID: {quiz.id}})

        assert _completion_counts([quiz], USER_ID, progress) == (1, 1)

    def test_another_learners_completions_are_not_counted(self) -> None:
        topic = a_topic()
        progress = a_progress_index(
            completed_topic_ids_by_user={OTHER_USER_ID: {topic.id}}
        )

        assert _completion_counts([topic], USER_ID, progress) == (0, 1)

    def test_an_empty_item_list_is_zero_of_zero(self) -> None:
        assert _completion_counts([], USER_ID, a_progress_index()) == (0, 0)


class TestLatestCompletion:
    def test_the_most_recent_completion_wins(self) -> None:
        early, late = a_topic("Early"), a_topic("Late")
        progress = a_progress_index(
            topic_complete_time={(USER_ID, early.id): JAN_1, (USER_ID, late.id): JAN_2}
        )

        assert _latest_completion([early, late], USER_ID, progress) == ("Late", JAN_2)

    def test_a_topic_and_a_form_compete_on_timestamp_alone(self) -> None:
        topic = a_topic("Stars")
        quiz = a_quiz("Astronomy Quiz")
        attempt = an_attempt(quiz, completed_time=JAN_1)
        progress = a_progress_index(
            topic_complete_time={(USER_ID, topic.id): JAN_2},
            latest_by_user_form={(USER_ID, quiz.id): attempt},
            completed_attempts_by_user_form={(USER_ID, quiz.id): [attempt]},
        )

        assert _latest_completion([topic, quiz], USER_ID, progress) == ("Stars", JAN_2)

    def test_a_form_with_no_completed_attempt_is_ignored(self) -> None:
        quiz = a_quiz("Astronomy Quiz")
        started = an_attempt(quiz, completed_time=None)
        progress = a_progress_index(latest_by_user_form={(USER_ID, quiz.id): started})

        assert _latest_completion([quiz], USER_ID, progress) == (None, None)

    def test_a_learner_with_no_completions_has_no_title_and_no_time(self) -> None:
        assert _latest_completion([a_topic()], USER_ID, a_progress_index()) == (
            None,
            None,
        )


class TestCompletedItems:
    def test_an_uncompleted_topic_is_absent(self) -> None:
        assert _completed_items([a_topic()], USER_ID, a_progress_index()) == []

    def test_a_completed_topic_is_not_marked_as_a_quiz(self) -> None:
        topic = a_topic("Stars")
        progress = a_progress_index(topic_complete_time={(USER_ID, topic.id): JAN_1})

        completed = _completed_items([topic], USER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [("Stars", False)]

    def test_a_quiz_form_is_marked_as_a_quiz(self) -> None:
        quiz = a_quiz("Astronomy Quiz")
        progress = attempted(quiz, [an_attempt(quiz, completed_time=JAN_1)])

        completed = _completed_items([quiz], USER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [
            ("Astronomy Quiz", True)
        ]

    def test_a_survey_form_is_not_marked_as_a_quiz(self) -> None:
        survey = a_survey("Confidence Survey")
        progress = attempted(survey, [an_attempt(survey, completed_time=JAN_1)])

        completed = _completed_items([survey], USER_ID, progress)

        assert [(item.title, item.is_quiz) for item in completed] == [
            ("Confidence Survey", False)
        ]

    def test_items_are_returned_in_the_order_the_course_lists_them(self) -> None:
        first, second = a_topic("First"), a_topic("Second")
        progress = a_progress_index(
            topic_complete_time={
                (USER_ID, first.id): JAN_2,
                (USER_ID, second.id): JAN_1,
            }
        )

        completed = _completed_items([first, second], USER_ID, progress)

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

        assert _quiz_result_for(USER_ID, quiz, a_progress_index().forms) is None

    def test_attempts_are_numbered_from_one_in_list_order(self) -> None:
        quiz = a_quiz(pass_percentage=50)
        attempts = [
            an_attempt(quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 2}),
            an_attempt(quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 2}),
            an_attempt(quiz, completed_time=JAN_3, scores={"score": 2, "max_score": 2}),
        ]
        progress = attempted(quiz, attempts)

        result = _quiz_result_for(USER_ID, quiz, progress.forms)

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

        result = _quiz_result_for(USER_ID, quiz, progress.forms)

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

        result = _quiz_result_for(USER_ID, quiz, attempted(quiz, attempts).forms)

        assert result is not None
        assert result.attempt_count == len(result.attempts) == 2


class TestFoldTopicProgressRows:
    def test_a_row_with_no_complete_time_still_marks_the_learner_active(self) -> None:
        topic = a_topic()

        index = fold_topic_progress_rows([(USER_ID, topic.id, None)])

        assert index.user_ids_seen == {USER_ID}
        assert index.completed_topic_ids_by_user.get(USER_ID, set()) == set()

    def test_a_completed_topic_is_indexed_against_its_learner(self) -> None:
        topic = a_topic()

        index = fold_topic_progress_rows([(USER_ID, topic.id, JAN_1)])

        assert index.completed_topic_ids_by_user[USER_ID] == {topic.id}
        assert index.complete_time[(USER_ID, topic.id)] == JAN_1


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

        assert index.latest_by_user_form[(USER_ID, quiz.id)] is newest

    def test_attempts_are_returned_oldest_first(self) -> None:
        quiz = a_quiz()
        newest = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 1, "max_score": 1}
        )
        oldest = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 1, "max_score": 1}
        )

        index = fold_form_progress_rows([newest, oldest])

        assert index.completed_attempts_by_user_form[(USER_ID, quiz.id)] == [
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

        assert index.completed_attempts_by_user_form[(USER_ID, quiz.id)] == [done]

    def test_a_failed_latest_attempt_does_not_complete_the_form(self) -> None:
        quiz = a_quiz(pass_percentage=80)
        failed_retry = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 0, "max_score": 2}
        )
        passed_first = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 2, "max_score": 2}
        )

        index = fold_form_progress_rows([failed_retry, passed_first])

        assert index.completed_form_ids_by_user.get(USER_ID, set()) == set()

    def test_a_passed_latest_attempt_completes_the_form(self) -> None:
        quiz = a_quiz(pass_percentage=80)
        passed_retry = an_attempt(
            quiz, completed_time=JAN_2, scores={"score": 2, "max_score": 2}
        )
        failed_first = an_attempt(
            quiz, completed_time=JAN_1, scores={"score": 0, "max_score": 2}
        )

        index = fold_form_progress_rows([passed_retry, failed_first])

        assert index.completed_form_ids_by_user[USER_ID] == {quiz.id}

    def test_a_survey_is_completed_by_any_sitting(self) -> None:
        survey = a_survey()
        sitting = an_attempt(survey, completed_time=JAN_1, scores={"Confidence": 3})

        index = fold_form_progress_rows([sitting])

        assert index.completed_form_ids_by_user[USER_ID] == {survey.id}

    def test_every_sitting_resolves_to_its_learner_and_form(self) -> None:
        survey = a_survey()
        sitting = an_attempt(survey, completed_time=JAN_1, scores={"Confidence": 3})

        index = fold_form_progress_rows([sitting])

        assert index.user_form_by_attempt_id[sitting.id] == (USER_ID, survey.id)


class TestMergeProgressIndexes:
    def test_a_learner_seen_only_in_form_progress_still_counts_as_active(self) -> None:
        quiz = a_quiz()
        forms = fold_form_progress_rows([an_attempt(quiz, completed_time=None)])

        merged = merge_progress_indexes(fold_topic_progress_rows([]), forms)

        assert merged.user_ids_with_any_progress == {USER_ID}

    def test_a_learner_seen_only_in_topic_progress_still_counts_as_active(self) -> None:
        topics = fold_topic_progress_rows([(OTHER_USER_ID, a_topic().id, None)])

        merged = merge_progress_indexes(topics, fold_form_progress_rows([]))

        assert merged.user_ids_with_any_progress == {OTHER_USER_ID}


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
            user_form_by_attempt_id={
                newer.id: (USER_ID, quiz.id),
                older.id: (USER_ID, quiz.id),
            }
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(USER_ID, quiz.id, question.id)]
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
            user_form_by_attempt_id={attempt.id: (USER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        assert (USER_ID, quiz.id, question.id) not in tallies.wrong_selected_counts

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
            user_form_by_attempt_id={attempt.id: (USER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(USER_ID, quiz.id, question.id)]
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
            user_form_by_attempt_id={attempt.id: (USER_ID, quiz.id)}
        ).forms

        tallies = tally_quiz_answers(sat, forms, first_attempt_ids=set())

        counts = tallies.wrong_selected_counts[(USER_ID, quiz.id, question.id)]
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
                (USER_ID, quiz.id, second.id): 1,
                (USER_ID, quiz.id, first.id): 1,
            },
            wrong_selected_counts={
                (USER_ID, quiz.id, second.id): {},
                (USER_ID, quiz.id, first.id): {},
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        built = build_wrong_answers_by_user_quiz(tallies, index)

        assert [answer.question_number for answer in built[USER_ID][quiz.id]] == [1, 2]

    def test_each_answer_carries_its_questions_correct_option_texts(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        options = [an_option(question, "Mars", correct=True)]
        index = _a_question_index((question, options))
        tallies = QuizTallies(
            wrong_counts={(USER_ID, quiz.id, question.id): 2},
            wrong_selected_counts={
                (USER_ID, quiz.id, question.id): {("Sun", False): 2}
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        answer = build_wrong_answers_by_user_quiz(tallies, index)[USER_ID][quiz.id][0]

        assert answer.times_wrong == 2
        assert answer.selected_options == [SelectedOption("Sun", False, 2)]
        assert answer.correct_option_texts == ["Mars"]

    def test_selected_options_carry_each_options_own_correctness(self) -> None:
        quiz = a_quiz()
        question = a_question(quiz)
        options = [an_option(question, "Mars", correct=True)]
        index = _a_question_index((question, options))
        tallies = QuizTallies(
            wrong_counts={(USER_ID, quiz.id, question.id): 1},
            wrong_selected_counts={
                (USER_ID, quiz.id, question.id): {
                    ("Mars", True): 1,
                    ("Sun", False): 1,
                    ("Pluto", None): 1,
                }
            },
            respondent_counts={},
            wrong_counts_first={},
        )

        answer = build_wrong_answers_by_user_quiz(tallies, index)[USER_ID][quiz.id][0]

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
            wrong_counts={(USER_ID, quiz.id, question.id): 1},
            wrong_selected_counts={(USER_ID, quiz.id, question.id): {}},
            respondent_counts={},
            wrong_counts_first={},
        )

        built = build_wrong_answers_by_user_quiz(tallies, index)

        assert OTHER_USER_ID not in built


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
            completed_topic_ids_by_user={USER_ID: {topic.id}},
            topic_complete_time={(USER_ID, topic.id): JAN_1},
        )

        row = _build_learner_row(
            USER_ID,
            [topic, quiz],
            [],
            a_roster(learner),
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
            USER_ID,
            [quiz],
            [column],
            a_roster(learner),
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
