"""The template contract: no |safe, and both routes a downstream extends by."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import lxml.html
import pytest
import pytest_django.fixtures

from django.contrib.sites.models import Site
from django.db.models import Model
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, TabSet
from freedom_ls.panel_framework.views import SectionConfigBase

from .conftest import _make_stub
from .stub_panels import StubDetailsPanel, StubHiddenPanel

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OVERRIDES_DIR = Path(__file__).resolve().parent / "template_overrides"
COMPONENTS_DIR = TEMPLATES_DIR / "cotton"
TAILWIND_COMPONENTS_CSS = FREEDOM_LS_PACKAGE_DIR.parent / "tailwind.components.css"

RAW_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RAW_TAILWIND_PALETTE_CLASS = re.compile(
    r"(bg|text|border|ring|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange"
    r"|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple"
    r"|fuchsia|pink|rose)-\d"
)


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
            config=SectionConfigBase,
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
    assert '<section data-panel="x"' in html


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
def test_a_panel_with_no_actions_renders_no_footer(mock_site_context: Site) -> None:
    html = _render(_bind(_PlainPanel))

    assert "<footer" not in html


@pytest.mark.django_db
def test_a_panels_heading_is_inside_the_card_not_a_sibling_of_it(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(_PlainPanel))

    document = lxml.html.fromstring(html)
    (section,) = document.cssselect('section[data-panel="x"]')
    (card,) = list(section)
    (heading,) = card.cssselect("h2")

    assert heading.getparent() is not section


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
    assert "aria-selected" not in html
    assert "data-tab-set" in html


def test_forced_colours_rules_live_with_their_components() -> None:
    """Each component's forced-colors rule is proved from its own source,
    not from the built CSS, so a later slice's rule shows up here too."""
    status_badge = (COMPONENTS_DIR / "panel-status-badge.html").read_text()
    progress_bar = (COMPONENTS_DIR / "panel-progress-bar.html").read_text()
    filter_toggle = (COMPONENTS_DIR / "panel-filter-toggle.html").read_text()

    assert "forced-colors:border" in status_badge
    assert "forced-colors: active" in progress_bar
    assert "forced-colors:" in filter_toggle
    assert "panel-progress-bar" not in TAILWIND_COMPONENTS_CSS.read_text()


def test_no_panel_component_uses_raw_colours() -> None:
    """Every panel-* component sources its colour from a role token, never a
    raw hex or a Tailwind default-palette utility, so a theme can recolour
    the whole kit by redefining tokens alone."""
    offenders: list[str] = []

    for path in sorted(COMPONENTS_DIR.glob("panel-*.html")):
        for line in path.read_text().splitlines():
            if "color-mix(" in line:
                continue
            if RAW_HEX_COLOUR.search(line) or RAW_TAILWIND_PALETTE_CLASS.search(line):
                offenders.append(f"{path.name}: {line.strip()}")

    assert offenders == []
