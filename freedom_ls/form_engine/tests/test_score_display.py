import pytest

from freedom_ls.form_engine.score_display import format_score


@pytest.mark.parametrize(
    ("earned", "possible", "expected"),
    [
        (7, 10, "7 / 10"),
        (0, 10, "0 / 10"),
        (10, 10, "10 / 10"),
        (0, 0, "0 / 0"),
        (12, 10, "12 / 10"),
    ],
)
def test_format_score_renders_earned_over_possible(
    earned: int, possible: int, expected: str
) -> None:
    assert format_score(earned, possible) == expected


@pytest.mark.parametrize(
    ("earned", "possible", "message"),
    [
        (-1, 10, "earned must not be negative"),
        (1, -10, "possible must not be negative"),
    ],
)
def test_format_score_rejects_negative_values(
    earned: int, possible: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        format_score(earned, possible)
