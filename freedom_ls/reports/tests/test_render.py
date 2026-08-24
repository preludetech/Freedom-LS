"""Tests for freedom_ls.reports.render.

No WeasyPrint call happens anywhere in this file. render_report_pdf()'s own PDF
output is proven by the pypdf-based integration tests in test_pdf_integration.py,
marked `weasyprint`. Everything here exercises build_report_html() and the
theme-token extractor, both pure Python plus a Django template render -- no
ORM access, so none of these tests need `django_db` or `mock_site_context`.
"""

from __future__ import annotations

import base64
import re

import pytest

from django.test import override_settings
from django.utils import timezone

from freedom_ls.organisations.validators import MAX_BYTES
from freedom_ls.reports.render import (
    ReportRenderError,
    _extract_theme_tokens_from_css,
    _find_static,
    _restrictive_url_fetcher,
    build_font_css,
    build_report_html,
    extract_theme_tokens,
)
from freedom_ls.reports.tests.conftest import requires_tailwind_bundle
from freedom_ls.reports.tests.report_data_builders import (
    cohort_report_data,
    course_section,
    full_report_data,
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

    @requires_tailwind_bundle
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


@requires_tailwind_bundle
class TestBuildReportHtml:
    def test_every_learner_name_present(self) -> None:
        html = build_report_html(full_report_data())

        assert "Ada Lovelace" in html
        assert "Bo Kim" in html

    def test_flag_reason_identical_between_at_a_glance_and_learner_section(
        self,
    ) -> None:
        data = full_report_data()
        reason = data.learners[0].flags[0].reason

        html = build_report_html(data)

        assert html.count(reason) == 2

    def test_inactive_course_section_carries_marker(self) -> None:
        html = build_report_html(full_report_data())

        assert 'class="inactive-marker"' in html
        assert "Retired Course" in html

    def test_timezone_appears_on_title_page(self) -> None:
        data = full_report_data()

        html = build_report_html(data)

        expected_tz = timezone.localtime(data.generated_at).strftime("%Z")
        assert expected_tz in html

    def test_every_anchor_href_target_exists_exactly_once(self) -> None:
        html = build_report_html(full_report_data())

        assert _dangling_anchor_links(html) == []

    def test_requester_name_replaces_the_system_fallback(self) -> None:
        html = build_report_html(full_report_data())

        assert "Jamie Educator" in html
        assert "the system" not in html

    def test_missing_requester_falls_back_to_the_system(self) -> None:
        html = build_report_html(cohort_report_data(requested_by_name=""))

        assert "the system" in html

    def test_confusion_percentage_names_its_denominator(self) -> None:
        html = build_report_html(full_report_data())

        assert "67% of 12 learners" in html


@requires_tailwind_bundle
class TestDegenerateCohortEmptyStates:
    def test_cohort_with_no_courses_states_so_on_the_title_page(self) -> None:
        html = build_report_html(cohort_report_data(courses=[]))

        assert "No courses are registered to this cohort." in html

    def test_cohort_with_no_courses_states_so_under_summary_tables(self) -> None:
        html = build_report_html(cohort_report_data(courses=[]))

        assert "There are no course registrations to summarise." in html

    def test_course_with_no_learners_states_so_instead_of_a_bare_header_row(
        self,
    ) -> None:
        data = cohort_report_data(courses=[course_section(title="Astronomy")])

        html = build_report_html(data)

        assert "This cohort has no learners." in html


class TestBuildFontCss:
    def test_emits_one_font_face_rule_per_configured_face(self) -> None:
        with override_settings(
            REPORTS_FONT_FACES=[
                {
                    "family": "Test Face",
                    "weight": "400",
                    "style": "normal",
                    "static_path": "reports/print.css",
                },
                {
                    "family": "Test Face",
                    "weight": "700",
                    "style": "italic",
                    "static_path": "reports/print.css",
                },
            ]
        ):
            css, paths = build_font_css()

        assert css.count("@font-face") == 2
        assert 'font-family: "Test Face"' in css
        assert "font-weight: 700" in css
        assert "font-style: italic" in css
        # Two rules, one file: several weights of a variable face share a path.
        assert len(paths) == 1

    def test_src_urls_are_absolute_file_urls_for_the_returned_paths(self) -> None:
        css, paths = build_font_css()

        for path in paths:
            assert f'url("{path.as_uri()}")' in css

    def test_stack_settings_become_custom_properties(self) -> None:
        with override_settings(
            REPORTS_FONT_DISPLAY='"Display Face", sans-serif',
            REPORTS_FONT_BODY='"Body Face", sans-serif',
            REPORTS_FONT_MONO='"Mono Face", monospace',
        ):
            css, _ = build_font_css()

        assert '--report-font-display: "Display Face", sans-serif;' in css
        assert '--report-font-body: "Body Face", sans-serif;' in css
        assert '--report-font-mono: "Mono Face", monospace;' in css

    def test_unresolvable_face_raises_rather_than_substituting(self) -> None:
        with (
            override_settings(
                REPORTS_FONT_FACES=[
                    {
                        "family": "Missing",
                        "weight": "400",
                        "style": "normal",
                        "static_path": "reports/fonts/not-a-real-file.ttf",
                    }
                ]
            ),
            pytest.raises(ReportRenderError, match=re.escape("not-a-real-file.ttf")),
        ):
            build_font_css()


def _fatal_url_fetching_error() -> type[Exception]:
    """WeasyPrint's fetch-refused exception, imported lazily.

    render.py keeps every weasyprint import inside a function so the module
    stays importable without Pango and friends; this file has to do the same or
    collection breaks for contributors who cannot run the `weasyprint` set.
    """
    from weasyprint.urls import FatalURLFetchingError

    error: type[Exception] = FatalURLFetchingError
    return error


@pytest.mark.weasyprint
class TestRestrictiveUrlFetcher:
    def test_refuses_a_file_outside_the_allowlist(self) -> None:
        allowed = _find_static("reports/print.css").resolve()
        fetch = _restrictive_url_fetcher({allowed})
        # A real, readable file in the same directory as an allowed one: a
        # directory-wide trust would let this through.
        sibling = allowed.parent / "fonts" / "DejaVuSans.ttf"

        with pytest.raises(_fatal_url_fetching_error()):
            fetch(sibling.as_uri())

    def test_refuses_http_urls(self) -> None:
        fetch = _restrictive_url_fetcher(set())

        with pytest.raises(_fatal_url_fetching_error()):
            fetch("https://example.invalid/logo.png")

    def test_allows_an_allowlisted_file(self) -> None:
        allowed = _find_static("reports/print.css").resolve()
        fetch = _restrictive_url_fetcher({allowed})

        assert fetch(allowed.as_uri()) is not None

    def test_allows_a_data_uri_with_an_allowed_mediatype(self) -> None:
        fetch = _restrictive_url_fetcher(set())
        payload = base64.b64encode(b"not a real image, just bytes").decode("ascii")

        assert fetch(f"data:image/png;base64,{payload}") is not None

    def test_allows_the_other_two_allowed_mediatypes(self) -> None:
        fetch = _restrictive_url_fetcher(set())
        payload = base64.b64encode(b"not a real image, just bytes").decode("ascii")

        assert fetch(f"data:image/jpeg;base64,{payload}") is not None
        assert fetch(f"data:image/webp;base64,{payload}") is not None

    def test_refuses_a_data_uri_with_a_disallowed_mediatype(self) -> None:
        fetch = _restrictive_url_fetcher(set())
        payload = base64.b64encode(b"<svg></svg>").decode("ascii")

        with pytest.raises(_fatal_url_fetching_error()):
            fetch(f"data:image/svg+xml;base64,{payload}")

    def test_refuses_a_non_base64_data_uri(self) -> None:
        fetch = _restrictive_url_fetcher(set())

        with pytest.raises(_fatal_url_fetching_error()):
            fetch("data:image/png,%3Csvg%3E%3C%2Fsvg%3E")

    def test_refuses_an_oversized_data_uri(self) -> None:
        fetch = _restrictive_url_fetcher(set())
        oversized = base64.b64encode(b"0" * (MAX_BYTES + 1)).decode("ascii")

        with pytest.raises(_fatal_url_fetching_error()):
            fetch(f"data:image/png;base64,{oversized}")

    def test_refuses_a_malformed_data_uri(self) -> None:
        fetch = _restrictive_url_fetcher(set())

        with pytest.raises(_fatal_url_fetching_error()):
            fetch("data:image/png;base64,not-valid-base64!!!")


@requires_tailwind_bundle
class TestBrandingOnTheCover:
    def test_site_logo_is_omitted_when_no_path_is_configured(self) -> None:
        with override_settings(HEADER_LOGO_STATIC_PATH=None):
            html = build_report_html(full_report_data())

        assert '<img class="cover-logo"' not in html

    def test_site_logo_is_rendered_when_configured(self) -> None:
        with override_settings(HEADER_LOGO_STATIC_PATH="reports/print.css"):
            html = build_report_html(full_report_data())

        assert '<img class="cover-logo"' in html
        assert "file://" in html

    def test_configured_but_unresolvable_logo_raises(self) -> None:
        with (
            override_settings(HEADER_LOGO_STATIC_PATH="nowhere/missing-logo.png"),
            pytest.raises(ReportRenderError, match=re.escape("missing-logo.png")),
        ):
            build_report_html(full_report_data())

    def test_site_name_appears_on_the_cover_and_in_the_page_footer(self) -> None:
        html = build_report_html(cohort_report_data(site_name="Bright Academy"))

        assert "Bright Academy" in html
        assert (
            "Bright Academy · Northside College · Cohort progress report · Cohort A"
            in html
        )
