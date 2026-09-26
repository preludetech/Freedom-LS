"""InstanceDetailsPanel rows: labels, values and the edit action."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import InstanceDetailsPanel

from .conftest import StubChild, StubModel, _make_stub, _make_stub_child


class StubInstanceDetails(InstanceDetailsPanel):
    model = StubModel
    fields = ["name", "kind", "is_active", "sat_score"]


class StubChildDetails(InstanceDetailsPanel):
    model = StubChild
    fields = ["parent__name"]


def _bind(
    panel_class: type[InstanceDetailsPanel], instance: Model
) -> InstanceDetailsPanel:
    return panel_class(
        PanelContext(
            request=RequestFactory().get("/"),
            instance=instance,
            base_url="/x",
            name="details",
        )
    )


@pytest.mark.django_db
def test_rows_carry_label_value_and_is_boolean(mock_site_context: Site) -> None:
    stub = _make_stub(name="Detailed", kind="b", is_active=True)

    rows = _bind(StubInstanceDetails, stub).get_rows()

    assert rows == [
        {"label": "name", "value": "Detailed", "is_boolean": False},
        {"label": "kind", "value": "Beta", "is_boolean": False},
        {"label": "is active", "value": True, "is_boolean": True},
        {"label": "SAT score", "value": "-", "is_boolean": False},
    ]


@pytest.mark.django_db
def test_a_dunder_path_resolves_through_the_relation(mock_site_context: Site) -> None:
    child = _make_stub_child(_make_stub(name="Parent Stub"))

    (row,) = _bind(StubChildDetails, child).get_rows()

    assert row["value"] == "Parent Stub"


@pytest.mark.django_db
def test_the_template_capitalises_the_label_once(mock_site_context: Site) -> None:
    stub = _make_stub(name="Detailed")
    panel = _bind(StubInstanceDetails, stub)

    html = render_to_string(panel.template_name, panel.get_context_data())

    assert "Is active" in html
    assert "SAT score" in html
    assert "Sat Score" not in html


@pytest.mark.django_db
def test_no_edit_action_when_the_panel_is_not_editable(mock_site_context: Site) -> None:
    stub = _make_stub(name="Detailed")

    assert _bind(StubInstanceDetails, stub).get_actions() == []
