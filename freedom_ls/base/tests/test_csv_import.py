"""Tests for reading an uploaded CSV and writing an error CSV."""

from __future__ import annotations

import re

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.base.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvImportError,
    parse_csv,
    write_error_csv,
)
from freedom_ls.base.csv_safety import UTF8_BOM

HEADERS = ("email", "name")


def _upload(content: str | bytes) -> SimpleUploadedFile:
    data = content.encode() if isinstance(content, str) else content
    return SimpleUploadedFile("people.csv", data)


def _parse(content: str | bytes, max_rows: int = 10) -> list[dict[str, str]]:
    return parse_csv(
        _upload(content),
        accepted_headers=HEADERS,
        required_headers=("email",),
        max_rows=max_rows,
    )


def test_parse_returns_rows_with_their_line_numbers() -> None:
    rows = _parse("email,name\na@example.com,Ann\nb@example.com,Bob\n")

    assert rows == [
        {"email": "a@example.com", "name": "Ann", "_line": "2"},
        {"email": "b@example.com", "name": "Bob", "_line": "3"},
    ]


def test_parse_accepts_semicolon_delimiter() -> None:
    rows = _parse("email;name\na@example.com;Ann\n")

    assert rows[0]["name"] == "Ann"


def test_parse_accepts_a_byte_order_mark() -> None:
    rows = _parse("﻿email,name\na@example.com,Ann\n")

    assert rows[0]["email"] == "a@example.com"


def test_parse_trims_and_case_folds_headers() -> None:
    rows = _parse(" Email , NAME \na@example.com,Ann\n")

    assert rows[0]["name"] == "Ann"


def test_parse_skips_blank_rows_but_keeps_line_numbers() -> None:
    rows = _parse("email,name\na@example.com,Ann\n , \nb@example.com,Bob\n")

    assert [row["_line"] for row in rows] == ["2", "4"]


def test_parse_fills_missing_trailing_cells_with_blank() -> None:
    rows = _parse("email,name\na@example.com\n")

    assert rows[0]["name"] == ""


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"PK\x03\x04 binary", "Excel"),
        (b"email\n\xff\xfe\n", "CSV UTF-8 and upload it again"),
        ("email,age\na@example.com,3\n", "Unknown column(s): age"),
        ("email,email\na@example.com,b\n", "Repeated column(s): email"),
        ("name\nAnn\n", "Missing required column(s): email"),
        ('email\n"a@example.com\n', "line"),
        ("email,name\n", "no rows"),
        ("email,name\n \n", "no rows"),
    ],
)
def test_parse_rejects_a_bad_file_with_a_message(
    content: str | bytes, message: str
) -> None:
    with pytest.raises(CsvImportError, match=re.escape(message)):
        _parse(content)


def test_parse_names_accepted_headers_when_rejecting_a_header() -> None:
    with pytest.raises(CsvImportError, match="Accepted columns: email, name"):
        _parse("email,age\na@example.com,3\n")


def test_parse_rejects_a_file_over_the_size_limit() -> None:
    content = "email\n" + "a@example.com\n" * (MAX_UPLOAD_BYTES // 10)

    with pytest.raises(CsvImportError, match="larger than 1 MB"):
        _parse(content)


def test_parse_rejects_too_many_rows_and_never_truncates() -> None:
    content = "email\n" + "a@example.com\n" * 3

    with pytest.raises(CsvImportError, match="3 rows; the limit is 2"):
        _parse(content, max_rows=2)


def test_write_error_csv_starts_with_the_byte_order_mark() -> None:
    chunks = list(write_error_csv(("email", "reason"), [("a@example.com", "bad")]))

    assert chunks[0] == UTF8_BOM
    assert chunks[1] == "email,reason\r\n"


def test_write_error_csv_escapes_formulas_in_header_and_cells() -> None:
    chunks = list(write_error_csv(("=h",), [("=1+1",)]))

    assert chunks[1:] == ["'=h\r\n", "'=1+1\r\n"]
