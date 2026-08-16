"""Tests for freedom_ls.reports.render.

No WeasyPrint call happens anywhere in this file. render_report_pdf()'s own PDF
output is proven by the pypdf-based integration tests in test_pdf_integration.py,
marked `weasyprint`. Everything here exercises build_report_html() and the
theme-token extractor, both pure Python plus a Django template render -- no
ORM access, so none of these tests need `django_db` or `mock_site_context`.
"""

from __future__ import annotations

import re

import pytest

from django.utils import timezone

from freedom_ls.reports.render import (
    ReportRenderError,
    _extract_theme_tokens_from_css,
    build_report_html,
    extract_theme_tokens,
)
from freedom_ls.reports.tests.report_data_builders import (
    _cohort_report_data,
    _course_section,
    _full_report_data,
)

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


def _dangling_anchor_links(html: str) -> list[str]:
    """href="#..." targets whose matching id="..." does not appear exactly once."""
    targets = re.findall(r'href="#([^"]+)"', html)
    return [target for target in targets if html.count(f'id="{target}"') != 1]


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

    def test_requester_name_replaces_the_system_fallback(self) -> None:
        html = build_report_html(_full_report_data())

        assert "by Jamie Educator." in html
        assert "by the system." not in html

    def test_missing_requester_falls_back_to_the_system(self) -> None:
        html = build_report_html(_cohort_report_data(requested_by_name=""))

        assert "by the system." in html

    def test_confusion_percentage_names_its_denominator(self) -> None:
        html = build_report_html(_full_report_data())

        assert "67% of 12 students" in html


class TestDegenerateCohortEmptyStates:
    def test_cohort_with_no_courses_states_so_on_the_title_page(self) -> None:
        html = build_report_html(_cohort_report_data(courses=[]))

        assert "No courses are registered to this cohort." in html

    def test_cohort_with_no_courses_states_so_under_summary_tables(self) -> None:
        html = build_report_html(_cohort_report_data(courses=[]))

        assert "There are no course registrations to summarise." in html

    def test_course_with_no_students_states_so_instead_of_a_bare_header_row(
        self,
    ) -> None:
        data = _cohort_report_data(courses=[_course_section(title="Astronomy")])

        html = build_report_html(data)

        assert "This cohort has no students." in html
