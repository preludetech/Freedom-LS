"""What a submitted or stored answer means for a given question type.

One module owns both the server-side check run against a submission
(`answer_error`) and the reader-facing rendering of an already-stored value
(`format_answer`), so the parsing rules are written once and the two cannot
drift apart.

It imports `enums` and `django.utils` only — never `models`, which imports
it. `FormQuestion` is referenced only for type-checking, under
`from __future__ import annotations` plus a `TYPE_CHECKING` block, the way
`submissions.py` does it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
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


def parsed_number(text: str) -> int | None:
    """`text` as an integer, or None when it does not parse."""
    try:
        return int(text)
    except ValueError:
        return None


def _with_scheme(text: str) -> str:
    """`text` with a scheme, prepending `https://` when it has none.

    `URLValidator` alone rejects a bare `linkedin.com/in/me`; prepending a
    scheme first is what `forms.URLField` does before validating, so a
    schemeless address is judged the way a browser's URL field would.
    """
    if "://" in text:
        return text
    return f"https://{text}"


def _bounds_error[T: (date, time, int)](
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
        if number_value is None:
            return f'You entered "{text}". Enter a whole number.'
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
