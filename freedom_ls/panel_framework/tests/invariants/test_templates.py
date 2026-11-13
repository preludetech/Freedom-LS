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

from ..helpers import make_stub
from ..stub_panels import StubDetailsPanel, StubHiddenPanel

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
OVERRIDES_DIR = Path(__file__).resolve().parent.parent / "template_overrides"
COMPONENTS_DIR = TEMPLATES_DIR / "cotton"
TAILWIND_COMPONENTS_CSS = FREEDOM_LS_PACKAGE_DIR.parent / "tailwind.components.css"
MODAL_HOST = TEMPLATES_DIR / "panel_framework" / "partials" / "modal_host.html"
SIDE_PANEL_HOST = FREEDOM_LS_PACKAGE_DIR / "base" / "templates" / "_base_interface.html"
EDUCATOR_TEMPLATES_DIR = (
    FREEDOM_LS_PACKAGE_DIR / "educator_interface" / "templates" / "educator_interface"
)
EDUCATOR_MODAL_DIR = (
    FREEDOM_LS_PACKAGE_DIR
    / "educator_interface"
    / "templates"
    / "educator_interface"
    / "modal"
)
# Every template that renders inside #app-modal or a bottom sheet.
DIALOG_TEMPLATES = (
    *sorted((TEMPLATES_DIR / "panel_framework" / "modal").glob("*.html")),
    *sorted(EDUCATOR_MODAL_DIR.glob("*.html")),
    MODAL_HOST,
    TEMPLATES_DIR / "panel_framework" / "partials" / "table_sheet.html",
    TEMPLATES_DIR / "panel_framework" / "partials" / "bulk_confirmation.html",
    TEMPLATES_DIR / "panel_framework" / "partials" / "bulk_result.html",
    TEMPLATES_DIR / "panel_framework" / "partials" / "action_unavailable.html",
    TEMPLATES_DIR / "panel_framework" / "partials" / "action_denied.html",
)

RAW_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RAW_TAILWIND_PALETTE_CLASS = re.compile(
    r"(bg|text|border|ring|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange"
    r"|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple"
    r"|fuchsia|pink|rose)-\d"
)


class _PlainPanel(Panel):
    title = "Plain"


class _PanelWithTwoRefreshEvents(Panel):
    title = "Refreshing"
    refresh_events = ("a", "b")


class _TabsWithAHiddenOne(TabSet):
    title = "Sections"
    children = {
        "shown": _PlainPanel,
        "also_shown": _PlainPanel,
        "hidden": StubHiddenPanel,
    }


class _TabsWithOneChild(TabSet):
    title = "Sections"
    children = {"only": _PlainPanel}


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
    assert ">Plain</h2>" in html
    assert 'data-panel="x"' in html


@pytest.mark.django_db
def test_a_panel_template_extending_the_framework_template_renders_both(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(StubDetailsPanel, make_stub(name="Extended")))

    assert "<p data-stub-details>Extended</p>" in html
    assert ">Details</h2>" in html
    assert '<section data-panel="x"' in html


@pytest.mark.django_db
def test_a_leaf_declaring_refresh_events_refetches_its_own_region(
    mock_site_context: Site,
) -> None:
    panel = _bind(_PanelWithTwoRefreshEvents)

    html = _render(panel)

    assert 'hx-trigger="a from:body delay:10ms, b from:body delay:10ms"' in html
    assert f'hx-target="#{panel.region_id}"' in html
    assert f'id="{panel.region_id}"' in html


def test_a_view_template_with_no_page_header_still_draws_the_navigation_toggle() -> (
    None
):
    """A page that fills in no heading (the bare main base, as the empty path
    renders) keeps the toggle, or a phone has no way into the navigation."""
    html = render_to_string("panel_framework/views/_main_base.html")

    document = lxml.html.fromstring(html)
    (toggle,) = document.cssselect(
        "#main-content button[aria-label='Open navigation panel']"
    )
    assert toggle.get("x-on:click") == "toggle"


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
def test_a_leaf_declaring_no_refresh_events_never_refetches(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(_PlainPanel))

    assert "hx-get" not in html
    assert "hx-trigger" not in html


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


@pytest.mark.django_db
def test_a_tab_set_with_one_tab_renders_its_content_without_a_tab_strip(
    mock_site_context: Site,
) -> None:
    html = _render(_bind(_TabsWithOneChild, name=""))

    document = lxml.html.fromstring(html)
    assert not document.cssselect("nav[aria-label]")
    (region,) = document.cssselect("[data-tab-set]")
    assert "Plain" in region.text_content()


def test_forced_colours_rules_live_with_their_components() -> None:
    """Each component's forced-colors rule is proved from its own source,
    not from the built CSS, so a rule added later shows up here too."""
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


def test_an_instance_pages_trail_renders_as_a_back_link_to_its_section() -> None:
    html = render_to_string(
        "panel_framework/partials/breadcrumbs.html",
        {
            "breadcrumbs": [
                {"label": "Cohorts", "url": "/test-panel/cohorts"},
                {"label": "Year 9 Maths"},
            ]
        },
    )

    document = lxml.html.fromstring(html)
    (link,) = document.cssselect("#breadcrumbs a")
    assert link.get("href") == "/test-panel/cohorts"
    assert link.get("hx-get") == "/test-panel/cohorts"
    assert link.get("hx-target") == "#main-content"
    assert link.text_content().strip() == "Cohorts"
    assert link.cssselect("svg")
    assert "Year 9 Maths" not in html


def test_a_list_pages_trail_renders_no_link_at_all() -> None:
    html = render_to_string(
        "panel_framework/partials/breadcrumbs.html",
        {"breadcrumbs": [{"label": "Cohorts"}]},
    )

    document = lxml.html.fromstring(html)
    assert document.get("id") == "breadcrumbs" or document.cssselect("#breadcrumbs")
    assert not document.cssselect("a")
    assert "Cohorts" not in html


def test_the_quick_view_open_full_page_link_shows_the_open_page_icon() -> None:
    html = render_to_string("panel_framework/partials/quick_view_host.html")

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (link,) = document.cssselect("#quick-view-open")
    (icon,) = link.cssselect("svg")
    assert icon.get("data-icon") == "open_page"


def test_the_base_select_rule_draws_its_own_chevron_inside_the_end_padding() -> None:
    """A select keeps its arrow clear of the edge: the base rule hides the
    browser's own, draws one in currentColor, and pads the end for it."""
    css = TAILWIND_COMPONENTS_CSS.read_text()
    select_rules = re.findall(r"\n    select \{(.*?)\n    \}", css, re.DOTALL)
    chevron_rules = [body for body in select_rules if "appearance-none" in body]

    assert len(chevron_rules) == 1
    assert "currentColor" in chevron_rules[0]
    assert "pr-10" in chevron_rules[0]


def test_the_modal_host_and_the_side_panel_clip_horizontal_overflow() -> None:
    """Nothing inside a dialog or sheet can push it past the viewport edge."""
    for host in (MODAL_HOST, SIDE_PANEL_HOST):
        text = host.read_text()

        assert "overflow-x: hidden" in text, host.name
        assert "max-width: 100vw" in text, host.name
        assert "max-width: none" not in text, host.name


WIDE_FRAGMENTS = frozenset({"content_preview.html", "course_details_preview.html"})
DIALOG_WIDTHS = ("min(92vw, 32rem)", "100%")


def test_only_a_fragment_declaring_the_wide_size_widens_the_dialog() -> None:
    """Any width other than the standard dialog's and the sheet's is set
    only by a rule keyed on data-modal-size="wide", and only the content
    preview fragments declare it."""
    css = re.sub(r"/\*.*?\*/", "", MODAL_HOST.read_text(), flags=re.DOTALL)
    for match in re.finditer(r"(?<![-\w])width:\s*([^;]+);", css):
        if match.group(1).strip() in DIALOG_WIDTHS:
            continue
        selector = css[: css.rfind("{", 0, match.start())].rsplit("}", 1)[-1]
        assert 'data-modal-size="wide"' in selector, selector
    declaring = {
        path.name
        for path in DIALOG_TEMPLATES
        if 'data-modal-size="wide"' in path.read_text() and path != MODAL_HOST
    }
    assert declaring == WIDE_FRAGMENTS


def test_every_dialog_ends_in_the_modal_footer_not_a_button_group() -> None:
    """A dialog's buttons sit in <c-modal-footer>, Cancel at the left and the
    actions at the right; <c-button-group> is for buttons outside a dialog."""
    assert len(DIALOG_TEMPLATES) > 20
    offenders = [
        path.name for path in DIALOG_TEMPLATES if "<c-button-group" in path.read_text()
    ]

    assert offenders == []


# Dialogs that do not take the header, body and footer parts, each with its reason.
DIALOG_PART_EXEMPTIONS: dict[str, str] = {
    "modal_host.html": "the host holds the parts only inside its discard prompt",
    "table_sheet.html": "the filter sheet is a bottom sheet with its own grouped body",
    "conversation_oversight.html": "the thread pane brings its own edge-to-edge layout",
}
MODAL_BODY_BLOCK = re.compile(r"<c-modal-body\b.*?</c-modal-body>", re.DOTALL)
HAND_PADDED_BODY = re.compile(r'<div class="[^"]*\bpx-6\b[^"]*"')


def _dialog_parts_source(path: Path) -> str:
    """The template's text, with message.html's parts counted for its children."""
    text = path.read_text()
    if '{% extends "panel_framework/modal/message.html" %}' in text:
        text += (
            TEMPLATES_DIR / "panel_framework" / "modal" / "message.html"
        ).read_text()
    return text


def test_every_dialog_is_a_header_a_body_and_a_footer() -> None:
    """Every dialog is built from the same three sibling parts, so the header
    and footer rules run the full width and the content lines up with the
    title and the buttons."""
    templates = [
        *DIALOG_TEMPLATES,
        *sorted(
            path
            for path in EDUCATOR_MODAL_DIR.glob("*.html")
            if path not in DIALOG_TEMPLATES
        ),
        TEMPLATES_DIR / "panel_framework" / "partials" / "bulk_run_stopped.html",
    ]
    offenders = []
    for path in templates:
        if path.name in DIALOG_PART_EXEMPTIONS:
            continue
        text = _dialog_parts_source(path)
        if "<c-modal-header" not in text and "{% include" in text:
            continue
        for part in ("<c-modal-header", "<c-modal-body", "<c-modal-footer"):
            if part not in text:
                offenders.append(f"{path.name}: no {part}>")
    assert offenders == []


def test_no_dialog_footer_sits_inside_the_body() -> None:
    """The footer is the body's sibling: inside the body it picks up the
    body's padding, so its rule stops short and its buttons sit out of line."""
    offenders = [
        path.name
        for path in (*DIALOG_TEMPLATES, *EDUCATOR_MODAL_DIR.glob("*.html"))
        if any(
            "<c-modal-footer" in block
            for block in MODAL_BODY_BLOCK.findall(_dialog_parts_source(path))
        )
    ]
    assert offenders == []


def test_no_dialog_pads_its_own_body() -> None:
    """<c-modal-body> owns a dialog body's padding and spacing; a hand-padded
    div is a second, slightly different body."""
    offenders = [
        path.name
        for path in (*DIALOG_TEMPLATES, *EDUCATOR_MODAL_DIR.glob("*.html"))
        if path.name not in DIALOG_PART_EXEMPTIONS
        and HAND_PADDED_BODY.search(path.read_text())
    ]
    assert offenders == []


CONTROL_TAG = re.compile(r"<(a|button)\b([^>]*)>", re.DOTALL)
CLASS_ATTR = re.compile(r'class="([^"]*)"', re.DOTALL)
# Templates whose anchors are allowed the prose style, each with its reason.
PROSE_LINK_TEMPLATES: dict[str, str] = {
    "panel_framework/partials/sidebar_nav.html": "nav links colour the current item with aria-[current]:text-primary",
}


def _control_tags(path: Path) -> list[str]:
    return [match.group(0) for match in CONTROL_TAG.finditer(path.read_text())]


def test_no_control_link_is_hand_styled() -> None:
    """Every anchor in these templates is a control, so it takes a component
    or the row-link style (no-underline and its own colour). The prose
    underline, whether hand-typed or left to the base layer by an anchor
    that names no link style, and a hand-typed text-primary are how a
    control used to be styled by hand, page by page."""
    offenders: list[str] = []
    for root in (TEMPLATES_DIR, EDUCATOR_TEMPLATES_DIR):
        for path in sorted(root.rglob("*.html")):
            relative = str(path.relative_to(root))
            if relative in PROSE_LINK_TEMPLATES:
                continue
            for tag in _control_tags(path):
                classes = CLASS_ATTR.search(tag)
                tokens = set(classes.group(1).split()) if classes else set()
                if "underline" in tokens or "text-primary" in tokens:
                    offenders.append(f"{relative}: {tag[:80]}")
                elif tag.startswith("<a") and "{{ attrs }}" not in tag:
                    styled = "no-underline" in tokens or any(
                        token.startswith("btn") for token in tokens
                    )
                    if not styled:
                        offenders.append(f"{relative}: {tag[:80]}")

    assert offenders == []


def test_no_template_hand_writes_a_table_outside_the_table_components() -> None:
    """A static table is `<c-panel-table>` and a list a user sorts or filters
    is `<c-data-table>`: both give the table its caption, header style and a
    focusable scroll region, so a hand-written `<table>` drifts from them."""
    table_components = {"data-table.html", "panel-table.html"}
    offenders: list[str] = []
    for root in (TEMPLATES_DIR, EDUCATOR_TEMPLATES_DIR):
        for path in sorted(root.rglob("*.html")):
            if path.name in table_components:
                continue
            source = re.sub(
                r"{% comment %}.*?{% endcomment %}", "", path.read_text(), flags=re.S
            )
            if re.search(r"<table\b", source):
                offenders.append(str(path.relative_to(root)))

    assert offenders == []


def test_every_framework_action_trigger_is_small() -> None:
    """The framework renders every action trigger (page header, panel
    footer, empty state, row) at the small size; only a dialog's footer
    buttons are full size."""
    partials = TEMPLATES_DIR / "panel_framework" / "partials"
    for name in ("modal_trigger.html", "action_button.html"):
        assert 'size="small"' in (partials / name).read_text(), name


def test_no_button_hand_writes_a_touch_height() -> None:
    """The interface button rule already gives every `.btn` 44px on a phone,
    so a button never carries `min-h-11` itself. Dropdown menu items are not
    `.btn`, so they keep theirs."""
    offenders = []
    for root in (TEMPLATES_DIR, EDUCATOR_TEMPLATES_DIR):
        for path in sorted(root.rglob("*.html")):
            source = path.read_text()
            for tag in re.findall(r"<c-button\b[^>]*>", source):
                if "min-h-11" in tag and "dropdown=" not in tag:
                    offenders.append(f"{path.name}: {tag[:80]}")
            for trigger in re.findall(r'trigger_class="btn[^"]*"', source):
                if "min-h-11" in trigger:
                    offenders.append(f"{path.name}: {trigger}")
    assert offenders == []


def test_the_filter_sheet_has_a_close_control() -> None:
    """A sheet opens with a header holding the title and a close control,
    as the quick view does, so how to dismiss it is never in doubt."""
    sheet = (
        TEMPLATES_DIR / "panel_framework" / "partials" / "table_sheet.html"
    ).read_text()

    assert "<c-panel-close-button" in sheet
    assert "bottom-sheet" in sheet


def test_the_quick_view_is_never_modal() -> None:
    """A quick view leaves the page behind it usable at every width, so it
    opens with show() and carries no scrim."""
    host = (
        TEMPLATES_DIR / "panel_framework" / "partials" / "quick_view_host.html"
    ).read_text()
    script = (
        FREEDOM_LS_PACKAGE_DIR
        / "panel_framework"
        / "static"
        / "panel_framework"
        / "js"
        / "alpine-components.js"
    ).read_text()
    quick_view = script[script.index('Alpine.data("quickView"') :]

    assert "modal-backdrop-host" not in host
    assert "showModal" not in quick_view


def test_every_anchor_with_visible_text_carries_its_own_classes() -> None:
    """A bare <a> falls back to the prose style; a control names its look."""
    offenders: list[str] = []
    for root in (TEMPLATES_DIR, EDUCATOR_TEMPLATES_DIR):
        for path in sorted(root.rglob("*.html")):
            relative = str(path.relative_to(root))
            if relative in PROSE_LINK_TEMPLATES:
                continue
            text = path.read_text()
            for match in re.finditer(r"<a\b([^>]*)>(.*?)</a>", text, re.DOTALL):
                attributes, content = match.group(1), match.group(2)
                if "class=" in attributes or "{{ attrs }}" in attributes:
                    continue
                if "<c-icon" in content and not re.sub(r"<[^>]+>|\s", "", content):
                    continue
                offenders.append(f"{relative}: {match.group(0)[:80]}")

    assert offenders == []


DROPDOWN_CHEVRON = re.compile(r'<c-icon name="dropdown"[^>]*>')


def test_every_expand_chevron_turns_when_its_control_opens() -> None:
    """A chevron on a menu button, disclosure or filter chip points down while
    closed and up while open, so each one carries a rotate-180 variant, on
    itself or on the span that wraps it."""
    offenders: list[str] = []
    roots = (
        TEMPLATES_DIR,
        EDUCATOR_TEMPLATES_DIR,
        FREEDOM_LS_PACKAGE_DIR / "base" / "templates",
    )
    for root in roots:
        for path in sorted(root.rglob("*.html")):
            text = path.read_text()
            for match in DROPDOWN_CHEVRON.finditer(text):
                wrapper = text[max(0, match.start() - 200) : match.start()]
                last_tag = wrapper[wrapper.rfind("<") :]
                if "rotate-180" not in match.group(0) and "rotate-180" not in last_tag:
                    offenders.append(f"{path.relative_to(root)}: {match.group(0)}")

    assert offenders == []


DIALOG_BODIES = tuple(
    path
    for path in DIALOG_TEMPLATES
    if path.name not in ("modal_host.html", "table_sheet.html")
)
MODAL_BODY_SPAN = re.compile(r"<c-modal-body\b.*?</c-modal-body>", re.DOTALL)
STEP_BRANCH = re.compile(r"\bstep == ")
EDUCATOR_PYTHON_FILES = sorted(
    (FREEDOM_LS_PACKAGE_DIR / "educator_interface").glob("*.py")
)


def _dialog_id(path: Path) -> str:
    return path.name


@pytest.mark.parametrize("path", DIALOG_BODIES, ids=_dialog_id)
def test_every_dialog_renders_one_modal_footer_outside_its_body(path: Path) -> None:
    """A dialog template holds one footer per step it renders, or none when
    it extends a template that supplies it; the footer is never inside the
    body, which is the part that scrolls under it."""
    text = path.read_text()
    steps = max(1, len(STEP_BRANCH.findall(text)))
    footers = [m.start() for m in re.finditer(r"<c-modal-footer\b", text)]
    inside_body = [
        start
        for start in footers
        for span in MODAL_BODY_SPAN.finditer(text)
        if span.start() < start < span.end()
    ]

    assert inside_body == []
    assert len(footers) <= steps
    if "{% extends" in text:
        assert footers == []


FORBIDDEN_IN_DIALOGS = {
    "a hand-written Cancel button": re.compile(r">\s*Cancel\s*</(c-)?button>"),
    "text-sm": re.compile(r"(?<![\w-])text-sm\b"),
    "px-6 py-4": re.compile(r"px-6 py-4"),
    "a bg-error/10 box": re.compile(r"bg-error/10"),
    "<c-callout>": re.compile(r"<c-callout\b"),
}


@pytest.mark.parametrize("rule", sorted(FORBIDDEN_IN_DIALOGS))
def test_no_dialog_template_hand_writes_what_a_component_owns(rule: str) -> None:
    offenders = [
        path.name
        for path in DIALOG_BODIES
        if FORBIDDEN_IN_DIALOGS[rule].search(path.read_text())
    ]

    assert offenders == []


def test_every_dialog_loading_text_ends_in_the_ellipsis_character() -> None:
    offenders = [
        f"{path.name}: {match}"
        for path in DIALOG_BODIES
        for match in re.findall(r'loading_text="[^"]*"', path.read_text())
        if "..." in match
    ]

    assert offenders == []


# `find` matches the first element only, so a form with several submit
# buttons names all of them through the modal body instead.
MULTI_SUBMIT_DIALOGS = {"form.html"}


def test_every_dialog_disables_only_its_own_submit_buttons() -> None:
    offenders = [
        f"{path.name}: {match}"
        for path in DIALOG_BODIES
        if path.name not in MULTI_SUBMIT_DIALOGS
        for match in re.findall(r'hx-disabled-elt="[^"]*"', path.read_text())
        if match != "hx-disabled-elt=\"find button[type='submit']\""
    ]

    assert offenders == []


def test_no_educator_module_sets_the_modal_trigger_template_by_hand() -> None:
    """The framework's modal action classes own the modal trigger, so an app
    extends one of them instead of naming the template."""
    offenders = [
        path.name
        for path in EDUCATOR_PYTHON_FILES
        if re.search(
            r'trigger_template_name\s*=\s*"panel_framework/partials/modal_trigger.html"',
            path.read_text(),
        )
    ]

    assert offenders == []
