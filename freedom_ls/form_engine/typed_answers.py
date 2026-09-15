"""What a submitted or stored answer means for a given question type.

One module owns the server-side check run against a submission
(`answer_error`), the reader-facing rendering of an already-stored value
(`format_answer`), and the check on the question's own `min`/`max` and
`decimal_places` (`question_bounds_error`), so the parsing rules are written
once and the three cannot drift apart.

It imports `enums` and `django.utils` only — never `models`, which imports
it. `FormQuestion` is referenced only for type-checking, under
`from __future__ import annotations` plus a `TYPE_CHECKING` block, the way
`submissions.py` does it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.utils import formats
from django.utils.dateparse import parse_date, parse_time

from .enums import QuestionType

if TYPE_CHECKING:
    from .models import FormQuestion


@dataclass(frozen=True)
class RejectedAnswer:
    """A submitted answer that failed its question type's check."""

    text: str  # what the person typed, so the page can hand it back
    message: str  # what to tell them, naming the format and the value


def parsed_date(text: str) -> date | None:
    """`text` as a date, or None when it does not parse.

    `dateparse.parse_date` returns None for a malformed string like "banana"
    but raises `ValueError` for a well-formed, impossible one like
    "2025-02-30". Catching it here means both failures reach the same `None`
    branch in every caller.
    """
    try:
        return parse_date(text)
    except ValueError:
        return None


def parsed_time(text: str) -> time | None:
    """`text` as a time, or None when it does not parse. See `parsed_date`."""
    try:
        return parse_time(text)
    except ValueError:
        return None


# HTML's "valid floating-point number" grammar, so the server accepts exactly
# what `<input type="number">` submits and no more. `int()` takes `1_0` and
# surrounding whitespace; `Decimal()` takes those plus `nan` and `Infinity`.
# None of them can be typed into a number input, so none may reach a stored
# answer either.
_NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")


def parsed_number(text: str) -> Decimal | None:
    """`text` as a number, or None when it does not parse."""
    if not _NUMBER.fullmatch(text):
        return None
    return Decimal(text)


def decimal_places_used(value: Decimal) -> int:
    """How many decimal places `value` is written to.

    Normalised first, so `7.50` counts as one place rather than two -- it is
    the same number as `7.5`, and counting the written zero would reject a
    value the question's own limit allows.
    """
    exponent = value.normalize().as_tuple().exponent
    # A non-integer exponent is NaN or Infinity, which `parsed_number` refuses.
    if not isinstance(exponent, int):
        return 0
    return max(0, -exponent)


def _with_scheme(text: str) -> str:
    """`text` with a scheme, prepending `https://` when it has none.

    `URLValidator` alone rejects a bare `linkedin.com/in/me`; prepending a
    scheme first is what `forms.URLField` does before validating, so a
    schemeless address is judged the way a browser's URL field would.
    """
    if "://" in text:
        return text
    return f"https://{text}"


def _number_shape(decimal_places: int) -> str:
    """What a number question with this many decimal places will accept."""
    if decimal_places == 0:
        return "Enter a whole number."
    places = "place" if decimal_places == 1 else "places"
    return f"Enter a number with at most {decimal_places} decimal {places}."


def _bounds_error[T: (date, time, Decimal)](
    question: FormQuestion,
    text: str,
    value: T,
    parse: Callable[[str], T | None],
    label: str,
) -> str | None:
    """Whether `value` falls outside `question.min`/`question.max`, inclusive.

    Bounds are compared against the parsed value, never the raw string. A
    bound this module cannot parse is ignored rather than failing closed,
    matching what a browser does with an unparseable `min`/`max` attribute.
    """
    min_text: str = question.min
    max_text: str = question.max
    min_value = parse(min_text) if min_text else None
    if min_value is not None and value < min_value:
        return f'You entered "{text}". Enter a {label} on or after {min_text}.'
    max_value = parse(max_text) if max_text else None
    if max_value is not None and value > max_value:
        return f'You entered "{text}". Enter a {label} on or before {max_text}.'
    return None


def answer_error(question: FormQuestion, text: str) -> str | None:
    """Why `text` is not a valid answer to `question`, or None when it is."""
    if question.type == QuestionType.DATE:
        date_value = parsed_date(text)
        if date_value is None:
            return f'You entered "{text}". Enter a date in the format YYYY-MM-DD.'
        return _bounds_error(question, text, date_value, parsed_date, "date")

    if question.type == QuestionType.TIME:
        time_value = parsed_time(text)
        if time_value is None:
            return f'You entered "{text}". Enter a time in the format HH:MM.'
        return _bounds_error(question, text, time_value, parsed_time, "time")

    if question.type == QuestionType.NUMBER:
        number_value = parsed_number(text)
        if (
            number_value is None
            or decimal_places_used(number_value) > question.decimal_places
        ):
            return f'You entered "{text}". {_number_shape(question.decimal_places)}'
        return _bounds_error(question, text, number_value, parsed_number, "number")

    if question.type == QuestionType.EMAIL:
        try:
            EmailValidator()(text)
        except ValidationError:
            return f'You entered "{text}". Enter a valid email address.'
        return None

    if question.type == QuestionType.URL:
        try:
            URLValidator()(_with_scheme(text))
        except ValidationError:
            return f'You entered "{text}". Enter a valid web address.'
        return None

    # phone, short_text, long_text: nothing to check. Real phone validation
    # needs libphonenumber and a country, which is a different piece of work.
    return None


# A time bound has to be written HH:MM, with seconds optional. Anything else
# that `parse_time` happens to accept — a bare "1020" from an unquoted YAML
# time — means a different time than the author wrote.
_TIME_BOUND = re.compile(r"\d{1,2}:\d{2}(:\d{2})?")


def question_bounds_error(
    question_type: str, min_text: str, max_text: str, decimal_places: int
) -> str | None:
    """Why this question's `min`, `max` and `decimal_places` do not go together.

    Shared by the pydantic schema, which judges an authored content file, and
    `FormQuestion.clean()`, which judges the admin. A bound set by hand is then
    held to the same rule as one written in YAML, and neither route can leave
    an unparseable bound sitting inert in the page's HTML.
    """
    if decimal_places and question_type != QuestionType.NUMBER:
        return f"decimal_places is only valid on number questions, not {question_type}"

    if not min_text and not max_text:
        return None

    parsers: dict[str, Callable[[str], date | time | Decimal | None]] = {
        QuestionType.DATE: parsed_date,
        QuestionType.TIME: parsed_time,
        QuestionType.NUMBER: parsed_number,
    }
    parse = parsers.get(question_type)
    if parse is None:
        return (
            f"min/max are only valid on date, time or number questions, "
            f"not {question_type}"
        )

    for name, bound in (("min", min_text), ("max", max_text)):
        if not bound:
            continue
        value = parse(bound)
        if value is None:
            return f'{name} "{bound}" is not a valid {question_type}'
        if question_type == QuestionType.TIME and not _TIME_BOUND.fullmatch(bound):
            return (
                f'{name} "{bound}" is not written as HH:MM — quote it in the '
                f"YAML, or it is read as a number"
            )
        if isinstance(value, Decimal) and decimal_places_used(value) > decimal_places:
            return f'{name} "{bound}" has more decimal places than this question allows'
    return None


def format_answer(question_type: str, text: str) -> str:
    """A stored answer rendered for a reader.

    Returns the raw string unchanged when it will not parse — a row written
    before this type existed, or under a question whose `type` was changed
    afterwards, still has to render as something.
    """
    if question_type == QuestionType.DATE:
        date_value = parsed_date(text)
        return formats.date_format(date_value) if date_value is not None else text

    if question_type == QuestionType.TIME:
        time_value = parsed_time(text)
        return formats.time_format(time_value) if time_value is not None else text

    return text
