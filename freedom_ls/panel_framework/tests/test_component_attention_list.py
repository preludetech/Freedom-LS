"""Tests for the <c-panel-attention-list /> and <c-panel-attention-row /> cotton components."""

from __future__ import annotations

import re

from .cotton_helpers import render_cotton


def test_list_root_is_a_ul_holding_li_rows() -> None:
    html = render_cotton(
        '<c-panel-attention-list><c-panel-attention-row subject="Thandi Mokoena" '
        'href="/learners/42/" /></c-panel-attention-list>'
    )

    assert html.strip().startswith("<ul")
    assert "<li" in html


def test_action_accessible_text_contains_the_subject() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Thandi Mokoena" href="/learners/42/" '
        'action_label="Message" action_href="/learners/42/message/" />'
    )

    assert "Message" in html
    assert "Thandi Mokoena" in html[html.index("Message") :]


def test_user_id_renders_the_avatar_initials_element() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Thandi Mokoena" href="/learners/42/" user_id="42" />'
    )

    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)

    assert match is not None
    assert match.group(1) == "TM"


def test_icon_alone_renders_the_severity_icon() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Cohort Alpha" href="/cohorts/1/" icon="warning" />'
    )

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="warning"', html
    )


def test_row_holds_exactly_one_link_to_href() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Thandi Mokoena" href="/learners/42/" '
        'action_label="Message" action_href="/learners/42/message/" />'
    )

    assert html.count('href="/learners/42/"') == 1


def test_no_action_link_without_action_href() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Thandi Mokoena" href="/learners/42/" '
        'action_label="Message" />'
    )

    assert "Message" not in html


def test_subject_is_escaped() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="<script>alert(1)</script>" href="/learners/42/" />'
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_a_stringified_none_user_id_falls_back_to_the_severity_icon() -> None:
    html = render_cotton(
        '<c-panel-attention-row subject="Cohort Alpha" href="/cohorts/1/" '
        'user_id="None" icon="warning" />'
    )

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="warning"', html
    )
    assert ">CA</span>" not in html
