"""The template contract: no |safe, and both routes a downstream extends by."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import pytest_django.fixtures

from django.contrib.sites.models import Site
from django.db.models import Model
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, TabSet

from .conftest import _make_stub
from .stub_panels import StubDetailsPanel, StubHiddenPanel

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OVERRIDES_DIR = Path(__file__).resolve().parent / "template_overrides"


class _PlainPanel(Panel):
    title = "Plain"


class _TabsWithAHiddenOne(TabSet):
    title = "Sections"
    children = {"shown": _PlainPanel, "hidden": StubHiddenPanel}


def _bind(
    panel_class: type[Panel], instance: Model | None = None, name: str = "x"
) -> Panel:
    return panel_class(
        PanelContext(
            request=RequestFactory().get("/p"),
            instance=instance,
            base_url="/p",
            name=name,
        )
    )


def _render(panel: Panel) -> str:
    return render_to_string(
        panel.template_name, panel.get_context_data(), request=panel.request
    )


@pytest.fixture
def leaf_override(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Put a downstream-style override of panels/panel.html ahead of the app's."""
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(OVERRIDES_DIR), *templates[0]["DIRS"]]
    settings.TEMPLATES = templates


def test_no_panel_framework_template_uses_safe() -> None:
    offenders = [
        str(path.relative_to(TEMPLATES_DIR))
        for path in TEMPLATES_DIR.rglob("*.html")
        if "|safe" in path.read_text()
    ]

    assert offenders == []


@pytest.mark.usefixtures("leaf_override")
@pytest.mark.django_db
def test_an_override_of_the_leaf_keeps_the_base_markup(mock_site_context: Site) -> None:
    html = _render(_bind(_PlainPanel))

    assert "<p data-override-marker>overridden</p>" in html
    assert "<h2>Plain</h2>" in html
    assert 'data-panel="x"' in html


@pytest.mark.django_db
def test_a_panel_template_extending_the_framework_template_renders_both(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(StubDetailsPanel, _make_stub(name="Extended")))

    assert "<p data-stub-details>Extended</p>" in html
    assert "<h2>Details</h2>" in html
    assert '<section class="surface"' in html


@pytest.mark.django_db
def test_a_leaf_refetches_its_own_region_on_panel_changed(
    mock_site_context: Site,
) -> None:
    panel = _bind(_PlainPanel)

    html = _render(panel)

    assert 'hx-trigger="panelChanged from:body"' in html
    assert f'hx-target="#{panel.region_id}"' in html
    assert f'id="{panel.region_id}"' in html


@pytest.mark.django_db
def test_a_hidden_tab_gets_no_link_in_the_nav(mock_site_context: Site) -> None:
    html = _render(_bind(_TabsWithAHiddenOne, name=""))

    assert "__tabs/shown" in html
    assert "Hidden" not in html
    assert "__tabs/hidden" not in html


@pytest.mark.django_db
def test_tab_set_markup_is_navigation_not_an_aria_tab_widget(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(_TabsWithAHiddenOne, name=""))

    assert '<nav aria-label="Sections"' in html
    assert 'aria-current="page"' in html
    assert 'role="tab' not in html
