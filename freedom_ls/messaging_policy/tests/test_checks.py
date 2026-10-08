"""System checks for the messaging policy app."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.messaging_policy.checks import check_default_flags

VALID_FLAGS = {
    "learner_to_educator": "closed",
    "learner_to_cohort_peer": "open",
    "learner_to_course_peer": "closed",
}


@pytest.mark.parametrize(
    "flags",
    [
        {"learner_to_educator": "closed", "learner_to_cohort_peer": "closed"},
        {**VALID_FLAGS, "learner_to_everyone": "open"},
        {**VALID_FLAGS, "learner_to_educator": "inherit"},
        {**VALID_FLAGS, "learner_to_educator": "sometimes"},
    ],
    ids=["missing_key", "unknown_key", "inherit_value", "bad_value"],
)
def test_malformed_default_flags_produce_an_error(flags: dict[str, str]) -> None:
    with override_settings(MESSAGING_DEFAULT_FLAGS=flags):
        errors = check_default_flags(None)

    assert [error.id for error in errors] == ["freedom_ls_messaging_policy.E001"]


def test_valid_default_flags_produce_no_error() -> None:
    with override_settings(MESSAGING_DEFAULT_FLAGS=VALID_FLAGS):
        errors = check_default_flags(None)

    assert errors == []


def test_the_shipped_default_flags_produce_no_error() -> None:
    assert check_default_flags(None) == []
