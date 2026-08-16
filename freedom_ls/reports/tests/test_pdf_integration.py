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

import dataclasses
import io
import re
from uuid import uuid4

import pytest
from fontTools.ttLib import TTFont
from pypdf import PdfReader
from pypdf._page import PageObject
from pypdf.generic import Destination
from pypdf.types import OutlineType

from freedom_ls.reports.gather import (
    CohortReportData,
    CompletedItem,
    QuizAttempt,
    QuizColumn,
    QuizResult,
    QuizWrongAnswers,
    WrongAnswer,
)
from freedom_ls.reports.render import render_report_pdf
from freedom_ls.reports.tests.report_data_builders import _full_report_data

pytestmark = pytest.mark.weasyprint

# The six status glyphs used throughout the report (methodology legend,
# quiz_result_cell.html, completion_bar.html, flag_list.html) -- plain
# Unicode, never emoji, per freedom_ls/reports/static/reports/print.css.
STATUS_GLYPH_CODEPOINTS = [0x2713, 0x2717, 0x25B2, 0x25CF, 0x25CB, 0x2014]


def _busy_report_data() -> CohortReportData:
    """`_full_report_data()` grown until every page-break case under test exists.

    Every student in the base fixture has `has_any_progress=False`, so the
    document contains no "Completed items" or "Quiz results" heading at all and
    an assertion that neither appears on a landscape page would hold vacuously.
    The *first* student is therefore given enough activity to run past one page.

    The *last* student is left short and given a name that appears nowhere else
    in the document. That combination is what a leaked running header needs:
    his section starts on a fresh page and ends part way down it, so the
    confusions section follows him onto that same page and WeasyPrint fills the
    header from his running element -- the leak QA saw on the first page of the
    section, which a long final student would hide by ending the page for him.

    The course gets a second quiz whose confusion block is far too big for one
    page, on top of the first quiz's small one, so the section has continuation
    pages to check as well as a first one.
    """
    data = _full_report_data()
    first, last = data.students[0], data.students[-1]
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
                        selected_option_texts=["A straight line"],
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
        students=[busy, *data.students[1:-1], trailing],
    )


def _unregistered_report_data() -> CohortReportData:
    """A cohort whose students are registered to no course at all.

    The summary tables have nothing but their headings, which is the shape
    that used to let a student's detail section -- and with it their running
    header -- start on the landscape page.
    """
    data = _full_report_data()
    courses = [
        dataclasses.replace(
            course,
            student_rows=[],
            summary_tables=[
                dataclasses.replace(table, rows=[]) for table in course.summary_tables
            ],
        )
        for course in data.courses
    ]
    return dataclasses.replace(data, courses=courses)


def _completion_report_data(percentage: int) -> CohortReportData:
    """`_full_report_data()` with its one summary row set to `percentage` complete."""
    data = _full_report_data()
    course = data.courses[0]
    table = course.summary_tables[0]
    row = dataclasses.replace(
        table.rows[0],
        completion_percentage=percentage,
        completed_item_count=percentage * 5 // 100,
    )
    return dataclasses.replace(
        data,
        courses=[
            dataclasses.replace(
                course, summary_tables=[dataclasses.replace(table, rows=[row])]
            ),
            *data.courses[1:],
        ],
    )


@pytest.fixture(scope="module")
def report_pdf_bytes() -> bytes:
    """Render once per module -- WeasyPrint is slow and the output is immutable bytes."""
    return render_report_pdf(_full_report_data())


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
        if "Question-level confusions" in text.replace("\n", " ")
    )
    return texts[first:]


def _landscape_rect_widths(reader: PdfReader) -> list[float]:
    """Width of every rectangle painted on the landscape summary page.

    WeasyPrint emits each painted box as a PDF `x y w h re` operator, so a
    completion bar whose fill is drawn at its declared percentage is visible
    here as a rectangle of that width -- and one whose fill is not drawn at
    all is visible as a zero-width one. Nothing else on this page paints a
    zero-width rectangle.
    """
    page = next(page for page in reader.pages if _is_landscape(page))
    content = page.get_contents()
    assert content is not None
    stream = content.get_data().decode("latin-1")
    return [
        float(match.group(1))
        for match in re.finditer(r"\S+ \S+ (\S+) \S+ re\b", stream)
    ]


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

    def test_outline_top_level_is_exactly_the_document_sections(
        self, report_pdf_bytes: bytes
    ) -> None:
        # WeasyPrint's UA stylesheet bookmarks every heading at its own depth,
        # so without print.css's `bookmark-level: none` reset the outline's top
        # level is whatever the page happened to break on. These six are the
        # sections report.html includes, in include order.
        reader = _reader(report_pdf_bytes)

        assert _top_level_outline_titles(reader.outline) == [
            "At a glance",
            "Contents",
            "How to read this report",
            "Summary tables",
            "Student details",
            "Question-level confusions",
        ]

    def test_outline_names_every_course_student_and_analysed_quiz_once(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        data = _busy_report_data()
        titles = _flatten_outline_titles(reader.outline)

        assert len(titles) == len(set(titles))
        for student in data.students:
            assert titles.count(student.full_name) == 1
        for course in data.courses:
            assert any(title.startswith(course.title) for title in titles)
        assert data.courses[0].quizzes[0].title in titles

    def test_outline_omits_the_sub_headings_the_contents_page_does_not_list(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        titles = _flatten_outline_titles(reader.outline)

        assert "Completed items" not in titles
        assert "Quiz results" not in titles
        assert "Courses covered" not in titles
        assert "Status legend" not in titles
        assert "Students needing attention" not in titles

    def test_no_landscape_page_carries_student_detail_content(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        landscape_texts = _landscape_page_texts(reader)
        portrait_text = "".join(_portrait_page_texts(reader))

        for heading in ("Student details", "Completed items", "Quiz results"):
            # Present in the document, so absence below is a real page-break
            # assertion rather than an assertion about a heading that never
            # renders in this fixture.
            assert heading in portrait_text
            for text in landscape_texts:
                assert heading not in text

    def test_no_landscape_page_names_a_student_when_none_is_registered(
        self, unregistered_report_pdf_bytes: bytes
    ) -> None:
        # A cohort registered to no course leaves the summary tables empty, so
        # any student name reaching a landscape page got there through the
        # running header the bare `@page` rule sets, not through a table row.
        reader = _reader(unregistered_report_pdf_bytes)
        data = _unregistered_report_data()

        for text in _landscape_page_texts(reader):
            for student in data.students:
                assert student.full_name not in text

    def test_no_page_of_the_confusions_section_names_a_student(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        # Two distinct leaks, and the section's first page is where the harder
        # one lives: WeasyPrint fills the header from the first running element
        # on a page, so while this section shared a page with the last student's
        # detail section its own reset element could never win. Nothing in a
        # cohort-wide section names a student, so any name on these pages came
        # from the running header.
        reader = _reader(busy_report_pdf_bytes)
        data = _busy_report_data()
        section_texts = _confusions_section_page_texts(reader)

        assert len(section_texts) > 1, "fixture must span a first and a later page"
        for text in section_texts:
            for student in data.students:
                assert student.full_name not in text

    def test_confusions_section_starts_on_a_page_of_its_own(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        first_page_text = _confusions_section_page_texts(reader)[0]

        assert "Question-level confusions" in first_page_text
        # The section heading is the first thing on the page, not something
        # stranded alone on the page before it.
        assert "Orbit Quiz" in first_page_text
        for heading in ("Student details", "Completed items", "Quiz results"):
            assert heading not in first_page_text

    def test_completion_bar_fill_is_drawn_at_its_declared_width(self) -> None:
        # The fill is a percentage-width box inside a fixed-width track. Drawn
        # as an inline box its width is ignored entirely, so an empty bar and a
        # full one paint the same zero-width rectangle.
        empty = _landscape_rect_widths(
            _reader(render_report_pdf(_completion_report_data(0)))
        )
        full = _landscape_rect_widths(
            _reader(render_report_pdf(_completion_report_data(100)))
        )

        assert 0.0 in empty
        assert 0.0 not in full

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
