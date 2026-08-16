"""Integration tests for render_report_pdf() against real PDF output.

Everything else in this app tests the HTML source or the dataclasses feeding
it; this file is the only place that actually invokes WeasyPrint and inspects
the resulting bytes with pypdf, proving what only a rendered PDF can prove:
page orientation, font embedding, glyph coverage, a real outline, and
resolved table-of-contents page references. `extract_text()` is used only as
a smoke test throughout -- it carries known spacing artefacts, so no
assertion here depends on exact whitespace or word order beyond what is
called out inline.

No PDF byte comparison anywhere -- fonts, timestamps and library versions
make exact output non-reproducible.
"""

from __future__ import annotations

import io
import re

import pytest
from fontTools.ttLib import TTFont
from pypdf import PdfReader
from pypdf._page import PageObject
from pypdf.generic import Destination
from pypdf.types import OutlineType

from freedom_ls.reports.render import render_report_pdf
from freedom_ls.reports.tests.report_data_builders import _full_report_data

pytestmark = pytest.mark.weasyprint

# The six status glyphs used throughout the report (methodology legend,
# quiz_result_cell.html, completion_bar.html, flag_list.html) -- plain
# Unicode, never emoji, per freedom_ls/reports/static/reports/print.css.
STATUS_GLYPH_CODEPOINTS = [0x2713, 0x2717, 0x25B2, 0x25CF, 0x25CB, 0x2014]


@pytest.fixture(scope="module")
def report_pdf_bytes() -> bytes:
    """Render once per module -- WeasyPrint is slow and the output is immutable bytes."""
    return render_report_pdf(_full_report_data())


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


def _font_cmap_codepoints(font_program: bytes) -> set[int]:
    font = TTFont(io.BytesIO(font_program))
    codepoints: set[int] = set()
    for table in font["cmap"].tables:
        codepoints |= set(table.cmap)
    return codepoints


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
    # contents.html's <h2>Contents</h2> is immediately followed by the
    # <li>Courses</li> subheading in document order -- a unique substring
    # that survives extract_text(), unlike "Contents" alone (also the page
    # title on the title page's generated-at line is not literally this
    # string, but "Question-level confusions" appears twice in the document:
    # once as a contents entry here and once as the section heading itself).
    return next(
        page.extract_text()
        for page in reader.pages
        if "Contents\nCourses" in page.extract_text()
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
        assert "Summary tables" in landscape_texts[0]

    def test_bundled_dejavu_font_is_embedded(self, report_pdf_bytes: bytes) -> None:
        reader = _reader(report_pdf_bytes)

        font_program = _embedded_font_program(reader, "+DejaVu-Sans")

        assert font_program is not None
        assert len(font_program) > 0

    def test_embedded_font_cmap_covers_status_glyph_codepoints(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)
        # The status glyphs render bold (print.css: `.status-glyph { font-weight:
        # bold; }`), so they are subset into the bold face, not the regular one.
        font_program = _embedded_font_program(reader, "+DejaVu-Sans-Bold")

        assert font_program is not None
        codepoints = _font_cmap_codepoints(font_program)
        assert set(STATUS_GLYPH_CODEPOINTS) <= codepoints

    def test_outline_is_nonempty_and_names_document_sections(
        self, report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(report_pdf_bytes)
        data = _full_report_data()
        titles = _flatten_outline_titles(reader.outline)

        assert titles != []
        assert data.students[0].full_name in titles
        assert data.students[1].full_name in titles

    def test_course_heading_bookmark_level_places_it_at_the_top_of_the_outline(
        self, report_pdf_bytes: bytes
    ) -> None:
        # print.css sets `h2.course-heading { bookmark-level: 1; }`, overriding
        # WeasyPrint's own default of 2 for h2 -- without that rule this course
        # heading would nest one level inside the title page's h1 instead of
        # sitting as a top-level entry alongside it, so this is the load-bearing
        # proof that the override actually applies rather than the outline
        # merely existing by virtue of WeasyPrint's default heading bookmarks.
        reader = _reader(report_pdf_bytes)
        data = _full_report_data()

        assert data.courses[0].title in _top_level_outline_titles(reader.outline)

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
        data = _full_report_data()

        assert data.cohort_name in _joined_text(reader)
