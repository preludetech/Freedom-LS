import pytest

from freedom_ls.health.durations import format_duration


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0h 00m"),
        (45, "0h 00m"),
        (59, "0h 00m"),
        (60, "0h 01m"),
        (3599, "0h 59m"),
        (3600, "1h 00m"),
        (3720, "1h 02m"),
        (7200, "2h 00m"),
        (360000, "100h 00m"),
    ],
)
def test_format_duration_floors_to_hours_and_padded_minutes(
    seconds: int, expected: str
) -> None:
    assert format_duration(seconds) == expected


def test_format_duration_rejects_negative_seconds() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        format_duration(-1)
