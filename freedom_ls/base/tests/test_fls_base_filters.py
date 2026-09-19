"""The `duration`, `get_dict_item` and `json_ld_script` filters.

`duration` names how long a wait lasts; its one call site is the lockout
page's "paused for about ..." sentence, so a value that renders as
"0 minutes" reads as though the pause is already over.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from django.template import Context, Template

from freedom_ls.base.templatetags.fls_base_filters import duration, get_dict_item


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


def test_get_dict_item_returns_the_value_for_a_known_key() -> None:
    assert get_dict_item({"a": 1}, "a") == 1


def test_get_dict_item_returns_none_for_a_missing_key() -> None:
    assert get_dict_item({"a": 1}, "b") is None


def test_get_dict_item_returns_none_for_a_non_dict_value() -> None:
    """A template variable never added to the context resolves to the empty
    string, not `None` — a downstream filter chained onto it must not raise.
    """
    assert get_dict_item("", "a") is None


# json_ld_script


def _render_json_ld_script(value: object, element_id: str) -> str:
    return Template(
        "{% load fls_base_filters %}{{ value|json_ld_script:element_id }}"
    ).render(Context({"value": value, "element_id": element_id}))


def test_json_ld_script_escapes_a_closing_script_tag_inside_a_value() -> None:
    """A value containing a literal "</script>" must not let a crawler (or a
    browser) treat it as the end of the JSON-LD block.
    """
    rendered = _render_json_ld_script(
        {"title": "</script><script>alert(1)</script>"}, "my-id"
    )

    assert rendered.count("</script>") == 1


def test_json_ld_script_escapes_a_double_quote_in_the_element_id() -> None:
    rendered = _render_json_ld_script({"a": 1}, 'my"id')

    assert 'id="my&quot;id"' in rendered


def test_json_ld_script_output_parses_back_to_the_input() -> None:
    value = {"a": 1, "b": ["x", "y"], "c": "<tag>&"}
    rendered = _render_json_ld_script(value, "my-id")

    match = re.search(
        r'<script id="my-id" type="application/ld\+json">(.*?)</script>',
        rendered,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == value
