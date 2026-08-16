"""Per-partial tests for the report templates.

Each partial is rendered directly via `render_to_string("reports/partials/<name>.html", {...})`
with a minimal hand-built context — a couple of `freedom_ls.reports.gather` dataclass
instances, never a whole `CohortReportData` built through the ORM. No database access
happens anywhere in this file, so none of these tests need `django_db` or
`mock_site_context`: the dataclasses under test are plain, frozen Python objects.

The whole-document tier (`build_report_html()`) is out of scope for this file — it needs
`render.py`, written in a later batch.
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
    QuizColumn,
    QuizConfusion,
    QuizResult,
    QuizWrongAnswers,
    StudentRow,
    SummaryTable,
    WrongAnswer,
)
from freedom_ls.reports.tests.report_data_builders import (
    GENERATED_AT,
    _cohort_report_data,
    _course_section_defaults,
    _student_detail,
    _summary_row,
)


def _course_section(
    quizzes: list[QuizColumn] | None = None,
    student_rows: list[StudentRow] | None = None,
    **overrides: object,
) -> CourseSection:
    """A course section whose single summary table covers every quiz it declares.

    Chunking a wide course across several tables is `gather`'s job and is
    tested there; a partial only ever renders the tables it is handed.
    """
    quizzes = quizzes or []
    student_rows = student_rows or []
    defaults = _course_section_defaults()
    defaults["quizzes"] = quizzes
    defaults["student_rows"] = student_rows
    defaults["summary_tables"] = [
        SummaryTable(
            quizzes=quizzes,
            rows=[_summary_row(row, quizzes) for row in student_rows],
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
            {"shown": 5, "total": 5, "noun": "students flagged"},
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

        assert "8/10" in html
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
    def test_links_to_student_anchor_and_shows_flags(self) -> None:
        student = _student_detail(
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
            "reports/partials/attention_entry.html", {"student": student}
        )

        assert 'href="#student-42"' in html
        assert "Alex Doe" in html
        assert "No activity recently" in html


class TestTitlePage:
    def test_shows_cohort_name_courses_and_inactive_marker(self) -> None:
        data = _cohort_report_data(
            courses=[
                _course_section(title="Course 1", is_active=True),
                _course_section(title="Course 2", is_active=False),
            ]
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "Cohort A" in html
        assert "Course 1" in html
        assert "Course 2" in html
        assert "inactive" in html.lower()
        assert "Jamie Educator" in html
        assert "2026" in html


class TestAtAGlance:
    def test_shows_stats_and_attention_list(self) -> None:
        student = _student_detail(
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
        attention = AttentionList(students=[student], shown=1, total=1)
        data = _cohort_report_data(
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
        attention = AttentionList(students=[], shown=12, total=18)
        data = _cohort_report_data(attention_list=attention)

        html = render_to_string(
            "reports/partials/at_a_glance.html", {"data": data, "attention": attention}
        )

        assert "12" in html
        assert "18" in html

    def test_no_disclosure_when_not_capped(self) -> None:
        attention = AttentionList(students=[], shown=0, total=0)
        data = _cohort_report_data(attention_list=attention)

        html = render_to_string(
            "reports/partials/at_a_glance.html", {"data": data, "attention": attention}
        )

        assert "No students currently flagged." in html


class TestContents:
    def test_links_to_course_and_student_anchors(self) -> None:
        course = _course_section(title="Course X")
        student = _student_detail(user_id=3, full_name="Robin Fox")
        data = _cohort_report_data(courses=[course], students=[student])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#course-{course.course_id}"' in html
        assert 'href="#student-3"' in html

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
        course = _course_section(
            quizzes=[quiz], confusions_by_quiz={quiz.form_id: block}
        )
        data = _cohort_report_data(courses=[course])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#confusions-{quiz.form_id}"' in html

    def test_omits_confusion_link_when_block_empty(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Y", abbreviation="QY", pass_percentage=50
        )
        block = ConfusionBlock(questions=[], shown=0, total=0)
        course = _course_section(
            quizzes=[quiz], confusions_by_quiz={quiz.form_id: block}
        )
        data = _cohort_report_data(courses=[course])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#confusions-{quiz.form_id}"' not in html


class TestMethodology:
    def test_mentions_key_concepts_and_glyphs(self) -> None:
        html = render_to_string("reports/partials/methodology.html", {})

        assert "recomputed" in html.lower()
        assert "latest" in html.lower()
        assert "first" in html.lower()
        assert "free-text" in html.lower()
        assert "✓" in html
        assert "✗" in html
        assert "▲" in html
        assert "●" in html
        assert "○" in html
        assert "—" in html


class TestCourseSummaryTable:
    def test_shows_student_rows_and_quiz_columns(self) -> None:
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
        row = StudentRow(
            user_id=5,
            full_name="Jesse Park",
            completion_percentage=80,
            completed_item_count=4,
            total_item_count=5,
            last_completed_title="Topic A",
            last_completed_at=GENERATED_AT,
            quiz_cells={quiz.form_id: result},
        )
        section = _course_section(title="Course Q", quizzes=[quiz], student_rows=[row])

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "Jesse Park" in html
        assert "QZ" in html
        assert "9/10" in html
        assert f'id="course-{section.course_id}"' in html

    def test_marks_inactive_registration(self) -> None:
        section = _course_section(title="Course Inactive", is_active=False)

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "inactive" in html.lower()

    def test_shows_dash_for_unattempted_quiz_cell(self) -> None:
        quiz = QuizColumn(
            form_id=uuid4(), title="Quiz Z", abbreviation="QZ", pass_percentage=50
        )
        row = StudentRow(
            user_id=5,
            full_name="Jesse Park",
            completion_percentage=0,
            completed_item_count=0,
            total_item_count=5,
            last_completed_title=None,
            last_completed_at=None,
            quiz_cells={quiz.form_id: None},
        )
        section = _course_section(quizzes=[quiz], student_rows=[row])

        html = render_to_string(
            "reports/partials/course_summary_table.html", {"section": section}
        )

        assert "—" in html


class TestSummaryTables:
    def test_renders_landscape_wrapper_and_course_tables(self) -> None:
        section = _course_section(title="Course L")

        html = render_to_string(
            "reports/partials/summary_tables.html", {"courses": [section]}
        )

        assert "landscape-section" in html
        assert f'id="course-{section.course_id}"' in html
        assert "Course L" in html


class TestStudentDetail:
    def test_renders_no_activity_recorded_when_has_any_progress_false(self) -> None:
        student = _student_detail(has_any_progress=False)

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert "No activity recorded" in html

    def test_renders_activity_when_has_any_progress_true(self) -> None:
        student = _student_detail(
            has_any_progress=True,
            completed_items=[
                CompletedItem(
                    title="Intro Topic", completed_at=GENERATED_AT, is_quiz=False
                )
            ],
        )

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert "No activity recorded" not in html
        assert "Intro Topic" in html

    def test_renders_flags_at_the_top(self) -> None:
        student = _student_detail(
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
            "reports/partials/student_detail.html", {"student": student}
        )

        assert "No recorded activity" in html
        assert "Has not started any course item." in html

    def test_emits_student_anchor_id(self) -> None:
        student = _student_detail(user_id=99)

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert 'id="student-99"' in html

    def test_running_header_name_is_a_separate_element_from_the_heading(self) -> None:
        # The heading is the section's PDF bookmark and the span is the running
        # header; one element cannot be both, because print.css redraws the
        # running element on every page of the section and each redraw would
        # bookmark the student again.
        student = _student_detail(full_name="Robin Fox")

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert '<span class="student-running-name">Robin Fox</span>' in html
        assert '<h3 class="student-heading">Robin Fox</h3>' in html

    def test_wrong_answers_heading_names_its_quiz(self) -> None:
        student = _student_detail(
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
                            selected_option_texts=["Option A"],
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
                            selected_option_texts=["Option C"],
                            correct_option_texts=["Option D"],
                        )
                    ],
                ),
            ],
        )

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert "Wrong answers — Voltage Quiz" in html
        assert "Wrong answers — Erosion Quiz" in html
        assert "Q8. What is voltage?" in html
        assert "Q3. What is erosion?" in html

    def test_omits_wrong_answers_block_for_a_quiz_with_no_wrong_answers(self) -> None:
        student = _student_detail(
            has_any_progress=True,
            wrong_answers=[
                QuizWrongAnswers(form_id=uuid4(), title="Clean Quiz", answers=[])
            ],
        )

        html = render_to_string(
            "reports/partials/student_detail.html", {"student": student}
        )

        assert "Wrong answers" not in html


class TestStudentDetails:
    def test_states_the_situation_when_the_cohort_has_no_students(self) -> None:
        html = render_to_string(
            "reports/partials/student_details.html", {"students": []}
        )

        assert "no students" in html
        assert "empty-state" in html

    def test_renders_one_block_per_student(self) -> None:
        students = [
            _student_detail(user_id=1, full_name="Ann Lee", sort_key=("Lee", "Ann")),
            _student_detail(user_id=2, full_name="Bo Kim", sort_key=("Kim", "Bo")),
        ]

        html = render_to_string(
            "reports/partials/student_details.html", {"students": students}
        )

        assert 'id="student-1"' in html
        assert 'id="student-2"' in html
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
        assert "Option B (3)" in html

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
        assert "Option B (12)" in html

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
        section = _course_section(
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
        section = _course_section(
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
        clean_section = _course_section(
            title="Clean course",
            quizzes=[clean_quiz],
            confusions_by_quiz={
                clean_quiz.form_id: ConfusionBlock(questions=[], shown=0, total=0)
            },
        )
        busy_section = _course_section(
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

    def test_emits_a_running_element_that_clears_the_student_header(self) -> None:
        html = render_to_string("reports/partials/confusions.html", {"courses": []})

        assert '<span class="running-name-reset">' in html


class TestReportShell:
    """Renders report.html directly, bypassing build_report_html() (written in a later
    batch) — a smoke test that the include wiring in the shell itself is correct."""

    def test_renders_every_section_marker(self) -> None:
        data = _cohort_report_data()

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
        assert 'class="at-a-glance"' in html
        assert 'class="contents"' in html
        assert 'class="methodology"' in html
        assert "landscape-section" in html
        assert 'class="student-details"' in html
        assert 'class="confusions"' in html
        assert "--color-success: #38A169;" in html
        assert "body { margin: 0; }" in html
