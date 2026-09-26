"""build_hx_trigger: the one function every panel action builds its
HX-Trigger header through."""

from __future__ import annotations

import json

from freedom_ls.panel_framework.events import build_hx_trigger


def test_one_event_carries_its_ids() -> None:
    header = build_hx_trigger({"itemChanged": ["1"]})

    assert json.loads(header) == {"itemChanged": {"ids": ["1"]}}


def test_two_events_both_appear() -> None:
    header = build_hx_trigger({"itemChanged": ["1"], "otherChanged": ["2"]})

    assert json.loads(header) == {
        "itemChanged": {"ids": ["1"]},
        "otherChanged": {"ids": ["2"]},
    }


def test_close_modal_is_an_empty_object() -> None:
    header = build_hx_trigger({}, close_modal=True)

    assert json.loads(header) == {"closeModal": {}}


def test_title_is_carried_under_instance_title_changed() -> None:
    header = build_hx_trigger({}, title="New Name")

    assert json.loads(header) == {"instanceTitleChanged": {"title": "New Name"}}


def test_no_close_modal_and_no_title_by_default() -> None:
    header = build_hx_trigger({"itemChanged": ["1"]})

    payload = json.loads(header)
    assert "closeModal" not in payload
    assert "instanceTitleChanged" not in payload


def test_ids_are_always_a_list_of_strings() -> None:
    header = build_hx_trigger({"itemChanged": []})

    assert json.loads(header) == {"itemChanged": {"ids": []}}
