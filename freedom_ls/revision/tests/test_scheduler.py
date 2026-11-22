from datetime import UTC, datetime, timedelta

import pytest
from fsrs import Rating

from freedom_ls.revision import scheduler

NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("was_correct", "guessed", "expected"),
    [
        (False, False, Rating.Again),
        (True, False, Rating.Good),
        (True, True, Rating.Hard),
    ],
)
def test_rating_for_maps_the_answer_to_a_rating(was_correct, guessed, expected):
    assert scheduler.rating_for(was_correct, guessed) == expected


def test_new_card_rated_good_is_due_later_than_the_same_card_rated_hard():
    card = scheduler.new_card(NOW)

    good, _ = scheduler.review(card, Rating.Good, NOW)
    hard, _ = scheduler.review(card, Rating.Hard, NOW)

    assert good["due"] > hard["due"]


def test_columns_round_trip_through_a_card_with_utc_datetimes():
    card, _ = scheduler.review(scheduler.new_card(NOW), Rating.Good, NOW)
    columns = scheduler.columns_from_card(card)

    again = scheduler.card_from_columns(**columns)

    assert again == card
    assert columns["due"].tzinfo is not None
    assert columns["due"].utcoffset() == timedelta(0)


def test_retrievability_is_lower_at_a_later_time():
    card, _ = scheduler.review(scheduler.new_card(NOW), Rating.Good, NOW)

    soon = scheduler.retrievability(card, NOW + timedelta(days=1))
    later = scheduler.retrievability(card, NOW + timedelta(days=30))

    assert later < soon
