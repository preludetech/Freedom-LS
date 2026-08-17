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

from django.test import override_settings
from django.utils import timezone

from freedom_ls.reports.render import (
    ReportRenderError,
    _extract_theme_tokens_from_css,
    _find_static,
    _restrictive_url_fetcher,
    build_font_css,
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

        assert "Jamie Educator" in html
        assert "the system" not in html

    def test_missing_requester_falls_back_to_the_system(self) -> None:
        html = build_report_html(_cohort_report_data(requested_by_name=""))

        assert "the system" in html

    def test_confusion_percentage_names_its_denominator(self) -> None:
        html = build_report_html(_full_report_data())

        assert "67% of 12 learners" in html


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


class TestRestrictiveUrlFetcher:
    def test_refuses_a_file_outside_the_allowlist(self) -> None:
        weasyprint_urls = pytest.importorskip("weasyprint.urls")
        allowed = _find_static("reports/print.css").resolve()
        fetch = _restrictive_url_fetcher({allowed})
        # A real, readable file in the same directory as an allowed one: a
        # directory-wide trust would let this through.
        sibling = allowed.parent / "fonts" / "DejaVuSans.ttf"

        with pytest.raises(weasyprint_urls.FatalURLFetchingError):
            fetch(sibling.as_uri())

    def test_refuses_http_urls(self) -> None:
        weasyprint_urls = pytest.importorskip("weasyprint.urls")
        fetch = _restrictive_url_fetcher(set())

        with pytest.raises(weasyprint_urls.FatalURLFetchingError):
            fetch("https://example.invalid/logo.png")

    def test_allows_an_allowlisted_file(self) -> None:
        pytest.importorskip("weasyprint.urls")
        allowed = _find_static("reports/print.css").resolve()
        fetch = _restrictive_url_fetcher({allowed})

        assert fetch(allowed.as_uri()) is not None


class TestBrandingOnTheCover:
    def test_site_logo_is_omitted_when_no_path_is_configured(self) -> None:
        with override_settings(HEADER_LOGO_STATIC_PATH=None):
            html = build_report_html(_full_report_data())

        assert '<img class="cover-logo"' not in html

    def test_site_logo_is_rendered_when_configured(self) -> None:
        with override_settings(HEADER_LOGO_STATIC_PATH="reports/print.css"):
            html = build_report_html(_full_report_data())

        assert '<img class="cover-logo"' in html
        assert "file://" in html

    def test_configured_but_unresolvable_logo_raises(self) -> None:
        with (
            override_settings(HEADER_LOGO_STATIC_PATH="nowhere/missing-logo.png"),
            pytest.raises(ReportRenderError, match=re.escape("missing-logo.png")),
        ):
            build_report_html(_full_report_data())

    def test_site_name_appears_on_the_cover_and_in_the_page_footer(self) -> None:
        html = build_report_html(_cohort_report_data(site_name="Bright Academy"))

        assert "Bright Academy" in html
        assert "Bright Academy · Cohort progress report · Cohort A" in html


class TestNoOptionLettersAnywhere:
    def test_option_text_is_never_prefixed_with_a_letter(self) -> None:
        # FLS does not letter a question's options, so labelling them in the
        # report would invent an ordering the learner never saw.
        html = build_report_html(_full_report_data())

        assert not re.search(r">\s*[A-D]\s+[—-]\s+\w", html)


def _css_declarations(css: str, selector: str) -> dict[str, str]:
    """The declarations of the one rule whose selector list starts a line.

    Anchoring on the line start keeps `.completion-bar-outer` from matching the
    `.student-section .completion-bar-outer` override further down the file.
    """
    match = re.search(
        rf"^{re.escape(selector)}\s*\{{(.*?)\}}", css, re.MULTILINE | re.DOTALL
    )
    assert match is not None, f"No rule in print.css starts a line with {selector!r}"
    declarations = {}
    for line in match.group(1).split(";"):
        if ":" in line:
            prop, _, value = line.partition(":")
            declarations[prop.strip()] = value.strip()
    return declarations


class TestCompletionBarTrackIsVisibleOnEveryRow:
    """The empty track once shared `--color-surface-2` with the zebra stripe.

    On an even summary-table row it therefore vanished: a half-complete learner
    showed a fill with no reference length, and a 0% learner showed no bar at
    all while a 0% learner on a white row showed an empty track. Nothing in the
    suite rasterises print.css, so the invariant is asserted against the
    stylesheet's own source.
    """

    def test_the_track_carries_an_edge_the_row_banding_does_not_hide(self) -> None:
        css = _find_static("reports/print.css").read_text()

        track = _css_declarations(css, ".completion-bar-outer")
        banding = _css_declarations(css, ".summary-tables tbody tr:nth-child(even) td")

        edge = track.get("border") or track.get("outline")
        assert edge is not None, "The track needs an edge, not only a fill"
        assert banding["background"] not in edge
