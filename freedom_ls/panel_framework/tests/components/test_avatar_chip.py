"""Tests for the <c-panel-avatar-chip /> cotton component."""

from __future__ import annotations

import re

from ..cotton_helpers import render_cotton


def test_initials_element_is_aria_hidden_and_holds_the_derived_initials() -> None:
    html = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)

    assert match is not None
    assert match.group(1) == "TM"


def test_name_is_visible_text_outside_the_initials_element() -> None:
    html = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    initials_end = html.index("</span>")

    assert "Thandi Mokoena" in html[initials_end:]


def test_initials_attribute_overrides_the_derived_initials() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" initials="ZZ" />'
    )

    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)

    assert match is not None
    assert match.group(1) == "ZZ"


def test_secondary_renders_when_given() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" secondary="Learner" />'
    )

    assert "Learner" in html


def test_name_hidden_renders_the_initials_and_no_name_text() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" name_hidden="true" />'
    )

    assert "Thandi Mokoena" not in html
    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)
    assert match is not None
    assert match.group(1) == "TM"


def test_name_is_escaped() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="<script>alert(1)</script>" user_id="42" />'
    )

    assert "<script>alert(1)</script>" not in html


def test_name_hidden_false_string_shows_the_name() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" name_hidden="False" />'
    )

    assert "Thandi Mokoena</span>" in html


def test_badges_sit_in_the_name_column_under_the_name() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" secondary="t@example.com">'
        '<c-slot name="badges"><span class="badge">You</span></c-slot>'
        "</c-panel-avatar-chip>"
    )

    match = re.search(r'<span class="([^"]*)"><span class="badge">You</span>', html)

    assert match is not None
    assert "col-start-2" in match.group(1).split()
    assert html.index("t@example.com") < html.index("You")


class _User:
    def __init__(self, first_name: str, last_name: str, email: str, pk: int) -> None:
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.pk = pk

    @property
    def display_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part) or (
            self.email
        )


def test_a_named_user_shows_the_name_and_the_email_beneath() -> None:
    user = _User("Thandi", "Mokoena", "thandi@example.com", 42)

    html = render_cotton('<c-panel-avatar-chip :user="user" />', user=user)

    assert "Thandi Mokoena" in html
    assert "thandi@example.com" in html


def test_an_unnamed_user_shows_the_email_once() -> None:
    user = _User("", "", "thandi@example.com", 42)

    html = render_cotton('<c-panel-avatar-chip :user="user" />', user=user)

    assert html.count("thandi@example.com") == 1


def test_a_user_picks_the_avatar_colour_from_their_pk() -> None:
    user = _User("Thandi", "Mokoena", "thandi@example.com", 42)

    by_user = render_cotton('<c-panel-avatar-chip :user="user" />', user=user)
    by_id = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    colour = re.search(r"class=\"panel-avatar-\d", by_id)
    assert colour is not None
    assert colour.group(0) in by_user


def test_with_no_user_and_no_id_the_fallback_icon_replaces_the_initials() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="System" fallback_icon="settings" />'
    )

    assert 'data-icon="settings"' in html
    assert "System" in html
    assert not re.search(r'class="panel-avatar-\d', html)


def test_a_hidden_name_labels_the_fallback_icon() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Deleted user" fallback_icon="user" name_hidden="true" />'
    )

    assert 'aria-label="Deleted user"' in html


def test_an_id_keeps_the_initials_even_with_a_fallback_icon() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" fallback_icon="user" />'
    )

    assert re.search(r'class="panel-avatar-\d', html)
    assert 'data-icon="user"' not in html
