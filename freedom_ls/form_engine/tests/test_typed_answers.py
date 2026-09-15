"""`typed_answers` owns both halves of "what does this answer mean": the
server-side check run against a submitted answer, and the reader-facing
rendering of an already-stored one. Both must reach the same conclusion about
what a string means for a given question type, so they are tested together.

Most cases here use a lightweight duck-typed stand-in rather than a real
`FormQuestion`, so these stay pure unit tests with no database round trip. A
handful of tests use the real model directly, to pin that its `min`/`max`
fields behave the same way the stand-in does.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from freedom_ls.form_engine.factories import FormQuestionFactory
from freedom_ls.form_engine.typed_answers import answer_error, format_answer


@dataclass
class _StubQuestion:
    """Duck-typed stand-in for `FormQuestion`, carrying only what `answer_error` reads."""

    type: str
    min: str = ""
    max: str = ""
    decimal_places: int = 0


# date


def test_valid_date_is_accepted():
    question = _StubQuestion(type="date")

    assert answer_error(question, "2025-06-15") is None


def test_unparseable_date_is_rejected_naming_format_and_value():
    question = _StubQuestion(type="date")

    message = answer_error(question, "banana")

    assert message is not None
    assert "banana" in message
    assert "YYYY-MM-DD" in message


def test_impossible_date_is_rejected():
    """`2025-02-30` is well-formed but not a real date; `dateparse.parse_date`
    raises `ValueError` for it rather than returning None, so this exercises
    the exception path rather than the plain-`None` path `banana` takes."""
    question = _StubQuestion(type="date")

    message = answer_error(question, "2025-02-30")

    assert message is not None
    assert "2025-02-30" in message


def test_date_before_min_is_rejected():
    question = _StubQuestion(type="date", min="2025-01-01")

    message = answer_error(question, "2024-12-31")

    assert message is not None
    assert "2024-12-31" in message


def test_date_equal_to_min_is_accepted():
    question = _StubQuestion(type="date", min="2025-01-01")

    assert answer_error(question, "2025-01-01") is None


def test_date_after_max_is_rejected():
    question = _StubQuestion(type="date", max="2025-12-31")

    message = answer_error(question, "2026-01-01")

    assert message is not None
    assert "2026-01-01" in message


def test_date_equal_to_max_is_accepted():
    question = _StubQuestion(type="date", max="2025-12-31")

    assert answer_error(question, "2025-12-31") is None


def test_date_bound_the_module_cannot_parse_is_ignored():
    """A `min`/`max` that itself does not parse is ignored, matching what a
    browser does with an unparseable `min`/`max` HTML attribute."""
    question = _StubQuestion(type="date", min="not-a-date")

    assert answer_error(question, "2025-06-15") is None


# time


def test_valid_time_is_accepted():
    question = _StubQuestion(type="time")

    assert answer_error(question, "09:30") is None


def test_unparseable_time_is_rejected_naming_format_and_value():
    question = _StubQuestion(type="time")

    message = answer_error(question, "banana")

    assert message is not None
    assert "banana" in message
    assert "HH:MM" in message


def test_time_before_min_is_rejected():
    question = _StubQuestion(type="time", min="09:00")

    message = answer_error(question, "08:59")

    assert message is not None
    assert "08:59" in message


def test_time_equal_to_min_is_accepted():
    question = _StubQuestion(type="time", min="09:00")

    assert answer_error(question, "09:00") is None


def test_time_after_max_is_rejected():
    question = _StubQuestion(type="time", max="17:00")

    message = answer_error(question, "17:01")

    assert message is not None
    assert "17:01" in message


def test_time_equal_to_max_is_accepted():
    question = _StubQuestion(type="time", max="17:00")

    assert answer_error(question, "17:00") is None


# number


def test_valid_number_is_accepted():
    question = _StubQuestion(type="number")

    assert answer_error(question, "42") is None


def test_non_numeric_text_is_rejected_naming_value():
    question = _StubQuestion(type="number")

    message = answer_error(question, "banana")

    assert message is not None
    assert "banana" in message


def test_number_below_min_is_rejected():
    question = _StubQuestion(type="number", min="0")

    message = answer_error(question, "-1")

    assert message is not None
    assert "-1" in message


def test_number_equal_to_min_is_accepted():
    question = _StubQuestion(type="number", min="0")

    assert answer_error(question, "0") is None


def test_number_above_max_is_rejected():
    question = _StubQuestion(type="number", max="70")

    message = answer_error(question, "71")

    assert message is not None
    assert "71" in message


def test_number_equal_to_max_is_accepted():
    question = _StubQuestion(type="number", max="70")

    assert answer_error(question, "70") is None


def test_exponent_notation_is_accepted():
    """`<input type="number">` submits it, so the server has to take it."""
    question = _StubQuestion(type="number")

    assert answer_error(question, "1e3") is None


@pytest.mark.parametrize(
    "text", ["1_0", "1,000", "nan", "Infinity", " 5 ", "+5", ".5", "5."]
)
def test_text_no_number_input_would_submit_is_rejected(text):
    """`int()` takes `1_0` and surrounding whitespace, and `Decimal()` takes
    those plus `nan` and `Infinity`. None of them is a valid floating-point
    number, so no browser would submit one and the server must not take one."""
    question = _StubQuestion(type="number")

    assert answer_error(question, text) is not None


# number: decimal places


def test_a_decimal_is_rejected_when_the_question_allows_none():
    """The default is whole numbers, which is what `<input type="number">`
    itself enforces with its default `step` of 1."""
    question = _StubQuestion(type="number")

    message = answer_error(question, "7.5")

    assert message is not None
    assert "7.5" in message
    assert "whole number" in message


def test_a_decimal_is_accepted_when_the_question_allows_decimal_places():
    question = _StubQuestion(type="number", decimal_places=2)

    assert answer_error(question, "7.5") is None


def test_too_many_decimal_places_is_rejected_naming_the_limit():
    question = _StubQuestion(type="number", decimal_places=2)

    message = answer_error(question, "7.555")

    assert message is not None
    assert "7.555" in message
    assert "2 decimal places" in message


def test_a_single_allowed_decimal_place_is_named_in_the_singular():
    question = _StubQuestion(type="number", decimal_places=1)

    message = answer_error(question, "7.55")

    assert message is not None
    assert "1 decimal place." in message


def test_a_trailing_zero_does_not_count_as_a_decimal_place():
    """`7.50` is the same number as `7.5`. Counting the written zero would
    reject a value the author's own limit allows."""
    question = _StubQuestion(type="number", decimal_places=1)

    assert answer_error(question, "7.50") is None


def test_a_decimal_bound_is_compared_numerically():
    question = _StubQuestion(type="number", max="7.5", decimal_places=2)

    assert answer_error(question, "7.6") is not None
    assert answer_error(question, "7.5") is None


# email


def test_valid_email_is_accepted():
    question = _StubQuestion(type="email")

    assert answer_error(question, "person@example.com") is None


def test_invalid_email_is_rejected_naming_value():
    question = _StubQuestion(type="email")

    message = answer_error(question, "not-an-email")

    assert message is not None
    assert "not-an-email" in message


def test_single_label_localhost_domain_is_accepted():
    """`EmailValidator` special-cases `localhost` as the one single-label
    domain it accepts, which is worth pinning because it bites in dev before
    it bites in production."""
    question = _StubQuestion(type="email")

    assert answer_error(question, "person@localhost") is None


# url


def test_url_with_scheme_is_accepted():
    question = _StubQuestion(type="url")

    assert answer_error(question, "https://example.com/profile") is None


def test_schemeless_url_is_accepted():
    """`URLValidator` alone rejects a bare `linkedin.com/in/me`; the module
    prepends a scheme first, the way `forms.URLField` does."""
    question = _StubQuestion(type="url")

    assert answer_error(question, "linkedin.com/in/me") is None


def test_invalid_url_is_rejected_naming_value():
    question = _StubQuestion(type="url")

    message = answer_error(question, "not a url")

    assert message is not None
    assert "not a url" in message


# phone


def test_any_phone_text_is_accepted():
    question = _StubQuestion(type="phone")

    assert answer_error(question, "+1 555 0100") is None


def test_phone_text_with_letters_is_still_accepted():
    """Real phone validation needs `libphonenumber` and a country; this
    type checks only that something is present, which is enforced elsewhere."""
    question = _StubQuestion(type="phone")

    assert answer_error(question, "call me maybe") is None


# min/max on a real FormQuestion


@pytest.mark.django_db
def test_date_equal_to_min_is_accepted_on_a_real_form_question(mock_site_context):
    question = FormQuestionFactory(type="date", min="2025-01-01")

    assert answer_error(question, "2025-01-01") is None


@pytest.mark.django_db
def test_date_before_min_is_rejected_on_a_real_form_question(mock_site_context):
    question = FormQuestionFactory(type="date", min="2025-01-01")

    message = answer_error(question, "2024-12-31")

    assert message is not None


@pytest.mark.django_db
def test_number_equal_to_max_is_accepted_on_a_real_form_question(mock_site_context):
    question = FormQuestionFactory(type="number", max="70")

    assert answer_error(question, "70") is None


@pytest.mark.django_db
def test_number_above_max_is_rejected_on_a_real_form_question(mock_site_context):
    question = FormQuestionFactory(type="number", max="70")

    message = answer_error(question, "71")

    assert message is not None


# format_answer


def test_format_answer_renders_a_stored_date():
    assert format_answer("date", "2025-06-15") == "June 15, 2025"


def test_format_answer_renders_a_stored_time():
    assert format_answer("time", "14:30") == "2:30 p.m."


def test_format_answer_falls_back_to_the_raw_string_when_unparseable():
    """A row written before this type existed, or under a question whose
    `type` was changed afterwards, still has to render as something."""
    assert format_answer("date", "not-a-real-date") == "not-a-real-date"


def test_format_answer_returns_untouched_text_for_a_plain_type():
    assert format_answer("short_text", "hello there") == "hello there"
