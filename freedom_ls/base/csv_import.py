"""Reading an uploaded CSV file into rows, and writing a CSV of rows back out.

Knows nothing about what the columns mean: the caller names the headers it
accepts and receives each row as a dict of header to cell.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator, Sequence
from typing import Protocol

from freedom_ls.base.csv_safety import UTF8_BOM, escape_csv_formula

MAX_UPLOAD_BYTES = 1_048_576
ACCEPTED_DELIMITERS = (",", ";")
LINE_KEY = "_line"


class CsvImportError(Exception):
    """A whole-file problem, carrying the sentence to show."""


class UploadedFile(Protocol):
    @property
    def size(self) -> int | None: ...

    def read(self) -> bytes: ...


def _delimiter(header_line: str) -> str:
    """The accepted delimiter that appears most in the header line; a comma
    when none appears (a single-column file)."""
    return max(ACCEPTED_DELIMITERS, key=header_line.count)


def _check_headers(
    headers: list[str],
    accepted_headers: Sequence[str],
    required_headers: Sequence[str],
) -> None:
    """Reject the headers with one message naming every problem. An empty
    header is named by its position, since "Unknown column(s): ." says
    nothing."""
    unknown = [
        header or f"unnamed column {position}"
        for position, header in enumerate(headers, start=1)
        if header not in accepted_headers
    ]
    repeated = sorted({header for header in headers if headers.count(header) > 1})
    missing = [header for header in required_headers if header not in headers]
    problems = [
        f"{label}: {', '.join(found)}."
        for label, found in (
            ("Unknown column(s)", unknown),
            ("Repeated column(s)", repeated),
            ("Missing required column(s)", missing),
        )
        if found
    ]
    if problems:
        raise CsvImportError(
            f"{' '.join(problems)} Accepted columns: {', '.join(accepted_headers)}."
        )


def _decode(uploaded_file: UploadedFile) -> str:
    if uploaded_file.size is not None and uploaded_file.size > MAX_UPLOAD_BYTES:
        raise CsvImportError("This file is larger than 1 MB.")
    content = uploaded_file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise CsvImportError("This file is larger than 1 MB.")
    # An .xlsx file is a zip archive, and every zip starts with these bytes.
    if content.startswith(b"PK"):
        raise CsvImportError(
            "This looks like an Excel file. Save it as CSV UTF-8 and upload that."
        )
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError(
            "Save the file as CSV UTF-8 and upload it again."
        ) from None


def parse_csv(
    uploaded_file: UploadedFile,
    *,
    accepted_headers: Sequence[str],
    required_headers: Sequence[str],
    max_rows: int,
) -> list[dict[str, str]]:
    """The data rows of an uploaded CSV file, each a dict of header to cell
    plus `_line`, the row's own line number in the file (the header is line 1).

    Raises `CsvImportError` for anything wrong with the file as a whole. A
    file with too many rows is rejected, never truncated.
    """
    text = _decode(uploaded_file)
    reader = csv.reader(
        io.StringIO(text), delimiter=_delimiter(text.partition("\n")[0]), strict=True
    )
    rows: list[dict[str, str]] = []
    try:
        headers = [header.strip().casefold() for header in next(reader, [])]
        # Spreadsheets end the header line with a delimiter for an empty last
        # column; the cells under it are ignored with it.
        while headers and not headers[-1]:
            headers.pop()
        _check_headers(headers, accepted_headers, required_headers)
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue
            # line_num counts to the end of the record; a quoted cell holding
            # line breaks makes the record start earlier.
            start = reader.line_num - sum(cell.count("\n") for cell in cells)
            row = {
                header: cells[index].strip() if index < len(cells) else ""
                for index, header in enumerate(headers)
            }
            row[LINE_KEY] = str(start)
            rows.append(row)
    except csv.Error as error:
        raise CsvImportError(
            f"The file could not be read at line {reader.line_num}: {error}."
        ) from error
    if not rows:
        raise CsvImportError("This file has no rows to import.")
    if len(rows) > max_rows:
        raise CsvImportError(f"{len(rows):,} rows; the limit is {max_rows:,}.")
    return rows


class EchoWriter:
    """A file-like object whose `write` hands back the string it was given
    instead of buffering it, so `csv.writer` can drive a generator that
    `StreamingHttpResponse` streams one row at a time."""

    def write(self, value: str) -> str:
        return value


def write_error_csv(
    header: Sequence[str], rows: Iterable[Sequence[str]]
) -> Iterator[str]:
    """The CSV text of `rows` under `header`, one chunk per line, starting
    with a byte-order mark so spreadsheets read it as UTF-8. Every cell is
    neutralised against formula injection."""
    writer = csv.writer(EchoWriter())
    yield UTF8_BOM
    yield writer.writerow([escape_csv_formula(cell) for cell in header])
    for row in rows:
        yield writer.writerow([escape_csv_formula(cell) for cell in row])
