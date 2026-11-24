"""Spaced-repetition scheduling over FSRS, on plain data.

Nothing here touches the ORM: a card travels as a `CardDict`, and the
caller maps it to and from whatever it stores.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from fsrs import Card, Rating, Scheduler, State

from .config import config

# fsrs.Card requires an id, but the row that stores a card already identifies
# it, so every card the wrapper builds carries this one.
_CARD_ID = 0


class CardDict(TypedDict):
    """An `fsrs.Card` as plain JSON: what `schedule_before` stores."""

    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: str
    last_review: str | None


class CardColumns(TypedDict):
    """The same card as the values RevisionSchedule's columns hold."""

    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime
    last_review: datetime | None


def _scheduler() -> Scheduler:
    # No fuzzing: "I guessed" replays a review, and a replay has to land on the
    # same due date the first rating gave, so a second tap restores it exactly.
    return Scheduler(
        desired_retention=config.REVISION_DESIRED_RETENTION, enable_fuzzing=False
    )


def _to_card(card: CardDict) -> Card:
    return Card.from_dict({"card_id": _CARD_ID, **card})


def _to_dict(card: Card) -> CardDict:
    return CardDict(
        state=card.state.value,
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due.isoformat(),
        last_review=card.last_review.isoformat() if card.last_review else None,
    )


def new_card(now: datetime) -> CardDict:
    return _to_dict(Card(card_id=_CARD_ID, due=now))


def card_from_columns(
    *,
    state: int,
    step: int | None,
    stability: float | None,
    difficulty: float | None,
    due: datetime,
    last_review: datetime | None,
) -> CardDict:
    return CardDict(
        state=state,
        step=step,
        stability=stability,
        difficulty=difficulty,
        due=due.astimezone(UTC).isoformat(),
        last_review=last_review.astimezone(UTC).isoformat() if last_review else None,
    )


def columns_from_card(card: CardDict) -> CardColumns:
    return CardColumns(
        state=card["state"],
        step=card["step"],
        stability=card["stability"],
        difficulty=card["difficulty"],
        due=datetime.fromisoformat(card["due"]),
        last_review=(
            datetime.fromisoformat(card["last_review"]) if card["last_review"] else None
        ),
    )


def is_review_state(card: CardDict) -> bool:
    """Whether FSRS holds the card as learned, so a wrong answer is a lapse."""
    return card["state"] == State.Review.value


def rating_for(was_correct: bool, guessed: bool) -> Rating:
    """A wrong answer is Again, a right one Good, a guessed right one Hard.

    Easy is never used: nothing the learner does tells the system an answer
    was effortless.
    """
    if not was_correct:
        return Rating.Again
    return Rating.Hard if guessed else Rating.Good


def review(card: CardDict, rating: Rating, now: datetime) -> tuple[CardDict, Rating]:
    reviewed, _log = _scheduler().review_card(_to_card(card), rating, now)
    return _to_dict(reviewed), rating


def retrievability(card: CardDict, now: datetime) -> float:
    return _scheduler().get_card_retrievability(_to_card(card), now)
