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
    LearnerDetail,
    LearnerRow,
    OrganisationBrand,
    QuizColumn,
    QuizConfusion,
    SummaryRow,
    SummaryTable,
)

GENERATED_AT = datetime(2026, 3, 15, 10, 30, tzinfo=UTC)


def learner_detail(**overrides: object) -> LearnerDetail:
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
    return LearnerDetail(**defaults)


def course_section_defaults() -> dict[str, object]:
    """A fresh default field map for one course section.

    Returned rather than applied so a caller that has to derive one field from
    another -- summary tables from the quiz columns, say -- can do so before
    building the frozen dataclass.
    """
    return {
        "course_id": uuid4(),
        "title": "Course A",
        "is_active": True,
        "item_count": 0,
        "quizzes": [],
        "learner_rows": [],
        "summary_tables": [],
        "confusions_by_quiz": {},
    }


def course_section(**overrides: object) -> CourseSection:
    defaults = course_section_defaults()
    defaults.update(overrides)
    return CourseSection(**defaults)


def summary_row(row: LearnerRow, quizzes: list[QuizColumn]) -> SummaryRow:
    """The SummaryRow gather.py would derive from this LearnerRow for `quizzes`."""
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


def organisation_brand(**overrides: object) -> OrganisationBrand:
    defaults: dict[str, object] = {
        "name": "Northside College",
        "logo_data_uri": None,
        "wordmark_size_class": "full",
        "wordmark_name": "Northside College",
        "footer_name": "Northside College",
    }
    defaults.update(overrides)
    return OrganisationBrand(**defaults)


def cohort_report_data(**overrides: object) -> CohortReportData:
    defaults: dict[str, object] = {
        "cohort_name": "Cohort A",
        "footer_cohort_name": "Cohort A",
        "organisation": organisation_brand(),
        "site_name": "Test Academy",
        "show_powered_by": True,
        "generated_at": GENERATED_AT,
        "requested_by_name": "Jamie Educator",
        "courses": [],
        "learners": [],
        "attention_list": AttentionList(learners=[], shown=0, total=0),
        "cohort_size": 0,
        "median_completion": 0,
        "not_started_count": 0,
        "complete_count": 0,
    }
    defaults.update(overrides)
    return CohortReportData(**defaults)


def full_report_data() -> CohortReportData:
    """A small but structurally complete cohort.

    One flagged learner whose flags must render identically on the at-a-glance
    page and their own section, one active and one inactive course, and one
    quiz with a non-empty confusion block -- enough to exercise every anchor
    id the document emits.
    """
    reason = "Has not started any course item in over 7 days, a distinctive reason."
    flag = AtRiskFlag(
        rule_id="no_activity",
        label="No recorded activity",
        reason=reason,
        severity="error",
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
    row = LearnerRow(
        user_id=1,
        full_name="Ada Lovelace",
        completion_percentage=40,
        completed_item_count=2,
        total_item_count=5,
        last_completed_title="Stars",
        last_completed_at=GENERATED_AT,
        quiz_cells={quiz.form_id: None},
    )
    course_active = course_section(
        title="Astronomy",
        is_active=True,
        item_count=5,
        quizzes=[quiz],
        learner_rows=[row],
        summary_tables=[
            SummaryTable(
                quizzes=[quiz], rows=[summary_row(row, [quiz])], continued=False
            )
        ],
        confusions_by_quiz={quiz.form_id: block},
    )
    course_inactive = course_section(
        title="Retired Course",
        is_active=False,
        summary_tables=[SummaryTable(quizzes=[], rows=[], continued=False)],
    )

    flagged_learner = learner_detail(
        user_id=1, full_name="Ada Lovelace", sort_key=("Lovelace", "Ada"), flags=[flag]
    )
    other_learner = learner_detail(
        user_id=2, full_name="Bo Kim", sort_key=("Kim", "Bo"), flags=[]
    )
    attention = AttentionList(learners=[flagged_learner], shown=1, total=1)

    return cohort_report_data(
        courses=[course_active, course_inactive],
        learners=[flagged_learner, other_learner],
        attention_list=attention,
        cohort_size=2,
    )
