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
from freedom_ls.reports.tests.conftest import requires_tailwind_bundle
from freedom_ls.reports.tests.report_data_builders import full_report_data

pytestmark = [pytest.mark.weasyprint, requires_tailwind_bundle]

# The six status glyphs used throughout the report (methodology legend,
# quiz_result_cell.html, completion_bar.html, flag_list.html) -- plain
# Unicode, never emoji, per freedom_ls/reports/static/reports/print.css.
STATUS_GLYPH_CODEPOINTS = [0x2713, 0x2717, 0x25B2, 0x25CF, 0x25CB, 0x2014]

# Headings that belong to the per-learner section and must never reach a
# landscape page or the confusions section. Upper-cased where print.css sets
# .subhead in small caps -- the extracted text carries what was drawn, not what
# the template wrote.
STUDENT_DETAIL_HEADINGS = ["Details per learner", "ITEMS COMPLETED", "QUIZ ATTEMPTS"]


def _busy_report_data() -> CohortReportData:
    """`full_report_data()` grown until every page-break case under test exists.

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
    data = full_report_data()
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
                        selected_options=[("A straight line", 1)],
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
    data = full_report_data()
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
        user_id=2,
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
    return {student.full_name for student in data.students if student.full_name in text}


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
        assert data.students[0].full_name in titles
        assert data.students[1].full_name in titles

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

    def test_outline_names_every_course_student_and_analysed_quiz_once(
        self, busy_report_pdf_bytes: bytes
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        data = _busy_report_data()
        titles = _flatten_outline_titles(reader.outline)

        assert len(titles) == len(set(titles))
        assert {student.full_name for student in data.students} <= set(titles)
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

    @pytest.mark.parametrize("heading", STUDENT_DETAIL_HEADINGS)
    def test_no_landscape_page_carries_student_detail_content(
        self, busy_report_pdf_bytes: bytes, heading: str
    ) -> None:
        reader = _reader(busy_report_pdf_bytes)
        landscape_text = "".join(_landscape_page_texts(reader))

        # Present in the document, so its absence below is a real page-break
        # assertion rather than one about a heading this fixture never renders.
        assert heading in "".join(_portrait_page_texts(reader))
        assert heading not in landscape_text

    def test_no_landscape_page_names_a_student_when_none_is_registered(
        self, unregistered_report_pdf_bytes: bytes
    ) -> None:
        # A cohort registered to no course leaves the summary tables empty, so
        # any student name reaching a landscape page got there through the
        # running header the bare `@page` rule sets, not through a table row.
        reader = _reader(unregistered_report_pdf_bytes)
        data = _unregistered_report_data()
        landscape_text = "".join(_landscape_page_texts(reader))

        assert _names_appearing_in(data, landscape_text) == set()

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
            heading for heading in STUDENT_DETAIL_HEADINGS if heading in first_page_text
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
