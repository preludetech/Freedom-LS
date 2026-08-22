"""Per-partial tests for the report templates.

Each partial is rendered directly via `render_to_string("reports/partials/<name>.html", {...})`
with a minimal hand-built context — a couple of `freedom_ls.reports.gather` dataclass
instances, never a whole `CohortReportData` built through the ORM. No database access
happens anywhere in this file, so none of these tests need `django_db` or
`mock_site_context`: the dataclasses under test are plain, frozen Python objects.

The whole-document tier is out of scope here: `build_report_html()` resolves fonts, the
theme bundle and the cover logo before it renders, and those are exercised in test_render.py.
"""

from __future__ import annotations

from uuid import uuid4

from django.template.loader import render_to_string

from freedom_ls.reports.gather import (
    AtRiskFlag,
    AttentionList,
    CompletedItem,
    ConfusionBlock,
    CourseSection,
    LearnerRow,
    QuizAttempt,
    QuizColumn,
    QuizConfusion,
    QuizResult,
    QuizWrongAnswers,
    SelectedOption,
    SummaryTable,
    WrongAnswer,
)
from freedom_ls.reports.tests.report_data_builders import (
    GENERATED_AT,
    cohort_report_data,
    course_section_defaults,
    learner_detail,
    summary_row,
)


def course_section_with_one_summary_table(
    quizzes: list[QuizColumn] | None = None,
    learner_rows: list[LearnerRow] | None = None,
    **overrides: object,
) -> CourseSection:
    """A course section whose single summary table covers every quiz it declares.

    Chunking a wide course across several tables is `gather`'s job and is
    tested there; a partial only ever renders the tables it is handed.
    """
    quizzes = quizzes or []
    learner_rows = learner_rows or []
    defaults = course_section_defaults()
    defaults["quizzes"] = quizzes
    defaults["learner_rows"] = learner_rows
    defaults["summary_tables"] = [
        SummaryTable(
            quizzes=quizzes,
            rows=[summary_row(row, quizzes) for row in learner_rows],
            continued=False,
        )
    ]
    defaults.update(overrides)
    return CourseSection(**defaults)


class TestFlagList:
    def test_renders_one_line_per_flag(self) -> None:
        flags = [
            AtRiskFlag(
                "no_activity",
                "No recorded activity",
                "Has not started any course item.",
                "warning",
            ),
            AtRiskFlag(
                "inactive",
                "No activity recently",
                "No activity recorded in over 7 days.",
                "warning",
            ),
        ]

        html = render_to_string("reports/partials/flag_list.html", {"flags": flags})

        assert html.count("Has not started any course item.") == 1
        assert html.count("No activity recorded in over 7 days.") == 1
        assert "No flags" not in html

    def test_renders_no_flags_when_empty(self) -> None:
        html = render_to_string("reports/partials/flag_list.html", {"flags": []})

        assert "No flags" in html


class TestCapDisclosure:
    def test_renders_nothing_when_shown_equals_total(self) -> None:
        html = render_to_string(
            "reports/partials/cap_disclosure.html",
            {"shown": 5, "total": 5, "noun": "learners flagged"},
        )

        assert html.strip() == ""

    def test_renders_sentence_with_numbers_when_capped(self) -> None:
        html = render_to_string(
            "reports/partials/cap_disclosure.html",
            {
                "shown": 10,
                "total": 23,
                "noun": "questions with at least one incorrect answer",
            },
        )

        assert "10" in html
        assert "23" in html
        assert "questions with at least one incorrect answer" in html


class TestQuizResultCell:
    def test_renders_dash_for_none_result(self) -> None:
        html = render_to_string(
            "reports/partials/quiz_result_cell.html", {"result": None}
        )

        assert "—" in html
        assert "✓" not in html

    def test_renders_score_and_pass_glyph(self) -> None:
        result = QuizResult(
            form_id=uuid4(),
            title="Quiz",
            latest_score=8,
            latest_max_score=10,
            latest_percentage=80,
            passed=True,
            attempt_count=2,
            completed_at=GENERATED_AT,
            attempts=[],
        )

        html = render_to_string(
            "reports/partials/quiz_result_cell.html", {"result": result}
        )

        assert "80%" in html
        assert "✓" in html
        assert "×2" in html  # noqa: RUF001 -- the actual attempt-count glyph the template renders

    def test_renders_fail_glyph_when_not_passed(self) -> None:
        result = QuizResult(
            form_id=uuid4(),
            title="Quiz",
            latest_score=3,
            latest_max_score=10,
            latest_percentage=30,
            passed=False,
            attempt_count=1,
            completed_at=GENERATED_AT,
            attempts=[],
        )

        html = render_to_string(
            "reports/partials/quiz_result_cell.html", {"result": result}
        )

        assert "✗" in html
        assert "✓" not in html

    def test_renders_no_verdict_glyph_when_passed_is_none(self) -> None:
        result = QuizResult(
            form_id=uuid4(),
            title="Quiz",
            latest_score=5,
            latest_max_score=10,
            latest_percentage=None,
            passed=None,
            attempt_count=1,
            completed_at=GENERATED_AT,
            attempts=[],
        )

        html = render_to_string(
            "reports/partials/quiz_result_cell.html", {"result": result}
        )

        assert "○" in html
        assert "✓" not in html
        assert "✗" not in html


class TestCompletionBar:
    def test_renders_percentage_and_counts(self) -> None:
        html = render_to_string(
            "reports/partials/completion_bar.html",
            {"percentage": 75, "completed": 3, "total": 4},
        )

        assert "75%" in html
        assert "3 of 4" in html
        assert "●" in html

    def test_renders_pass_glyph_at_100_percent(self) -> None:
        html = render_to_string(
            "reports/partials/completion_bar.html",
            {"percentage": 100, "completed": 4, "total": 4},
        )

        assert "✓" in html

    def test_renders_fail_glyph_at_zero_percent(self) -> None:
        html = render_to_string(
            "reports/partials/completion_bar.html",
            {"percentage": 0, "completed": 0, "total": 4},
        )

        assert "✗" in html

    def test_renders_no_course_items_instead_of_a_zero_denominator(self) -> None:
        html = render_to_string(
            "reports/partials/completion_bar.html",
            {"percentage": 0, "completed": 0, "total": 0},
        )

        assert "No course items" in html
        assert "0 of 0" not in html
        assert "✗" not in html
        assert "completion-bar-outer" not in html

    def test_fill_carries_the_percentage_as_an_inline_width(self) -> None:
        html = render_to_string(
            "reports/partials/completion_bar.html",
            {"percentage": 40, "completed": 2, "total": 5},
        )

        assert "completion-bar-inner" in html
        assert "width: 40%" in html


class TestAttentionEntry:
    def test_links_to_learner_anchor_and_shows_flags(self) -> None:
        learner = learner_detail(
            user_id=42,
            full_name="Alex Doe",
            flags=[
                AtRiskFlag(
                    "inactive",
                    "No activity recently",
                    "No activity recorded in over 7 days.",
                    "warning",
                )
            ],
        )

        html = render_to_string(
            "reports/partials/attention_entry.html", {"learner": learner}
        )

        assert 'href="#learner-42"' in html
        assert "Alex Doe" in html
        assert "No activity recently" in html


class TestTitlePage:
    def test_shows_cohort_name_courses_and_inactive_marker(self) -> None:
        data = cohort_report_data(
            courses=[
                course_section_with_one_summary_table(title="Course 1", is_active=True),
                course_section_with_one_summary_table(
                    title="Course 2", is_active=False
                ),
            ]
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "Cohort A" in html
        assert "Northside College" in html
        assert "Course 1" in html
        assert "Course 2" in html
        assert "inactive" in html.lower()
        assert "Jamie Educator" in html
        assert "2026" in html


class TestAtAGlance:
    def test_shows_stats_and_attention_list(self) -> None:
        learner = learner_detail(
            user_id=7,
            full_name="Sam Lee",
            flags=[
                AtRiskFlag(
                    "no_activity",
                    "No recorded activity",
                    "Has not started any course item.",
                    "warning",
                )
            ],
        )
        attention = AttentionList(learners=[learner], shown=1, total=1)
        data = cohort_report_data(
            cohort_size=20,
            median_completion=55,
            not_started_count=3,
            complete_count=2,
            attention_list=attention,
        )

        html = render_to_string(
            "reports/partials/at_a_glance.html", {"data": data, "attention": attention}
        )

        assert "20" in html
        assert "55%" in html
        assert "Sam Lee" in html

    def test_cap_disclosure_shown_when_capped(self) -> None:
        attention = AttentionList(learners=[], shown=12, total=18)
        data = cohort_report_data(attention_list=attention)

        html = render_to_string(
            "reports/partials/at_a_glance.html", {"data": data, "attention": attention}
        )

        assert "12" in html
        assert "18" in html

    def test_no_disclosure_when_not_capped(self) -> None:
        attention = AttentionList(learners=[], shown=0, total=0)
        data = cohort_report_data(attention_list=attention)

        html = render_to_string(
            "reports/partials/at_a_glance.html", {"data": data, "attention": attention}
        )

        assert "No learners currently flagged." in html


class TestContents:
    def test_links_to_course_and_learner_anchors(self) -> None:
        course = course_section_with_one_summary_table(title="Course X")
        learner = learner_detail(user_id=3, full_name="Robin Fox")
        data = cohort_report_data(courses=[course], learners=[learner])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#course-{course.course_id}"' in html
        assert 'href="#learner-3"' in html

    def test_links_to_confusion_block_when_present(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Y", abbreviation="QY", pass_percentage=50
        )
        confusion = QuizConfusion(
            question_number=1,
            question_text="Q?",
            respondent_count=5,
            wrong_count=2,
            show_percentage=False,
            wrong_percentage=None,
            distractors=[],
            correct_option_texts=["A"],
        )
        block = ConfusionBlock(questions=[confusion], shown=1, total=1)
        course = course_section_with_one_summary_table(
            quizzes=[quiz], confusions_by_quiz={quiz.form_id: block}
        )
        data = cohort_report_data(courses=[course])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#confusions-{quiz.form_id}"' in html

    def test_omits_confusion_link_when_block_empty(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Y", abbreviation="QY", pass_percentage=50
        )
        block = ConfusionBlock(questions=[], shown=0, total=0)
        course = course_section_with_one_summary_table(
            quizzes=[quiz], confusions_by_quiz={quiz.form_id: block}
        )
        data = cohort_report_data(courses=[course])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#confusions-{quiz.form_id}"' not in html


class TestMethodology:
    def test_legend_defines_every_status_glyph_the_report_draws(self) -> None:
        html = render_to_string("reports/partials/methodology.html", {})

        legend = html.split("Status legend")[1]
        assert {"✓", "✗", "▲", "●", "○", "—"} <= set(legend)

    def test_states_the_rules_the_figures_are_read_under(self) -> None:
        """Each figure in the report is defensible only against a stated rule, and
        the report travels without whoever generated it — an educator reading a
        printout has nowhere else to look these up.
        """
        html = render_to_string("reports/partials/methodology.html", {})

        assert "Recomputed from progress records every time" in html
        assert (
            "<strong>latest</strong> completed attempt, not their best or first" in html
        )
        assert "<strong>first</strong> completed attempt at a quiz only" in html
        assert "every correct option to be selected and no incorrect one" in html
        assert "carries a score but no verdict" in html
        assert "free-text questions carry no completion or correctness record" in html


class TestCourseSummaryTable:
    def test_shows_learner_rows_and_quiz_columns(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Z", abbreviation="QZ", pass_percentage=50
        )
        result = QuizResult(
            form_id=quiz.form_id,
            title="Quiz Z",
            latest_score=9,
            latest_max_score=10,
            latest_percentage=90,
            passed=True,
            attempt_count=1,
            completed_at=GENERATED_AT,
            attempts=[],
        )
        row = LearnerRow(
            user_id=5,
            full_name="Jesse Park",
            completion_percentage=80,
            completed_item_count=4,
            total_item_count=5,
            last_completed_title="Topic A",
            last_completed_at=GENERATED_AT,
            quiz_cells={quiz.form_id: result},
        )
        section = course_section_with_one_summary_table(
            title="Course Q", quizzes=[quiz], learner_rows=[row]
        )

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "Jesse Park" in html
        assert "QZ" in html
        assert "90%" in html
        assert f'id="course-{section.course_id}"' in html

    def test_marks_inactive_registration(self) -> None:
        section = course_section_with_one_summary_table(
            title="Course Inactive", is_active=False
        )

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "inactive" in html.lower()

    def test_shows_dash_for_unattempted_quiz_cell(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Z", abbreviation="QZ", pass_percentage=50
        )
        row = LearnerRow(
            user_id=5,
            full_name="Jesse Park",
            completion_percentage=0,
            completed_item_count=0,
            total_item_count=5,
            last_completed_title=None,
            last_completed_at=None,
            quiz_cells={quiz.form_id: None},
        )
        section = course_section_with_one_summary_table(
            quizzes=[quiz], learner_rows=[row]
        )

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "—" in html


class TestSummaryTables:
    def test_renders_landscape_wrapper_and_course_tables(self) -> None:
        section = course_section_with_one_summary_table(title="Course L")

        html = render_to_string(
            "reports/partials/summary_tables.html", {"courses": [section]}
        )

        assert "landscape-section" in html
        assert f'id="course-{section.course_id}"' in html
        assert "Course L" in html


class TestLearnerDetail:
    def test_renders_no_activity_recorded_when_the_learner_never_started(self) -> None:
        learner = learner_detail(has_any_progress=False)

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "No activity recorded" in html
        assert "nothing completed yet" not in html

    def test_renders_the_started_line_when_nothing_was_completed(self) -> None:
        """The section must never be an empty gap.

        A learner who opened an item without finishing it has a progress row, so
        `has_any_progress` is True, but none of the three lists the body draws
        from has anything in it.
        """
        learner = learner_detail(has_any_progress=True)

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Started, but nothing completed yet." in html
        assert "No activity recorded" not in html
        # The line sits above a "No flags" panel, so it must not be drawn in
        # the error tint the never-started line carries.
        assert "no-activity-started" in html

    def test_renders_activity_when_an_item_was_completed(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            completed_items=[
                CompletedItem(
                    title="Intro Topic", completed_at=GENERATED_AT, is_quiz=False
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "No activity recorded" not in html
        assert "nothing completed yet" not in html
        assert "Intro Topic" in html

    def test_renders_activity_when_only_a_quiz_was_attempted(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            quiz_results=[
                QuizResult(
                    form_id=uuid4(),
                    title="Voltage Quiz",
                    latest_score=9,
                    latest_max_score=14,
                    latest_percentage=64,
                    passed=True,
                    attempt_count=1,
                    completed_at=GENERATED_AT,
                    attempts=[
                        QuizAttempt(
                            attempt_number=1,
                            completed_at=GENERATED_AT,
                            score=9,
                            max_score=14,
                            percentage=64,
                            passed=True,
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "nothing completed yet" not in html
        assert "Voltage Quiz" in html

    def test_renders_activity_when_only_wrong_answers_were_recorded(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=3,
                            question_text="What is erosion?",
                            times_wrong=1,
                            selected_options=[SelectedOption("Option C", False, 1)],
                            correct_option_texts=["Option D"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "nothing completed yet" not in html
        assert "Incorrect answers — Erosion Quiz" in html

    def test_names_an_unanswered_question_rather_than_leaving_the_cell_blank(
        self,
    ) -> None:
        """A question left blank has nothing to quote back, so the cell has to say so."""
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=3,
                            question_text="What is erosion?",
                            times_wrong=1,
                            selected_options=[],
                            correct_option_texts=["Option D"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Not answered" in html

    def test_an_option_chosen_on_more_than_one_attempt_carries_its_count(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=3,
                            question_text="What is erosion?",
                            times_wrong=3,
                            selected_options=[
                                SelectedOption("Option C", False, 2),
                                SelectedOption("Option A", False, 1),
                            ],
                            correct_option_texts=["Option D"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert 'Option C <span class="chip-count">×2</span>' in html  # noqa: RUF001 -- the multiplication sign the template renders

    def test_an_option_chosen_once_carries_no_count(self) -> None:
        """A question missed once has every option at a count of one, so the badge
        would put a number on the common case that carries no information."""
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=3,
                            question_text="What is erosion?",
                            times_wrong=1,
                            selected_options=[SelectedOption("Option C", False, 1)],
                            correct_option_texts=["Option D"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Option C" in html
        assert "chip-count" not in html

    def test_a_correctly_ticked_option_is_not_painted_as_a_mistake(self) -> None:
        """On a multi-select question the learner's right ticks sit inside a wrong
        answer, and painting them red would contradict the correct-answer column
        two cells to the right."""
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=2,
                            question_text="Which two apply?",
                            times_wrong=1,
                            selected_options=[
                                SelectedOption("Option A", True, 1),
                                SelectedOption("Option C", False, 1),
                            ],
                            correct_option_texts=["Option A", "Option B"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert (
            '<span class="chip chip-success"><span class="chip-glyph">✓</span>Option A'
            in html
        )
        assert (
            '<span class="chip chip-error"><span class="chip-glyph">✗</span>Option C'
            in html
        )

    def test_an_option_the_author_never_marked_up_carries_no_verdict(self) -> None:
        """`correct` is nullable. An unmarked option is not right, but calling it
        wrong would assert a verdict the course author never gave."""
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=2,
                            question_text="Which two apply?",
                            times_wrong=1,
                            selected_options=[SelectedOption("Option E", None, 1)],
                            correct_option_texts=["Option A"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert (
            '<span class="chip chip-neutral"><span class="chip-glyph">○</span>Option E'
            in html
        )

    def test_every_answer_chip_carries_a_glyph_so_greyscale_still_reads(self) -> None:
        """Tint is not the only signal anywhere else in the report, and these two
        columns sit side by side -- printed in greyscale they would otherwise be
        indistinguishable from one another."""
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=2,
                            question_text="Which two apply?",
                            times_wrong=1,
                            selected_options=[SelectedOption("Option C", False, 1)],
                            correct_option_texts=["Option A"],
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert html.count('class="chip-glyph"') == 2

    def test_renders_flags_at_the_top(self) -> None:
        learner = learner_detail(
            flags=[
                AtRiskFlag(
                    "no_activity",
                    "No recorded activity",
                    "Has not started any course item.",
                    "warning",
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "No recorded activity" in html
        assert "Has not started any course item." in html

    def test_emits_learner_anchor_id(self) -> None:
        learner = learner_detail(user_id=99)

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert 'id="learner-99"' in html

    def test_running_header_name_is_a_separate_element_from_the_heading(self) -> None:
        # The heading is the section's PDF bookmark and the span is the running
        # header; one element cannot be both, because print.css redraws the
        # running element on every page of the section and each redraw would
        # bookmark the learner again.
        learner = learner_detail(full_name="Robin Fox")

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert '<span class="learner-running-name">Robin Fox</span>' in html
        assert '<h3 class="learner-heading">Robin Fox</h3>' in html

    def test_wrong_answers_heading_names_its_quiz(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Voltage Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=8,
                            question_text="What is voltage?",
                            times_wrong=2,
                            selected_options=[SelectedOption("Option A", False, 1)],
                            correct_option_texts=["Option B"],
                        )
                    ],
                ),
                QuizWrongAnswers(
                    form_id=uuid4(),
                    title="Erosion Quiz",
                    answers=[
                        WrongAnswer(
                            question_number=3,
                            question_text="What is erosion?",
                            times_wrong=1,
                            selected_options=[SelectedOption("Option C", False, 1)],
                            correct_option_texts=["Option D"],
                        )
                    ],
                ),
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Incorrect answers — Voltage Quiz" in html
        assert "Incorrect answers — Erosion Quiz" in html
        assert "What is voltage?" in html
        assert "What is erosion?" in html

    def test_omits_wrong_answers_block_for_a_quiz_with_no_wrong_answers(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(form_id=uuid4(), title="Clean Quiz", answers=[])
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Incorrect answers" not in html


class TestLearnerDetails:
    def test_states_the_situation_when_the_cohort_has_no_learners(self) -> None:
        html = render_to_string(
            "reports/partials/learner_details.html", {"learners": []}
        )

        assert "no learners" in html
        assert "empty-state" in html

    def test_renders_one_block_per_learner(self) -> None:
        learners = [
            learner_detail(user_id=1, full_name="Ann Lee", sort_key=("Lee", "Ann")),
            learner_detail(user_id=2, full_name="Bo Kim", sort_key=("Kim", "Bo")),
        ]

        html = render_to_string(
            "reports/partials/learner_details.html", {"learners": learners}
        )

        assert 'id="learner-1"' in html
        assert 'id="learner-2"' in html
        assert "Ann Lee" in html
        assert "Bo Kim" in html


class TestQuizConfusion:
    def test_renders_counts_not_percentage_when_show_percentage_false(self) -> None:
        question = QuizConfusion(
            question_number=1,
            question_text="What is X?",
            respondent_count=6,
            wrong_count=4,
            show_percentage=False,
            wrong_percentage=None,
            distractors=[("Option B", 3)],
            correct_option_texts=["Option A"],
        )
        block = ConfusionBlock(questions=[question], shown=1, total=1)
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz 1", abbreviation="Q1", pass_percentage=50
        )

        html = render_to_string(
            "reports/partials/quiz_confusion.html", {"quiz": quiz, "block": block}
        )

        assert "4 of 6" in html
        assert "%" not in html
        assert "Option A" in html
        assert "Option B" in html
        assert "×3" in html  # noqa: RUF001 -- the multiplication sign the template renders

    def test_renders_percentage_not_counts_when_show_percentage_true(self) -> None:
        question = QuizConfusion(
            question_number=1,
            question_text="What is X?",
            respondent_count=20,
            wrong_count=15,
            show_percentage=True,
            wrong_percentage=75,
            distractors=[("Option B", 12)],
            correct_option_texts=["Option A"],
        )
        block = ConfusionBlock(questions=[question], shown=1, total=1)
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz 1", abbreviation="Q1", pass_percentage=50
        )

        html = render_to_string(
            "reports/partials/quiz_confusion.html", {"quiz": quiz, "block": block}
        )

        assert "75%" in html
        assert "15 of 20" not in html
        assert "Option A" in html
        assert "Option B" in html
        assert "×12" in html  # noqa: RUF001 -- the multiplication sign the template renders

    def test_emits_confusion_anchor_id(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz 1", abbreviation="Q1", pass_percentage=50
        )
        block = ConfusionBlock(questions=[], shown=0, total=0)

        html = render_to_string(
            "reports/partials/quiz_confusion.html", {"quiz": quiz, "block": block}
        )

        assert f'id="confusions-{quiz.form_id}"' in html


class TestConfusions:
    def test_includes_quiz_with_nonempty_block_and_skips_empty(self) -> None:
        quiz_with_confusion = QuizColumn(
            form_id=uuid4(),
            title="Quiz With Confusion",
            abbreviation="Q1",
            pass_percentage=50,
        )
        clean_quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Clean", abbreviation="Q2", pass_percentage=50
        )
        confusion = QuizConfusion(
            question_number=1,
            question_text="Tricky?",
            respondent_count=5,
            wrong_count=3,
            show_percentage=False,
            wrong_percentage=None,
            distractors=[("Wrong option", 2)],
            correct_option_texts=["Right option"],
        )
        block_with_confusion = ConfusionBlock(questions=[confusion], shown=1, total=1)
        clean_block = ConfusionBlock(questions=[], shown=0, total=0)
        section = course_section_with_one_summary_table(
            quizzes=[quiz_with_confusion, clean_quiz],
            confusions_by_quiz={
                quiz_with_confusion.form_id: block_with_confusion,
                clean_quiz.form_id: clean_block,
            },
        )

        html = render_to_string(
            "reports/partials/confusions.html", {"courses": [section]}
        )

        assert "Tricky?" in html
        assert "Quiz Clean" not in html
        assert f'id="confusions-{quiz_with_confusion.form_id}"' in html
        assert f'id="confusions-{clean_quiz.form_id}"' not in html
        assert "no incorrect answers to analyse" not in html

    def test_states_the_situation_when_there_are_no_courses(self) -> None:
        html = render_to_string("reports/partials/confusions.html", {"courses": []})

        assert "No quiz in this report has any incorrect answers to analyse." in html

    def test_states_the_situation_when_every_quiz_is_clean(self) -> None:
        clean_quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Clean", abbreviation="QC", pass_percentage=50
        )
        section = course_section_with_one_summary_table(
            quizzes=[clean_quiz],
            confusions_by_quiz={
                clean_quiz.form_id: ConfusionBlock(questions=[], shown=0, total=0)
            },
        )

        html = render_to_string(
            "reports/partials/confusions.html", {"courses": [section]}
        )

        assert "No quiz in this report has any incorrect answers to analyse." in html

    def test_no_empty_state_when_a_later_course_has_confusions(self) -> None:
        # The emptiness flag has to survive the loop that finds the match, not
        # just the iteration it was set in.
        clean_quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Clean", abbreviation="QC", pass_percentage=50
        )
        busy_quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Busy", abbreviation="QB", pass_percentage=50
        )
        confusion = QuizConfusion(
            question_number=1,
            question_text="Tricky?",
            respondent_count=5,
            wrong_count=3,
            show_percentage=False,
            wrong_percentage=None,
            distractors=[],
            correct_option_texts=["Right option"],
        )
        clean_section = course_section_with_one_summary_table(
            title="Clean course",
            quizzes=[clean_quiz],
            confusions_by_quiz={
                clean_quiz.form_id: ConfusionBlock(questions=[], shown=0, total=0)
            },
        )
        busy_section = course_section_with_one_summary_table(
            title="Busy course",
            quizzes=[busy_quiz],
            confusions_by_quiz={
                busy_quiz.form_id: ConfusionBlock(
                    questions=[confusion], shown=1, total=1
                )
            },
        )

        html = render_to_string(
            "reports/partials/confusions.html",
            {"courses": [clean_section, busy_section]},
        )

        assert "Tricky?" in html
        assert "no incorrect answers to analyse" not in html

    def test_emits_a_running_element_that_clears_the_learner_header(self) -> None:
        html = render_to_string("reports/partials/confusions.html", {"courses": []})

        assert '<span class="running-name-reset">' in html


class TestReportShell:
    """Renders report.html directly with hand-supplied CSS, bypassing
    build_report_html()'s asset resolution — a smoke test that the include wiring
    in the shell itself is correct."""

    def test_renders_every_section_marker(self) -> None:
        data = cohort_report_data()

        html = render_to_string(
            "reports/report.html",
            {
                "data": data,
                "theme_tokens": ":root { --color-success: #38A169; }",
                "print_css": "body { margin: 0; }",
            },
        )

        assert "<!doctype html>" in html
        assert "Cohort A" in html
        assert 'class="title-page"' in html
        assert 'class="at-a-glance' in html
        assert 'class="contents' in html
        assert 'class="methodology"' in html
        assert "landscape-section" in html
        assert 'class="learner-details' in html
        assert 'class="confusions' in html
        assert "--color-success: #38A169;" in html
        assert "body { margin: 0; }" in html


class TestFlagSeverity:
    def test_badge_class_follows_the_flag_severity(self) -> None:
        flags = [
            AtRiskFlag("no_activity", "No recorded activity", "Nothing yet.", "error"),
            AtRiskFlag("inactive", "No activity recently", "Quiet lately.", "warning"),
        ]

        html = render_to_string("reports/partials/flag_list.html", {"flags": flags})

        assert "badge-error" in html
        assert "badge-warning" in html

    def test_every_flag_still_carries_the_at_risk_glyph(self) -> None:
        # Colour is never the only signal, so severity changes the badge's
        # colour but never removes the glyph.
        flags = [AtRiskFlag("inactive", "No activity recently", "Quiet.", "warning")]

        html = render_to_string("reports/partials/flag_list.html", {"flags": flags})

        assert "▲" in html

    def test_panel_takes_its_severity_from_the_first_flag(self) -> None:
        learner = learner_detail(
            flags=[
                AtRiskFlag("no_activity", "No recorded activity", "Nothing.", "error"),
                AtRiskFlag("inactive", "No activity recently", "Quiet.", "warning"),
            ]
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "flags-error" in html


class TestQuizAttemptsTable:
    def test_renders_one_row_per_completed_attempt(self) -> None:
        attempts = [
            QuizAttempt(
                attempt_number=1,
                completed_at=GENERATED_AT,
                score=3,
                max_score=10,
                percentage=30,
                passed=False,
            ),
            QuizAttempt(
                attempt_number=2,
                completed_at=GENERATED_AT,
                score=9,
                max_score=10,
                percentage=90,
                passed=True,
            ),
        ]
        learner = learner_detail(
            has_any_progress=True,
            quiz_results=[
                QuizResult(
                    form_id=uuid4(),
                    title="Orbit Quiz",
                    latest_score=9,
                    latest_max_score=10,
                    latest_percentage=90,
                    passed=True,
                    attempt_count=2,
                    completed_at=GENERATED_AT,
                    attempts=attempts,
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert "Quiz attempts" in html
        assert html.count("Orbit Quiz") == 2
        assert "30%" in html
        assert "90%" in html
        assert "3/10" in html
        assert "9/10" in html

    def test_attempt_with_no_pass_mark_shows_no_verdict_glyph(self) -> None:
        learner = learner_detail(
            has_any_progress=True,
            quiz_results=[
                QuizResult(
                    form_id=uuid4(),
                    title="Unmarked Quiz",
                    latest_score=5,
                    latest_max_score=10,
                    latest_percentage=50,
                    passed=None,
                    attempt_count=1,
                    completed_at=GENERATED_AT,
                    attempts=[
                        QuizAttempt(
                            attempt_number=1,
                            completed_at=GENERATED_AT,
                            score=5,
                            max_score=10,
                            percentage=50,
                            passed=None,
                        )
                    ],
                )
            ],
        )

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        # Scoped to the attempts table: the learner's own completion bar above
        # it carries a glyph of its own.
        attempts_table = html.split("Quiz attempts")[1]
        assert "○" in attempts_table
        assert "✓" not in attempts_table
        assert "✗" not in attempts_table


class TestCoverBranding:
    def test_names_the_site_and_omits_an_unconfigured_logo(self) -> None:
        data = cohort_report_data(site_name="Bright Academy")

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_url": None},
        )

        assert "Bright Academy" in html
        assert "<img" not in html

    def test_renders_the_site_logo_when_configured(self) -> None:
        data = cohort_report_data(site_name="Bright Academy")

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_url": "file:///tmp/site.png"},
        )

        assert 'src="file:///tmp/site.png"' in html

    def test_course_card_states_each_course_scale(self) -> None:
        data = cohort_report_data(
            courses=[
                course_section_with_one_summary_table(title="Astronomy", item_count=24)
            ]
        )

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_url": None},
        )

        assert "24 items" in html
