"""Tests for the shared deadline copy partials and the deadline label component."""

from __future__ import annotations

import re
from datetime import timedelta
from types import SimpleNamespace

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils import timezone


def _closing_child(tier: str = "MISSED", is_closed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        due_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=2),
        is_closed=is_closed,
        is_overdue=True,
        status="INCOMPLETE",
        deadline_tier=tier,
    )


def test_date_text_holds_only_the_tier_date() -> None:
    html = render_to_string(
        "learner_interface/partials/deadline_labels.html#date-text",
        {"child": _closing_child(), "show_time_zone_to_learners": False},
    )

    assert "Closes" not in html
    assert html.count("<time") == 1


def test_closes_label_is_its_own_deadline_label_in_the_due_tier_colour() -> None:
    for layout in ("inline", "stacked", "minimal"):
        html = render_to_string(
            "learner_interface/partials/deadline_labels.html#closes-label",
            {
                "child": _closing_child(tier="TODAY"),
                "layout": layout,
                "show_time_zone_to_learners": False,
            },
        )

        assert html.count('data-testid="deadline-label"') == 1
        assert f'data-layout="{layout}"' in html
        assert "Closes" in html
        assert "text-on-warning-light" in html


def test_closes_label_uses_the_lock_icon() -> None:
    closes = _render_component(
        '<c-deadline-label tier="MISSED" closes="true" layout="stacked">4 Jan</c-deadline-label>'
    )
    closed = _render_component(
        '<c-deadline-label tier="CLOSED" layout="stacked">4 Jan</c-deadline-label>'
    )
    missed = _render_component(
        '<c-deadline-label tier="MISSED" layout="stacked">4 Jan</c-deadline-label>'
    )

    assert _visible_text(closes) == "Closes 4 Jan"
    assert closes.replace("Closes", "Closed") == closed
    assert closes.replace("Closes", "Missed deadline") != missed


def test_closes_label_is_absent_once_the_item_has_closed() -> None:
    html = render_to_string(
        "learner_interface/partials/deadline_labels.html#closes-label",
        {
            "child": _closing_child(tier="CLOSED", is_closed=True),
            "layout": "stacked",
            "show_time_zone_to_learners": False,
        },
    )

    assert html.strip() == ""


_cotton_compiler = CottonCompiler()


def _render_component(markup: str) -> str:
    return Template(_cotton_compiler.process(markup)).render(Context({}))


def _render_label(layout: str, tier: str = "MISSED", detail: str = "Welcome") -> str:
    return _render_component(
        f'<c-deadline-label tier="{tier}" detail="{detail}" layout="{layout}">'
        "Jan 31, 2024</c-deadline-label>"
    )


def _visible_text(html: str) -> str:
    without_sr_only = re.sub(r'<span class="sr-only">.*?</span>', " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", without_sr_only).split())


def test_every_layout_colours_the_icon_and_the_bold_main_text_alike() -> None:
    for layout in ("inline", "stacked", "minimal"):
        html = _render_label(layout)

        assert f'data-layout="{layout}"' in html
        assert "text-error" in html
        assert "chip" not in html
        assert "border" not in html
        assert "bg-" not in html


def test_inline_and_stacked_show_the_main_text_detail_and_date_in_order() -> None:
    for layout in ("inline", "stacked"):
        assert (
            _visible_text(_render_label(layout))
            == "Missed deadline Welcome Jan 31, 2024"
        )


def test_stacked_aligns_the_icon_to_the_top_beside_the_main_text() -> None:
    html = _render_label("stacked")

    assert 'class="flex items-start' in html


def test_inline_and_stacked_show_the_date_in_muted_mono() -> None:
    for layout in ("inline", "stacked"):
        html = _render_label(layout)

        assert '<span class="font-mono text-muted">Jan 31, 2024</span>' in html


def test_minimal_keeps_the_date_in_the_tier_colour() -> None:
    html = _render_label("minimal")

    assert "font-mono" not in html
    assert "text-muted" not in html


def test_minimal_shows_the_date_and_keeps_the_words_for_screen_readers() -> None:
    html = _render_label("minimal", tier="CLOSED", detail="")

    assert _visible_text(html) == "Jan 31, 2024"
    assert '<span class="sr-only">Closed</span>' in html


def test_minimal_without_a_date_shows_the_main_text() -> None:
    html = _render_component('<c-deadline-label tier="CLOSED" layout="minimal" />')

    assert "sr-only" not in html
    assert _visible_text(html) == "Closed"


def test_today_word_reads_deadline_today() -> None:
    html = _render_component(
        '<c-deadline-label tier="TODAY" today_word="true">Today</c-deadline-label>'
    )

    assert _visible_text(html) == "Deadline today Today"


def test_access_ended_reads_access_ended_with_a_lock() -> None:
    html = _render_component(
        '<c-deadline-label tier="ACCESS_ENDED" layout="stacked">May 30</c-deadline-label>'
    )

    assert _visible_text(html) == "Access ended May 30"
