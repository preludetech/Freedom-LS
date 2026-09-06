"""The `duration` filter, which names how long a wait lasts.

Its one call site is the lockout page's "paused for about ..." sentence, so a
value that renders as "0 minutes" reads as though the pause is already over.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.template import Context, Template

from freedom_ls.base.templatetags.fls_base_filters import duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (timedelta(hours=1), "1\xa0hour"),
        (timedelta(hours=2), "2\xa0hours"),
        (timedelta(minutes=5), "5\xa0minutes"),
        (timedelta(seconds=59), "59\xa0seconds"),
        (timedelta(seconds=30), "30\xa0seconds"),
        (timedelta(seconds=1), "1\xa0second"),
        (timedelta(seconds=0), "0\xa0seconds"),
    ],
)
def test_duration_names_the_length_of_the_wait(value: timedelta, expected: str) -> None:
    assert duration(value) == expected


def test_a_non_timedelta_renders_empty_rather_than_raising() -> None:
    """`now + value` would raise TypeError from inside template rendering,
    turning a page that only needed to say nothing into a 500.
    """
    rendered = Template("{% load fls_base_filters %}{{ value|duration }}").render(
        Context({"value": "not a timedelta"})
    )

    assert rendered == ""
