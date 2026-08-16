"""Hand-built `CohortReportData` builders shared by the render-layer test files.

`test_render.py` (pure-Python HTML assertions) and `test_pdf_integration.py`
(WeasyPrint/pypdf assertions, marked `weasyprint`) both drive
`build_report_html()` / `render_report_pdf()` over the same small, structurally
complete cohort, so the builders live here once rather than being copied
between the two files.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from freedom_ls.reports.gather import (
    AtRiskFlag,
    AttentionList,
    CohortReportData,
    ConfusionBlock,
    CourseSection,
    QuizColumn,
    QuizConfusion,
    StudentDetail,
    StudentRow,
    SummaryRow,
    SummaryTable,
)

GENERATED_AT = datetime(2026, 3, 15, 10, 30, tzinfo=UTC)


def _student_detail(**overrides: object) -> StudentDetail:
    defaults: dict[str, object] = {
        "user_id": 1,
        "full_name": "Jamie Smith",
        "sort_key": ("Smith", "Jamie"),
        "completion_percentage": 0,
        "completed_item_count": 0,
        "total_item_count": 5,
        "last_completed_title": None,
        "last_completed_at": None,
        "has_any_progress": False,
        "completed_items": [],
        "quiz_results": [],
        "wrong_answers": [],
        "report_generated_at": GENERATED_AT,
        "flags": [],
    }
    defaults.update(overrides)
    return StudentDetail(**defaults)


def _course_section(**overrides: object) -> CourseSection:
    defaults: dict[str, object] = {
        "course_id": uuid4(),
        "title": "Course A",
        "is_active": True,
        "quizzes": [],
        "student_rows": [],
        "summary_tables": [],
        "confusions_by_quiz": {},
    }
    defaults.update(overrides)
    return CourseSection(**defaults)


def _summary_row(row: StudentRow, quizzes: list[QuizColumn]) -> SummaryRow:
    """The SummaryRow gather.py would derive from this StudentRow for `quizzes`."""
    return SummaryRow(
        user_id=row.user_id,
        full_name=row.full_name,
        completion_percentage=row.completion_percentage,
        completed_item_count=row.completed_item_count,
        total_item_count=row.total_item_count,
        last_completed_title=row.last_completed_title,
        last_completed_at=row.last_completed_at,
        cells=[row.quiz_cells[quiz.form_id] for quiz in quizzes],
    )


def _cohort_report_data(**overrides: object) -> CohortReportData:
    defaults: dict[str, object] = {
        "cohort_name": "Cohort A",
        "generated_at": GENERATED_AT,
        "requested_by_name": "Jamie Educator",
        "courses": [],
        "students": [],
        "attention_list": AttentionList(students=[], shown=0, total=0),
        "cohort_size": 0,
        "median_completion": 0,
        "not_started_count": 0,
        "complete_count": 0,
    }
    defaults.update(overrides)
    return CohortReportData(**defaults)


def _full_report_data() -> CohortReportData:
    """A small but structurally complete cohort.

    One flagged student whose flags must render identically on the at-a-glance
    page and their own section, one active and one inactive course, and one
    quiz with a non-empty confusion block -- enough to exercise every anchor
    id the document emits.
    """
    reason = "Has not started any course item in over 7 days, a distinctive reason."
    flag = AtRiskFlag(
        rule_id="no_activity", label="No recorded activity", reason=reason
    )

    quiz = QuizColumn(
        form_id=uuid4(), title="Orbit Quiz", abbreviation="OQ", pass_percentage=50
    )
    confusion = QuizConfusion(
        question_number=1,
        question_text="What is an orbit?",
        respondent_count=12,
        wrong_count=8,
        show_percentage=True,
        wrong_percentage=67,
        distractors=[("A straight line", 5)],
        correct_option_texts=["A closed path around a body"],
    )
    block = ConfusionBlock(questions=[confusion], shown=1, total=1)
    row = StudentRow(
        user_id=1,
        full_name="Ada Lovelace",
        completion_percentage=40,
        completed_item_count=2,
        total_item_count=5,
        last_completed_title="Stars",
        last_completed_at=GENERATED_AT,
        quiz_cells={quiz.form_id: None},
    )
    course_active = _course_section(
        title="Astronomy",
        is_active=True,
        quizzes=[quiz],
        student_rows=[row],
        summary_tables=[
            SummaryTable(
                quizzes=[quiz], rows=[_summary_row(row, [quiz])], continued=False
            )
        ],
        confusions_by_quiz={quiz.form_id: block},
    )
    course_inactive = _course_section(
        title="Retired Course",
        is_active=False,
        summary_tables=[SummaryTable(quizzes=[], rows=[], continued=False)],
    )

    flagged_student = _student_detail(
        user_id=1, full_name="Ada Lovelace", sort_key=("Lovelace", "Ada"), flags=[flag]
    )
    other_student = _student_detail(
        user_id=2, full_name="Bo Kim", sort_key=("Kim", "Bo"), flags=[]
    )
    attention = AttentionList(students=[flagged_student], shown=1, total=1)

    return _cohort_report_data(
        courses=[course_active, course_inactive],
        students=[flagged_student, other_student],
        attention_list=attention,
        cohort_size=2,
    )
