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
    _build_document,
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
    organisation_brand,
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


def _body_of(html: str) -> str:
    """Everything after <body>, which is the only part that is markup.

    build_report_html() inlines print.css into <head>, so a bare substring
    search over the whole document also matches the stylesheet's own class
    names and comment prose -- and would pass whether or not anything was
    actually drawn.
    """
    return html.split("<body>")[1]


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

    def test_a_logo_replaces_the_wordmark_rather_than_joining_it(self) -> None:
        data = cohort_report_data(
            organisation=organisation_brand(logo_data_uri=A_LOGO_DATA_URI)
        )

        html = build_report_html(data)

        assert "cover-wordmark" not in _body_of(html)

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
        metadata_row = html.split("<dt>Organisation</dt>")[1].split("<dt>")[0]
        assert brand_slot.count("Northside College of Advanced Hydrology…") == 1
        assert A_LONG_ORGANISATION_NAME not in brand_slot
        assert A_LONG_ORGANISATION_NAME in metadata_row

    def test_the_footer_identity_line_leads_with_the_organisation(self) -> None:
        html = build_report_html(cohort_report_data())

        assert "Northside College · Cohort A · Cohort progress report" in html

    def test_the_platform_mark_appears_on_the_band_and_in_the_footer(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=True)

        html = build_report_html(data)

        assert _body_of(html).count("Powered by") == 2

    def test_the_house_organisation_gets_no_platform_mark(self) -> None:
        data = cohort_report_data(site_name="Bright Academy", show_powered_by=False)

        html = build_report_html(data)

        assert "Powered by" not in _body_of(html)


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
        assert body.count("Powered by") == 2

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
