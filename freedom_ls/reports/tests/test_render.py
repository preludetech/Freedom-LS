"""Tests for freedom_ls.reports.render.

No WeasyPrint call happens anywhere in this file. render_report_pdf()'s own PDF
output is proven by Task 4.6's pypdf-based integration tests, marked
`weasyprint` and written in a later batch. Everything here exercises
build_report_html() and the theme-token extractor, both pure Python plus a
Django template render -- no ORM access, so none of these tests need
`django_db` or `mock_site_context`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from django.utils import timezone

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
)
from freedom_ls.reports.render import (
    ReportRenderError,
    _extract_theme_tokens_from_css,
    build_report_html,
    extract_theme_tokens,
)

GENERATED_AT = datetime(2026, 3, 15, 10, 30, tzinfo=UTC)

# Deliberately fake values, not the real bundle's hex codes -- this is a
# controlled input mimicking the real bundle's shape (a nested `@layer theme {
# :root, :host { ... } }` block followed by an unrelated `@layer utilities`
# block), never the repo's actual compiled CSS. See test_real_bundle_* below
# for the separate, value-blind check against the real file.
CONTROLLED_BUNDLE_CSS = """
@layer theme {
  :root, :host {
    --color-success: #123456;
    --color-warning: #abcdef;
  }
}
@layer utilities {
  .flex {
    display: flex;
  }
  .bg-success-light {
    background-color: var(--color-success-light);
  }
}
"""


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
        "wrong_answers_by_quiz": {},
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
        "confusions_by_quiz": {},
    }
    defaults.update(overrides)
    return CourseSection(**defaults)


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


def _dangling_anchor_links(html: str) -> list[str]:
    """href="#..." targets whose matching id="..." does not appear exactly once."""
    targets = re.findall(r'href="#([^"]+)"', html)
    return [target for target in targets if html.count(f'id="{target}"') != 1]


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
        confusions_by_quiz={quiz.form_id: block},
    )
    course_inactive = _course_section(title="Retired Course", is_active=False)

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


class TestExtractThemeTokens:
    def test_controlled_input_yields_custom_properties_only(self) -> None:
        result = _extract_theme_tokens_from_css(CONTROLLED_BUNDLE_CSS)

        assert "--color-success: #123456;" in result
        assert "--color-warning: #abcdef;" in result
        assert ".flex" not in result
        assert "display: flex" not in result
        assert "@layer" not in result

    def test_real_bundle_yields_every_role_token_the_report_uses(self) -> None:
        result = extract_theme_tokens()
        role_tokens = [
            "--color-success:",
            "--color-warning:",
            "--color-error:",
            "--color-info:",
            "--color-success-light:",
            "--color-warning-light:",
            "--color-error-light:",
            "--color-info-light:",
            "--color-on-success-light:",
            "--color-on-warning-light:",
            "--color-on-error-light:",
            "--color-on-info-light:",
            "--color-surface:",
            "--color-muted:",
        ]

        assert all(name in result for name in role_tokens)

    def test_missing_bundle_raises_report_render_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("freedom_ls.reports.render.finders.find", lambda path: None)

        with pytest.raises(ReportRenderError):
            extract_theme_tokens()


class TestBuildReportHtml:
    def test_every_student_name_present(self) -> None:
        html = build_report_html(_full_report_data())

        assert "Ada Lovelace" in html
        assert "Bo Kim" in html

    def test_flag_reason_identical_between_at_a_glance_and_student_section(
        self,
    ) -> None:
        data = _full_report_data()
        reason = data.students[0].flags[0].reason

        html = build_report_html(data)

        assert html.count(reason) == 2

    def test_inactive_course_section_carries_marker(self) -> None:
        html = build_report_html(_full_report_data())

        assert 'class="inactive-marker"' in html
        assert "Retired Course" in html

    def test_timezone_appears_on_title_page(self) -> None:
        data = _full_report_data()

        html = build_report_html(data)

        expected_tz = timezone.localtime(data.generated_at).strftime("%Z")
        assert expected_tz in html

    def test_every_anchor_href_target_exists_exactly_once(self) -> None:
        html = build_report_html(_full_report_data())

        assert _dangling_anchor_links(html) == []
