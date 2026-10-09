"""Tests for freedom_ls.reports.render.

The tests down to the PDF integration section make no WeasyPrint call.
render_report_pdf()'s own PDF output is proven by the pypdf-based integration
tests at the end of this file, marked `weasyprint`. Everything before them
exercises build_report_html(), the theme-token extractor and the report
partials, all pure Python plus a Django template render -- no ORM access, so
none of these tests need `django_db` or `mock_site_context`.
"""

from __future__ import annotations

import base64
import dataclasses
import io
import re
from html import unescape
from uuid import uuid4

import pytest
from fontTools.ttLib import TTFont
from PIL import Image
from pypdf import PdfReader
from pypdf._page import PageObject
from pypdf.generic import Destination
from pypdf.types import OutlineType

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.organisations.validators import MAX_BYTES
from freedom_ls.reports.gather import (
    FOOTER_COHORT_MAX_CHARS,
    FOOTER_LINE_MAX_CHARS,
    FOOTER_ORGANISATION_MAX_CHARS,
    AtRiskFlag,
    AttentionList,
    CohortReportData,
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
    gather_cohort_report_data,
)
from freedom_ls.reports.render import (
    ReportRenderError,
    _build_document,
    _extract_theme_tokens_from_css,
    _find_static,
    _restrictive_url_fetcher,
    build_font_css,
    build_report_html,
    extract_theme_tokens,
    render_report_pdf,
)
from freedom_ls.reports.tests.helpers import requires_tailwind_bundle
from freedom_ls.reports.tests.report_data_builders import (
    GENERATED_AT,
    cohort_report_data,
    course_section,
    course_section_defaults,
    full_report_data,
    learner_detail,
    organisation_brand,
    summary_row,
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
            "--color-on-surface:",
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

        assert 'data-empty-state="cover-courses"' in html

    def test_cohort_with_no_courses_states_so_under_summary_tables(self) -> None:
        html = build_report_html(cohort_report_data(courses=[]))

        assert 'data-empty-state="summary-tables"' in html

    def test_course_with_no_learners_states_so_instead_of_a_bare_header_row(
        self,
    ) -> None:
        data = cohort_report_data(courses=[course_section(title="Astronomy")])

        html = build_report_html(data)

        assert 'data-empty-state="course-learners"' in html


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


def _body_of(html: str) -> str:
    """Everything after <body>, which is the only part that is markup.

    build_report_html() inlines print.css into <head>, so a bare substring
    search over the whole document also matches the stylesheet's own class
    names and comment prose -- and would pass whether or not anything was
    actually drawn.
    """
    return html.split("<body>")[1]


def _footer_identity_of(html: str) -> str:
    """The running element print.css draws in every interior page's footer."""
    return html.split('class="footer-identity"')[1].split("</div>")[0]


def _text_of(markup: str) -> str:
    """`markup` as a reader sees it: tags dropped, entities and runs of space resolved."""
    return unescape(re.sub(r"<[^>]+>", "", markup)).strip()


A_LOGO_DATA_URI = "data:image/png;base64,aGVsbG8="

# 150 characters, the longest name an Organisation can carry.
A_LONG_ORGANISATION_NAME = (
    "Northside College of Advanced Hydrology and Environmental Science " * 3
)[:150]


@requires_tailwind_bundle
class TestBrandingOnTheCover:
    def test_a_logo_is_rendered_in_the_brand_slot(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(logo_data_uri=A_LOGO_DATA_URI)
        )

        html = build_report_html(data)

        assert f'<img class="cover-logo" src="{A_LOGO_DATA_URI}"' in html

    def test_a_logo_is_joined_by_the_organisation_name(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(
                logo_data_uri=A_LOGO_DATA_URI, wordmark_name="Northside College"
            )
        )

        html = build_report_html(data)
        body = _body_of(html)

        assert "cover-brand--with-logo" in body
        assert '<img class="cover-logo"' in body
        assert "Northside College" in body.split('class="cover-brand')[1]

    def test_an_organisation_without_a_logo_gets_a_wordmark(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(wordmark_name="Northside College")
        )

        html = build_report_html(data)

        assert "cover-wordmark" in _body_of(html)
        assert '<img class="cover-logo"' not in html

    def test_the_wordmark_carries_the_size_class_from_the_data(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(wordmark_size_class="condensed")
        )

        html = build_report_html(data)

        assert "cover-wordmark--condensed" in _body_of(html)

    def test_the_wordmark_is_cut_while_the_metadata_row_states_the_name_whole(
        self,
    ) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(
                name=A_LONG_ORGANISATION_NAME,
                wordmark_name="Northside College of Advanced Hydrology…",
            )
        )

        html = build_report_html(data)

        brand_slot = html.split('class="cover-brand"')[1].split("</div>")[0]
        metadata_row = html.split('data-meta="organisation"')[1].split("</dd>")[0]
        assert brand_slot.count("Northside College of Advanced Hydrology…") == 1
        assert A_LONG_ORGANISATION_NAME not in brand_slot
        assert A_LONG_ORGANISATION_NAME in metadata_row

    def test_the_footer_identity_line_leads_with_the_organisation(self) -> None:
        html = build_report_html(cohort_report_data())
        footer = _footer_identity_of(html)

        assert "Northside College" in footer
        assert "Cohort A" in footer
        assert "Cohort progress report" not in footer

    def test_the_footer_identity_line_stacks_the_cohort_under_the_organisation(
        self,
    ) -> None:
        html = build_report_html(cohort_report_data())
        footer = _footer_identity_of(html)

        assert footer.index("Northside College") < footer.index("Cohort A")
        assert '<span class="footer-org">' in footer
        assert '<span class="footer-doc">' in footer

    def test_neither_footer_line_outgrows_the_margin_box_at_its_longest(self) -> None:
        """The budgets, checked against what the template actually composes.

        Read off the render rather than added up by hand, so a literal added to
        either line is counted without anyone remembering to widen the sum. A
        PDF-text assertion cannot stand in for this: extracting text rejoins
        wrapped lines, so a line that overflowed would read back as if it fit.
        """
        data = cohort_report_data(
            organisation=organisation_brand(
                footer_name="W" * FOOTER_ORGANISATION_MAX_CHARS
            ),
            footer_cohort_name="W" * FOOTER_COHORT_MAX_CHARS,
        )

        footer = _footer_identity_of(build_report_html(data))
        lines = [
            _text_of(line) for line in re.findall(r"<span[^>]*>(.*?)</span>", footer)
        ]

        assert len(lines) == 2
        for line in lines:
            assert len(line) <= FOOTER_LINE_MAX_CHARS

    def test_the_platform_mark_appears_on_the_band_and_in_the_footer(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=True)

        html = build_report_html(data)

        body = _body_of(html)
        assert "band-powered-by" in body
        assert "footer-powered-by" in body

    def test_the_house_organisation_gets_no_platform_mark(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=False)

        html = build_report_html(data)

        body = _body_of(html)
        assert "band-powered-by" not in body
        assert "footer-powered-by" not in body


@requires_tailwind_bundle
class TestThePlatformMarkOnTheReport:
    """The two logo variants, and which slot reaches for which.

    Overridden onto the report's own font files rather than the branding
    assets: these tests care that a configured path is resolved, embedded and
    allowlisted, not what the image is of, and a font file is a static asset
    the finders resolve in every environment the suite runs in.
    """

    LIGHT = "reports/fonts/DejaVuSans.ttf"
    DARK = "reports/fonts/DejaVuSans-Bold.ttf"

    def _url(self, static_path: str) -> str:
        return _find_static(static_path).resolve().as_uri()

    @override_settings(HEADER_LOGO_STATIC_PATH=LIGHT)
    def test_the_footer_carries_the_light_variant(self) -> None:
        html = build_report_html(cohort_report_data(show_powered_by=True))

        footer = html.split('class="footer-powered-by"')[1].split("</div>")[0]
        assert f'<img class="footer-logo" src="{self._url(self.LIGHT)}"' in footer

    @override_settings(HEADER_LOGO_ON_DARK_STATIC_PATH=DARK)
    def test_the_band_carries_the_dark_variant(self) -> None:
        html = build_report_html(cohort_report_data(show_powered_by=True))

        band = html.split('class="cover-band"')[1].split("</div>")[0]
        assert f'<img class="band-logo" src="{self._url(self.DARK)}"' in band

    @override_settings(
        HEADER_LOGO_STATIC_PATH=LIGHT, HEADER_LOGO_ON_DARK_STATIC_PATH=DARK
    )
    def test_each_slot_reaches_for_its_own_variant(self) -> None:
        html = build_report_html(cohort_report_data(show_powered_by=True))

        band = html.split('class="cover-band"')[1].split("</div>")[0]
        footer = html.split('class="footer-powered-by"')[1].split("</div>")[0]
        assert self._url(self.DARK) in band
        assert self._url(self.LIGHT) not in band
        assert self._url(self.LIGHT) in footer
        assert self._url(self.DARK) not in footer

    @override_settings(
        HEADER_LOGO_STATIC_PATH=None, HEADER_LOGO_ON_DARK_STATIC_PATH=None
    )
    def test_an_unconfigured_mark_leaves_the_text_standing_alone(self) -> None:
        html = build_report_html(cohort_report_data(show_powered_by=True))

        body = _body_of(html)
        assert "band-logo" not in body
        assert "footer-logo" not in body
        assert "band-powered-by" in body
        assert "footer-powered-by" in body

    @override_settings(
        HEADER_LOGO_STATIC_PATH=LIGHT, HEADER_LOGO_ON_DARK_STATIC_PATH=DARK
    )
    def test_the_house_organisation_gets_neither_variant(self) -> None:
        body = _body_of(build_report_html(cohort_report_data(show_powered_by=False)))

        assert "band-logo" not in body
        assert "footer-logo" not in body

    @override_settings(HEADER_LOGO_STATIC_PATH="images/no-such-logo.png")
    def test_a_configured_mark_that_cannot_be_resolved_raises(self) -> None:
        with pytest.raises(ReportRenderError, match="no-such-logo"):
            build_report_html(cohort_report_data(show_powered_by=True))

    @override_settings(
        HEADER_LOGO_STATIC_PATH=LIGHT, HEADER_LOGO_ON_DARK_STATIC_PATH=DARK
    )
    def test_both_variants_reach_the_fetcher_allowlist(self) -> None:
        """Resolving the marks is not enough -- the fetcher refuses what it is not told about."""
        _, allowed_paths = _build_document(cohort_report_data(show_powered_by=True))

        assert _find_static(self.LIGHT).resolve() in allowed_paths
        assert _find_static(self.DARK).resolve() in allowed_paths

    def test_an_organisation_name_is_escaped_on_the_cover(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(name="Ampersand <script> & Co")
        )

        html = build_report_html(data)

        assert "<script>" not in html
        assert "Ampersand &lt;script&gt; &amp; Co" in html

    def test_an_organisation_name_is_escaped_in_the_footer_running_element(
        self,
    ) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(footer_name="Ampersand <script> & Co")
        )

        html = build_report_html(data)

        footer = html.split('class="footer-identity"')[1]
        assert "<script>" not in footer
        assert "Ampersand &lt;script&gt; &amp; Co" in footer


# Per-partial tests for the report templates.
#
# Each partial is rendered directly via `render_to_string("reports/partials/<name>.html", {...})`
# with a minimal hand-built context — a couple of `freedom_ls.reports.gather` dataclass
# instances, never a whole `CohortReportData` built through the ORM. No database access
# happens anywhere in this file, so none of these tests need `django_db` or
# `mock_site_context`: the dataclasses under test are plain, frozen Python objects.
#
# The whole-document tier is out of scope here: `build_report_html()` resolves fonts, the
# theme bundle and the cover logo before it renders, and those are exercised in the build_report_html tests above.

# The template only ever interpolates this, so any well-formed URL will do.
A_LOGO_FILE_URL = "file:///static/images/platform-logo-on-dark.png"


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
        assert "flag-list-empty" not in html

    def test_renders_no_flags_when_empty(self) -> None:
        html = render_to_string("reports/partials/flag_list.html", {"flags": []})

        assert "flag-list-empty" in html


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

        assert 'data-empty-state="course-items"' in html
        assert "completion-ratio" not in html
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

        assert f'href="#learner-{learner.learner_id}"' in html
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

        assert "attention-list-empty" in html


class TestContents:
    def test_links_to_course_and_learner_anchors(self) -> None:
        course = course_section_with_one_summary_table(title="Course X")
        learner = learner_detail(full_name="Robin Fox")
        data = cohort_report_data(courses=[course], learners=[learner])

        html = render_to_string("reports/partials/contents.html", {"data": data})

        assert f'href="#course-{course.course_id}"' in html
        assert f'href="#learner-{learner.learner_id}"' in html

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

        legend = html.split('class="legend"')[1]
        assert {"✓", "✗", "▲", "●", "○", "—"} <= set(legend)

    def test_states_the_rules_the_figures_are_read_under(self) -> None:
        """Each figure in the report is defensible only against a stated rule, and
        the report travels without whoever generated it — an educator reading a
        printout has nowhere else to look these up.
        """
        html = render_to_string("reports/partials/methodology.html", {})

        stated = set(re.findall(r'data-methodology-rule="([^"]+)"', html))

        assert {
            "complete",
            "quiz-score",
            "attempt",
            "cohort-analysis",
            "multi-select-scoring",
            "answers-given",
            "pass-marks",
            "excluded",
            "covered",
        } <= stated


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
            learner_id=uuid4(),
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
            learner_id=uuid4(),
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

        assert "no-activity" in html
        assert "no-activity-started" not in html

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

        assert "no-activity" not in html
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

        assert "no-activity" not in html
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

        assert "no-activity" not in html
        assert 'data-subhead="wrong-answers"' in html
        assert "Erosion Quiz" in html

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

        assert "no-answer" in html

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
        learner = learner_detail()

        html = render_to_string(
            "reports/partials/learner_detail.html", {"learner": learner}
        )

        assert f'id="learner-{learner.learner_id}"' in html

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

        # One heading per quiz, each naming the quiz it introduces.
        headings = re.findall(
            r'data-subhead="wrong-answers"[^>]*>(.*?)</p>', html, re.S
        )
        assert len(headings) == 2
        assert "Voltage Quiz" in headings[0]
        assert "Erosion Quiz" in headings[1]
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

        assert 'data-subhead="wrong-answers"' not in html


class TestLearnerDetails:
    def test_states_the_situation_when_the_cohort_has_no_learners(self) -> None:
        html = render_to_string(
            "reports/partials/learner_details.html", {"learners": []}
        )

        assert 'data-empty-state="learner-details"' in html

    def test_renders_one_block_per_learner(self) -> None:
        learners = [
            learner_detail(full_name="Ann Lee", sort_key=("Lee", "Ann")),
            learner_detail(full_name="Bo Kim", sort_key=("Kim", "Bo")),
        ]

        html = render_to_string(
            "reports/partials/learner_details.html", {"learners": learners}
        )

        assert f'id="learner-{learners[0].learner_id}"' in html
        assert f'id="learner-{learners[1].learner_id}"' in html
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
        assert 'data-empty-state="confusions"' not in html

    def test_states_the_situation_when_there_are_no_courses(self) -> None:
        html = render_to_string("reports/partials/confusions.html", {"courses": []})

        assert 'data-empty-state="confusions"' in html

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

        assert 'data-empty-state="confusions"' in html

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
        assert 'data-empty-state="confusions"' not in html

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

        assert 'data-subhead="quiz-attempts"' in html
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
        attempts_table = html.split('data-subhead="quiz-attempts"')[1]
        assert "○" in attempts_table
        assert "✓" not in attempts_table
        assert "✗" not in attempts_table


class TestCoverBranding:
    def test_an_organisation_without_a_logo_gets_a_wordmark(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(wordmark_name="Northside College")
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "cover-wordmark" in html
        assert '<img class="cover-logo"' not in html

    def test_an_organisation_logo_is_rendered_from_its_data_uri(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(
                logo_data_uri="data:image/png;base64,aGVsbG8="
            )
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert 'src="data:image/png;base64,aGVsbG8="' in html

    def test_the_organisation_name_is_set_beneath_its_logo(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(
                logo_data_uri="data:image/png;base64,aGVsbG8=",
                wordmark_name="Northside College",
            )
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})
        brand_slot = html.split('class="cover-brand')[1].split("</div>")[0]

        assert "cover-brand--with-logo" in html
        assert brand_slot.index("cover-logo") < brand_slot.index("Northside College")

    def test_the_band_carries_the_platform_mark(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=True)

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "band-powered-by" in html
        assert "Bright Academy" in html

    def test_the_band_is_blank_for_the_house_organisation(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=False)

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "band-powered-by" not in html
        assert "Bright Academy" not in html

    def test_the_band_carries_the_reversed_mark_beside_the_name(self) -> None:
        data = cohort_report_data(show_powered_by=True)

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_on_dark_url": A_LOGO_FILE_URL},
        )

        assert f'<img class="band-logo" src="{A_LOGO_FILE_URL}"' in html
        assert "band-powered-by" in html

    def test_the_band_carries_no_mark_without_a_reversed_variant(self) -> None:
        data = cohort_report_data(show_powered_by=True)

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_on_dark_url": None},
        )

        assert "band-logo" not in html
        assert "band-powered-by" in html

    def test_the_house_organisation_gets_no_mark_even_with_a_variant(self) -> None:
        data = cohort_report_data(show_powered_by=False)

        html = render_to_string(
            "reports/partials/title_page.html",
            {"data": data, "site_logo_on_dark_url": A_LOGO_FILE_URL},
        )

        assert "band-logo" not in html
        assert "band-powered-by" not in html

    def test_course_card_states_each_course_scale(self) -> None:
        data = cohort_report_data(
            courses=[
                course_section_with_one_summary_table(title="Astronomy", item_count=24)
            ]
        )

        html = render_to_string("reports/partials/title_page.html", {"data": data})

        assert "24 items" in html


# Integration tests for render_report_pdf() against real PDF output.
#
# Everything else in this app tests the HTML source or the dataclasses feeding
# it; this file is the only place that actually invokes WeasyPrint and inspects
# the resulting bytes with pypdf, proving what only a rendered PDF can prove:
# page orientation, font embedding, glyph coverage, a real outline, and
# resolved table-of-contents page references. `extract_text()` is used only as
# a smoke test throughout -- it carries known spacing artefacts, so no
# assertion here depends on exact whitespace or word order beyond what is
# called out inline.
#
# No PDF byte comparison anywhere -- fonts, timestamps and library versions
# make exact output non-reproducible.
# The six status glyphs used throughout the report (methodology legend,
# quiz_result_cell.html, completion_bar.html, flag_list.html) -- plain
# Unicode, never emoji, per freedom_ls/reports/static/reports/print.css.
STATUS_GLYPH_CODEPOINTS = [0x2713, 0x2717, 0x25B2, 0x25CF, 0x25CB, 0x2014]

# Headings that belong to the per-learner section and must never reach a
# landscape page or the confusions section. Upper-cased where print.css sets
# .subhead in small caps -- the extracted text carries what was drawn, not what
# the template wrote.
LEARNER_DETAIL_HEADINGS = ["Details per learner", "ITEMS COMPLETED", "QUIZ ATTEMPTS"]


def _busy_report_data() -> CohortReportData:
    """`full_report_data()` grown until every page-break case under test exists.

    Every learner in the base fixture has `has_any_progress=False`, so the
    document contains no "Completed items" or "Quiz results" heading at all and
    an assertion that neither appears on a landscape page would hold vacuously.
    The *first* learner is therefore given enough activity to run past one page.

    The *last* learner is left short and given a name that appears nowhere else
    in the document. That combination is what a leaked running header needs:
    his section starts on a fresh page and ends part way down it, so the
    confusions section follows him onto that same page and WeasyPrint fills the
    header from his running element -- the leak QA saw on the first page of the
    section, which a long final learner would hide by ending the page for him.

    The course gets a second quiz whose confusion block is far too big for one
    page, on top of the first quiz's small one, so the section has continuation
    pages to check as well as a first one.
    """
    data = full_report_data()
    first, last = data.learners[0], data.learners[-1]
    course = data.courses[0]
    quiz = course.quizzes[0]
    block = course.confusions_by_quiz[quiz.form_id]
    second_quiz = QuizColumn(
        form_id=uuid4(), title="Gravity Quiz", abbreviation="GQ", pass_percentage=50
    )
    crowded = dataclasses.replace(
        block,
        questions=[
            dataclasses.replace(
                block.questions[0],
                question_number=number,
                question_text=f"Question {number}: what holds a moon in place?",
            )
            for number in range(1, 46)
        ],
        shown=45,
        total=45,
    )
    table = course.summary_tables[0]
    course = dataclasses.replace(
        course,
        quizzes=[quiz, second_quiz],
        summary_tables=[
            dataclasses.replace(
                table,
                quizzes=[quiz, second_quiz],
                rows=[
                    dataclasses.replace(row, cells=[*row.cells, None])
                    for row in table.rows
                ],
            )
        ],
        confusions_by_quiz={quiz.form_id: block, second_quiz.form_id: crowded},
    )
    busy = dataclasses.replace(
        first,
        has_any_progress=True,
        completed_items=[
            CompletedItem(
                title=f"Topic {number}",
                completed_at=data.generated_at,
                is_quiz=False,
            )
            for number in range(60)
        ],
        quiz_results=[
            QuizResult(
                form_id=quiz.form_id,
                title=quiz.title,
                latest_score=3,
                latest_max_score=10,
                latest_percentage=30,
                passed=False,
                attempt_count=1,
                completed_at=data.generated_at,
                attempts=[
                    QuizAttempt(
                        attempt_number=1,
                        completed_at=data.generated_at,
                        score=3,
                        max_score=10,
                        percentage=30,
                        passed=False,
                    )
                ],
            )
        ],
        wrong_answers=[
            QuizWrongAnswers(
                form_id=quiz.form_id,
                title=quiz.title,
                answers=[
                    WrongAnswer(
                        question_number=1,
                        question_text="What is an orbit?",
                        times_wrong=1,
                        selected_options=[SelectedOption("A straight line", False, 1)],
                        correct_option_texts=["A closed path around a body"],
                    )
                ],
            )
        ],
    )
    trailing = dataclasses.replace(last, full_name="Rustam Yusupova-Trelawney")
    return dataclasses.replace(
        data,
        courses=[course, *data.courses[1:]],
        learners=[busy, *data.learners[1:-1], trailing],
    )


def _unregistered_report_data() -> CohortReportData:
    """A cohort whose learners are registered to no course at all.

    The summary tables have nothing but their headings, which is the shape
    that used to let a learner's detail section -- and with it their running
    header -- start on the landscape page.
    """
    data = full_report_data()
    courses = [
        dataclasses.replace(
            course,
            learner_rows=[],
            summary_tables=[
                dataclasses.replace(table, rows=[]) for table in course.summary_tables
            ],
        )
        for course in data.courses
    ]
    return dataclasses.replace(data, courses=courses)


def _with_summary_rows(data: CohortReportData, rows: list) -> CohortReportData:
    """`data` with its first course's single summary table carrying exactly `rows`."""
    course = data.courses[0]
    table = course.summary_tables[0]
    return dataclasses.replace(
        data,
        courses=[
            dataclasses.replace(
                course, summary_tables=[dataclasses.replace(table, rows=rows)]
            ),
            *data.courses[1:],
        ],
    )


def _completion_report_data(percentage: int) -> CohortReportData:
    """`full_report_data()` with its one summary row set to `percentage` complete."""
    data = full_report_data()
    row = dataclasses.replace(
        data.courses[0].summary_tables[0].rows[0],
        completion_percentage=percentage,
        completed_item_count=percentage * 5 // 100,
    )
    return _with_summary_rows(data, [row])


def _banded_zero_completion_report_data() -> CohortReportData:
    """A summary table whose 0%-complete learner sits on a zebra-striped row.

    Row parity is what makes this fixture the case under test: the empty track
    takes its fill from the same token the stripe does, so only on an even row
    is the fill alone incapable of showing the bar.
    """
    data = full_report_data()
    template = data.courses[0].summary_tables[0].rows[0]
    unbanded = dataclasses.replace(
        template, completion_percentage=40, completed_item_count=2
    )
    banded = dataclasses.replace(
        template,
        learner_id=uuid4(),
        full_name="Bo Kim",
        completion_percentage=0,
        completed_item_count=0,
    )
    return _with_summary_rows(data, [unbanded, banded])


@pytest.fixture(scope="module")
def report_pdf_bytes() -> bytes:
    """Render once per module -- WeasyPrint is slow and the output is immutable bytes."""
    return render_report_pdf(full_report_data())


@pytest.fixture(scope="module")
def busy_report_pdf_bytes() -> bytes:
    return render_report_pdf(_busy_report_data())


@pytest.fixture(scope="module")
def unregistered_report_pdf_bytes() -> bytes:
    return render_report_pdf(_unregistered_report_data())


def _reader(pdf_bytes: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(pdf_bytes))


def _is_landscape(page: PageObject) -> bool:
    mediabox = page.mediabox
    return bool(mediabox.width > mediabox.height)


def _landscape_page_texts(reader: PdfReader) -> list[str]:
    return [page.extract_text() for page in reader.pages if _is_landscape(page)]


def _portrait_page_texts(reader: PdfReader) -> list[str]:
    return [page.extract_text() for page in reader.pages if not _is_landscape(page)]


def _embedded_font_program(reader: PdfReader, base_font_suffix: str) -> bytes | None:
    """Raw TrueType program bytes for the first font whose /BaseFont ends with `base_font_suffix`.

    WeasyPrint prefixes every embedded subset with a random six-letter tag
    (e.g. `ABCDEF+DejaVu-Sans`), so matching is by suffix, never the full name.
    """
    for page in reader.pages:
        resources = page.get("/Resources")
        fonts = resources.get("/Font") if resources is not None else None
        if fonts is None:
            continue
        for font_ref in fonts.values():
            font = font_ref.get_object()
            if not str(font.get("/BaseFont", "")).endswith(base_font_suffix):
                continue
            descendants = font.get("/DescendantFonts")
            if not descendants:
                continue
            descriptor = descendants[0].get_object()["/FontDescriptor"].get_object()
            font_file = descriptor.get("/FontFile2")
            if font_file is not None:
                data: bytes = font_file.get_object().get_data()
                return data
    return None


def _embedded_font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        resources = page.get("/Resources")
        fonts = resources.get("/Font") if resources is not None else None
        if fonts is None:
            continue
        for font_ref in fonts.values():
            names.add(str(font_ref.get_object().get("/BaseFont", "")))
    return names


def _font_cmap_codepoints(font_program: bytes) -> set[int]:
    font = TTFont(io.BytesIO(font_program))
    codepoints: set[int] = set()
    for table in font["cmap"].tables:
        codepoints |= set(table.cmap)
    return codepoints


def _embedded_codepoints(reader: PdfReader) -> set[int]:
    """Every code point the document's embedded faces can draw between them."""
    covered: set[int] = set()
    for name in _embedded_font_names(reader):
        program = _embedded_font_program(reader, name.split("+")[-1])
        if program is not None:
            covered |= _font_cmap_codepoints(program)
    return covered


def _flatten_outline_titles(entries: OutlineType) -> list[str]:
    titles: list[str] = []
    for entry in entries:
        if isinstance(entry, list):
            titles.extend(_flatten_outline_titles(entry))
        else:
            titles.append(str(entry.title))
    return titles


def _top_level_outline_titles(entries: OutlineType) -> list[str]:
    return [entry.title for entry in entries if isinstance(entry, Destination)]


def _contents_page_text(reader: PdfReader) -> str:
    # contents.html's kicker sits immediately above its heading, and nothing
    # else in the document carries that pair -- "Contents and definitions"
    # alone would also match the running header of the section's later pages.
    return next(
        page.extract_text()
        for page in reader.pages
        if "HOW TO READ THIS REPORT\nContents and definitions" in page.extract_text()
    )


def _contents_page_reference_numbers(reader: PdfReader) -> list[int]:
    """Numeric page references from the contents page's target-counter() links.

    WeasyPrint's extracted text stream places each `target-counter(attr(href),
    page)` link's floated number ahead of the page's normal-flow text rather
    than beside the entry it annotates -- a known pypdf extraction ordering
    artefact -- so the numbers are recovered as the run of integers before
    the "Contents" heading itself, not by pairing each number with its entry.
    """
    text = _contents_page_text(reader)
    prefix = text[: text.index("Contents")]
    return [int(token) for token in re.findall(r"\d+", prefix)]


def _joined_text(reader: PdfReader) -> str:
    return "".join(page.extract_text() for page in reader.pages)


def _names_appearing_in(data: CohortReportData, text: str) -> set[str]:
    """Which of the cohort's learners `text` names -- empty is the passing case."""
    return {learner.full_name for learner in data.learners if learner.full_name in text}


def _confusions_section_page_texts(reader: PdfReader) -> list[str]:
    """Text of every page of the confusions section, its own first page included.

    Anchored on the *last* page carrying the section heading, because the same
    string appears earlier as an entry on the contents page. Anchoring on
    quiz_confusion.html's caution line instead would silently skip the section's
    first page whenever the first block is pushed off it, which is exactly the
    page a running-header leak lands on. Everything from there to the end of the
    document belongs to the section: confusions is the last include in
    report.html.
    """
    texts = [page.extract_text() for page in reader.pages]
    first = max(
        index
        for index, text in enumerate(texts)
        if "Quiz confusions across the cohort" in text.replace("\n", " ")
    )
    return texts[first:]


Rect = tuple[float, float, float, float]

# One PDF path/painting operator: a colour to paint in, a rectangle to add to the
# current path, or the instruction that paints (`f`/`f*`) or strokes (`S`) it.
_PAINT_OP = re.compile(
    r"(?P<rgb>[\d.]+ [\d.]+ [\d.]+) rg"
    r"|(?P<gray>(?<![\d.])[\d.]+) g\b"
    r"|(?P<rect>[-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+) re\b"
    r"|(?P<paint>f\*?|S)\b"
)


def _landscape_fills(reader: PdfReader) -> list[tuple[str, Rect]]:
    """(fill colour, rectangle) for every rectangle filled on the landscape page.

    WeasyPrint paints a box's background across its whole border box, then the
    border itself as an even-odd ring over that same outer rectangle in the
    border colour. A bordered box therefore appears here twice under two
    colours, while an unbordered one appears only under its background.
    """
    page = next(page for page in reader.pages if _is_landscape(page))
    content = page.get_contents()
    assert content is not None
    stream = content.get_data().decode("latin-1")

    colour: str | None = None
    path: list[Rect] = []
    filled: list[tuple[str, Rect]] = []
    for match in _PAINT_OP.finditer(stream):
        if match.group("rgb") or match.group("gray"):
            colour = match.group("rgb") or match.group("gray")
        elif match.group("rect"):
            x, y, width, height = (
                round(float(value), 4) for value in match.group("rect").split()
            )
            path.append((x, y, width, height))
        elif match.group("paint"):
            if match.group("paint").startswith("f") and colour is not None:
                filled.extend((colour, rect) for rect in path)
            path = []
    return filled


def _landscape_rect_widths(reader: PdfReader) -> list[float]:
    """Width of every rectangle painted on the landscape summary page.

    A completion bar whose fill is drawn at its declared percentage is visible
    here as a rectangle of that width -- and one whose fill is not drawn at all
    is visible as a zero-width one. Nothing else on this page paints a
    zero-width rectangle.
    """
    return [width for _, (_, _, width, _) in _landscape_fills(reader)]


def _bordered_boxes(filled: list[tuple[str, Rect]]) -> dict[Rect, set[str]]:
    """Every rectangle painted in more than one colour, keyed to those colours.

    Two colours on one rectangle means a background plus a border ring; the
    completion bar tracks are the only boxes the summary page draws that way.
    """
    colours_by_rect: dict[Rect, set[str]] = {}
    for colour, rect in filled:
        colours_by_rect.setdefault(rect, set()).add(colour)
    return {
        rect: colours for rect, colours in colours_by_rect.items() if len(colours) > 1
    }


def _colours_behind(filled: list[tuple[str, Rect]], box: Rect) -> set[str]:
    """Colours painted on the rectangles enclosing `box` -- its table cell and the page."""
    left, bottom, width, height = box
    return {
        colour
        for colour, (x, y, other_width, other_height) in filled
        if (x, y, other_width, other_height) != box
        and x <= left
        and y <= bottom
        and x + other_width >= left + width
        and y + other_height >= bottom + height
    }


def _png_bytes(width: int = 64, height: int = 32) -> bytes:
    """A genuine, decodable PNG for an organisation's logo field."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _page_has_image_xobject(page: PageObject) -> bool:
    resources = page.get("/Resources")
    xobjects = resources.get("/XObject") if resources is not None else None
    if xobjects is None:
        return False
    return any(
        xobject.get_object().get("/Subtype") == "/Image"
        for xobject in xobjects.values()
    )


def _any_page_has_image_xobject(reader: PdfReader) -> bool:
    return any(_page_has_image_xobject(page) for page in reader.pages)


@pytest.mark.weasyprint
@requires_tailwind_bundle
class TestRenderReportPdf:
    def test_output_parses_as_a_well_formed_pdf(self, report_pdf_bytes: bytes) -> None:
        reader = _reader(report_pdf_bytes)

        assert reader.get_num_pages() > 0

    def test_summary_tables_page_is_landscape_while_other_pages_are_portrait(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)
        landscape_texts = _landscape_page_texts(reader)
        portrait_texts = _portrait_page_texts(reader)

        assert len(landscape_texts) == 1
        assert len(portrait_texts) >= 1
        assert "Summary of learner progress" in landscape_texts[0]

    def test_every_font_the_report_uses_is_embedded_as_a_subset(
        self, report_pdf_bytes: bytes
    ) -> None:
        # Which faces these are is a setting, so naming the shipped default's
        # families would be asserting configuration through the code under
        # test. The claim that survives a re-skin is that the report carries
        # its fonts rather than leaning on whatever the printer happens to
        # have: WeasyPrint tags every subset it embeds `ABCDEF+Family`.
        reader = _reader(report_pdf_bytes)

        embedded = _embedded_font_names(reader)

        assert embedded != set()
        assert {name for name in embedded if "+" not in name} == set()

    def test_every_status_glyph_is_covered_by_an_embedded_font(
        self, report_pdf_bytes: bytes
    ) -> None:
        # "A font is embedded" and "this font can draw these glyphs" are
        # different claims, and a code point no embedded face carries is drawn
        # as a hollow .notdef box -- invisible until somebody reads a printed
        # report. Asserted over every embedded face rather than a named one:
        # which faces the report uses is a setting, and WeasyPrint falls back
        # per glyph, so the guarantee that matters is that the set of faces
        # covers the vocabulary between them.
        reader = _reader(report_pdf_bytes)

        covered = _embedded_codepoints(reader)

        assert set(STATUS_GLYPH_CODEPOINTS) <= covered

    def test_outline_is_nonempty_and_names_document_sections(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)
        data = full_report_data()
        titles = _flatten_outline_titles(reader.outline)

        assert titles != []
        assert data.learners[0].full_name in titles
        assert data.learners[1].full_name in titles

    def test_outline_top_level_is_exactly_the_document_sections(
        self, report_pdf_bytes: bytes
    ) -> None:
        # WeasyPrint's UA stylesheet bookmarks every heading at its own depth,
        # so without print.css's `bookmark-level: none` reset the outline's top
        # level is whatever the page happened to break on. These are the
        # sections report.html includes, in include order; the cover has no
        # section heading and the methodology is part of the contents section.
        reader = _reader(report_pdf_bytes)

        assert _top_level_outline_titles(reader.outline) == [
            "Cohort at a glance",
            "Contents and definitions",
            "Summary of learner progress",
            "Details per learner",
            "Quiz confusions across the cohort",
        ]

    def test_outline_names_every_course_learner_and_analysed_quiz_once(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        data = _busy_report_data()
        titles = _flatten_outline_titles(reader.outline)

        assert len(titles) == len(set(titles))
        assert {learner.full_name for learner in data.learners} <= set(titles)
        assert all(
            any(title.startswith(course.title) for title in titles)
            for course in data.courses
        )
        assert data.courses[0].quizzes[0].title in titles

    def test_outline_omits_the_sub_headings_the_contents_page_does_not_list(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        titles = _flatten_outline_titles(reader.outline)

        assert "Items completed" not in titles
        assert "Quiz attempts" not in titles
        assert "Courses covered" not in titles
        assert "Status legend" not in titles
        assert "Learners needing attention" not in titles

    @pytest.mark.parametrize("heading", LEARNER_DETAIL_HEADINGS)
    def test_no_landscape_page_carries_learner_detail_content(
        self, busy_report_pdf_bytes: bytes, heading: str
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        landscape_text = "".join(_landscape_page_texts(reader))

        # Present in the document, so its absence below is a real page-break
        # assertion rather than one about a heading this fixture never renders.
        assert heading in "".join(_portrait_page_texts(reader))
        assert heading not in landscape_text

    def test_no_landscape_page_names_a_learner_when_none_is_registered(
        self, unregistered_report_pdf_bytes: bytes
    ) -> None:
        # A cohort registered to no course leaves the summary tables empty, so
        # any learner name reaching a landscape page got there through the
        # running header the bare `@page` rule sets, not through a table row.
        reader = _reader(unregistered_report_pdf_bytes)
        data = _unregistered_report_data()
        landscape_text = "".join(_landscape_page_texts(reader))

        assert _names_appearing_in(data, landscape_text) == set()

    def test_no_page_of_the_confusions_section_names_a_learner(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        # Two distinct leaks, and the section's first page is where the harder
        # one lives: WeasyPrint fills the header from the first running element
        # on a page, so while this section shared a page with the last learner's
        # detail section its own reset element could never win. Nothing in a
        # cohort-wide section names a learner, so any name on these pages came
        # from the running header.
        reader = _reader(busy_report_pdf_bytes)
        data = _busy_report_data()
        section_texts = _confusions_section_page_texts(reader)

        assert len(section_texts) > 1, "fixture must span a first and a later page"
        assert _names_appearing_in(data, "".join(section_texts)) == set()

    def test_confusions_section_starts_on_a_page_of_its_own(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        first_page_text = _confusions_section_page_texts(reader)[0]

        assert "Quiz confusions across the cohort" in first_page_text
        # The section heading is the first thing on the page, not something
        # stranded alone on the page before it.
        assert "Orbit Quiz" in first_page_text
        assert {
            heading for heading in LEARNER_DETAIL_HEADINGS if heading in first_page_text
        } == set()

    def test_an_empty_completion_bar_paints_a_zero_width_fill(self) -> None:
        # The fill is a percentage-width box inside a fixed-width track. Drawn
        # as an inline box its width is ignored entirely, so an empty bar and a
        # full one would paint the same rectangle.
        widths = _landscape_rect_widths(
            _reader(render_report_pdf(_completion_report_data(0)))
        )

        assert 0.0 in widths

    def test_a_full_completion_bar_paints_no_zero_width_fill(self) -> None:
        widths = _landscape_rect_widths(
            _reader(render_report_pdf(_completion_report_data(100)))
        )

        assert 0.0 not in widths

    def test_a_completion_bar_stays_visible_where_the_row_banding_matches_its_fill(
        self,
    ) -> None:
        """The empty track takes its fill from the same theme token the zebra
        stripe does, so on a banded row the fill alone leaves nothing to see: a
        0%-complete learner showed no bar at all, while the same learner on a
        white row showed an empty track. The track's border is what keeps it on
        the page.
        """
        reader = _reader(render_report_pdf(_banded_zero_completion_report_data()))
        filled = _landscape_fills(reader)

        # The tracks whose own fill is a colour already painted behind them --
        # the ones sitting on a stripe, where the fill cannot be what shows the bar.
        hidden_fill = {
            box: colours
            for box, colours in _bordered_boxes(filled).items()
            if colours & _colours_behind(filled, box)
        }

        assert hidden_fill, "no track sits on a stripe matching its fill"
        assert all(
            colours - _colours_behind(filled, box)
            for box, colours in hidden_fill.items()
        )

    def test_contents_page_references_are_present_and_non_decreasing(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)

        numbers = _contents_page_reference_numbers(reader)

        assert numbers != []
        assert numbers == sorted(numbers)

    def test_cohort_name_appears_in_extracted_text(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)
        data = full_report_data()

        assert data.cohort_name in _joined_text(reader)


@pytest.mark.weasyprint
@requires_tailwind_bundle
@pytest.mark.django_db
class TestOrganisationBranding:
    """Proof that the organisation's brand reaches the rendered PDF itself.

    Everything above renders `full_report_data()`, a pure dataclass tree; these
    tests are the only place in the app that runs the whole pipeline --
    `gather_cohort_report_data()` against real rows, through
    `render_report_pdf()` -- so they are the only place that can prove the
    logo never goes through `.path()`, or that a real WeasyPrint document
    metadata dictionary carries what the templates set.
    """

    def test_an_organisation_logo_embeds_in_the_rendered_pdf(
        self, mock_site_context, pathless_logo_storage
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("logo.png", ContentFile(_png_bytes()))
        cohort = CohortFactory(organisation=organisation)

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)
        reader = _reader(render_report_pdf(data))

        assert _any_page_has_image_xobject(reader)

    def test_pdf_metadata_names_the_organisation_and_the_site(
        self, mock_site_context
    ) -> None:
        cohort = CohortFactory(
            organisation=OrganisationFactory(name="Northside College")
        )

        with override_settings(HEADER_TITLE=None):
            data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)
        metadata = _reader(render_report_pdf(data)).metadata

        assert metadata is not None
        assert metadata.author == "Northside College"
        assert metadata.creator == mock_site_context.name
        # WeasyPrint joins every <meta name="author"> tag it finds with ", "
        # into one /Author field, so a second one -- the site, say -- would
        # read as "Org, Site" rather than naming the organisation alone.
        assert ", " not in metadata.author

    def test_the_cover_page_carries_no_powered_by_margin_box(
        self, mock_site_context
    ) -> None:
        cohort = CohortFactory(organisation=OrganisationFactory())

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)
        cover_text = _reader(render_report_pdf(data)).pages[0].extract_text()

        # Once, on the band -- not twice, which is what a base @page
        # `@bottom-center` would print if `@page :first` had not cleared it.
        assert cover_text.count("Powered by") == 1

    def test_an_interior_page_carries_the_powered_by_footer(
        self, mock_site_context
    ) -> None:
        cohort = CohortFactory(
            organisation=OrganisationFactory(name="Northside College")
        )

        with override_settings(HEADER_TITLE=None):
            data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)
        reader = _reader(render_report_pdf(data))
        # Page 0 is the cover; the report's second section is the first page
        # that carries the interior footer.
        interior_text = reader.pages[1].extract_text()

        assert f"Powered by {mock_site_context.name}" in interior_text
        # The two lines are asserted separately: the identity block sets the
        # organisation above the cohort, and extraction reports them in that
        # order but with the line break between them rendered as whitespace it
        # is not worth pinning.
        assert data.organisation.footer_name in interior_text
        assert data.footer_cohort_name in interior_text
        assert "Cohort progress report" not in interior_text

    def test_the_house_organisation_gets_no_powered_by_mark_anywhere(
        self, mock_site_context
    ) -> None:
        cohort = CohortFactory(organisation=get_default_organisation(mock_site_context))

        data = gather_cohort_report_data(str(cohort.id), mock_site_context.pk)
        reader = _reader(render_report_pdf(data))

        assert "Powered by" not in _joined_text(reader)


# The report's own font files, used as stand-in logo assets: these tests care
# that a configured mark is embedded in the right page's resources, not what
# the image is of, and the finders resolve these in every environment the suite
# runs in. WeasyPrint reads them as images regardless of the extension.
_A_LIGHT_MARK = "reports/fonts/DejaVuSans.ttf"


@pytest.mark.weasyprint
@requires_tailwind_bundle
@pytest.mark.django_db
class TestThePlatformMarkInThePdf:
    """Where each logo variant lands once WeasyPrint has drawn the document.

    The text-level assertions above cannot see a mark at all -- an image leaves
    nothing for `extract_text()` to find -- so suppression for the house
    organisation needs proving against the page's image resources too.
    """

    def _rendered(self, site, organisation):
        cohort = CohortFactory(organisation=organisation)
        data = gather_cohort_report_data(str(cohort.id), site.pk)
        return _reader(render_report_pdf(data))

    def test_an_interior_page_carries_the_mark(self, mock_site_context) -> None:
        with override_settings(HEADER_LOGO_STATIC_PATH=_A_LIGHT_MARK):
            reader = self._rendered(mock_site_context, OrganisationFactory())

        # Page 0 is the cover, whose own margin boxes are cleared.
        assert _page_has_image_xobject(reader.pages[1])

    def test_the_house_organisation_gets_no_mark_on_any_page(
        self, mock_site_context
    ) -> None:
        house = get_default_organisation(mock_site_context)

        with override_settings(HEADER_LOGO_STATIC_PATH=_A_LIGHT_MARK):
            reader = self._rendered(mock_site_context, house)

        assert not _any_page_has_image_xobject(reader)

    def test_an_unconfigured_mark_leaves_the_pages_imageless(
        self, mock_site_context
    ) -> None:
        with override_settings(
            HEADER_LOGO_STATIC_PATH=None, HEADER_LOGO_ON_DARK_STATIC_PATH=None
        ):
            reader = self._rendered(mock_site_context, OrganisationFactory())

        assert not _any_page_has_image_xobject(reader)
