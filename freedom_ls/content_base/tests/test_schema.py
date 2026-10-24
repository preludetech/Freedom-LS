# Guards the content-type schema registry against silent gaps.
#
# If nothing ever imports a consumer app's `schema.py` module before this runs,
# that app's content types register no schema — no error, no warning, just
# content validation quietly treating `.yaml` files declaring them as
# unrecognised. This test iterates the enum, so it adds no dependency on either
# consumer app.

from datetime import UTC, date, datetime, time

import pytest
from pydantic import ValidationError

from freedom_ls.content_base.schema import (
    DUE_DATE_FIELD_NAMES,
    SCHEMAS,
    ContentType,
    DueDateFields,
)


def test_every_content_type_has_a_registered_schema() -> None:
    assert set(ContentType) == set(SCHEMAS)


class _DueFile(DueDateFields):
    """DueDateFields plus the file_path its error messages name."""

    file_path: str = "topics/intro.md"


def test_due_date_field_names_are_the_three_authored_fields() -> None:
    assert {
        "due_date",
        "due_time",
        "due_days_after_registration",
    } == DUE_DATE_FIELD_NAMES


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, (None, None, None)),
        ({"due_date": date(2026, 3, 14)}, (date(2026, 3, 14), None, None)),
        (
            {"due_date": date(2026, 3, 14), "due_time": "17:00"},
            (date(2026, 3, 14), time(17, 0), None),
        ),
        ({"due_days_after_registration": 0}, (None, None, 0)),
        (
            {"due_days_after_registration": 14, "due_time": "09:30"},
            (None, time(9, 30), 14),
        ),
    ],
)
def test_valid_due_date_shapes_are_accepted(
    fields: dict[str, object], expected: tuple[date | None, time | None, int | None]
) -> None:
    parsed = _DueFile.model_validate(fields)

    assert (
        parsed.due_date,
        parsed.due_time,
        parsed.due_days_after_registration,
    ) == expected


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"due_date": datetime(2026, 3, 14, 0, 0, tzinfo=UTC)}, "without a time"),
        ({"due_date": "2026-03-14"}, "without a time"),
        ({"due_time": 1020, "due_days_after_registration": 1}, "quoted 24-hour time"),
        ({"due_time": "5pm", "due_days_after_registration": 1}, "quoted 24-hour time"),
        ({"due_time": "25:99", "due_days_after_registration": 1}, "time"),
        ({"due_days_after_registration": -1}, "greater than or equal to 0"),
        ({"due_days_after_registration": "14"}, "valid integer"),
        (
            {"due_date": date(2026, 3, 14), "due_days_after_registration": 3},
            "topics/intro.md: set due_date or due_days_after_registration, not both",
        ),
        (
            {"due_time": "17:00"},
            "topics/intro.md: due_time needs due_date or due_days_after_registration",
        ),
    ],
)
def test_invalid_due_date_shapes_are_refused(
    fields: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _DueFile.model_validate(fields)
