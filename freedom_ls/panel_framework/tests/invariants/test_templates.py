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

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, TabSet
from freedom_ls.panel_framework.views import SectionConfigBase

from ..helpers import make_stub
from ..stub_panels import StubDetailsPanel, StubHiddenPanel
from . import template_rules

FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_ROOT / "templates"
OVERRIDES_DIR = TESTS_DIR / "template_overrides"
COMPONENTS_DIR = TEMPLATES_DIR / "cotton"
FRAMEWORK_CSS = FRAMEWORK_ROOT / "css" / "panel_framework.css"
MODAL_HOST = TEMPLATES_DIR / "panel_framework" / "partials" / "modal_host.html"
SIDE_PANEL_HOST = FRAMEWORK_ROOT / "css" / "minimal_shell.css"
PARTIALS_DIR = TEMPLATES_DIR / "panel_framework" / "partials"
FRAMEWORK_SCRIPT = (
    FRAMEWORK_ROOT / "static" / "panel_framework" / "js" / "alpine-components.js"
)
INLINE_FORM = PARTIALS_DIR / "inline_record_form.html"
# Every template that renders inside #app-modal or a bottom sheet.
DIALOG_TEMPLATES = (
    *sorted((TEMPLATES_DIR / "panel_framework" / "modal").glob("*.html")),
    MODAL_HOST,
    PARTIALS_DIR / "table_sheet.html",
    PARTIALS_DIR / "bulk_confirmation.html",
    PARTIALS_DIR / "bulk_result.html",
    PARTIALS_DIR / "action_unavailable.html",
    PARTIALS_DIR / "action_denied.html",
)
DIALOG_BODIES = tuple(
    path
    for path in DIALOG_TEMPLATES
    if path.name not in ("modal_host.html", "table_sheet.html")
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
    assert template_rules.files_using_safe(TEMPLATES_DIR) == []


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

    assert "forced-colors:border" in status_badge
    assert "forced-colors: active" in progress_bar


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


@pytest.mark.parametrize(
    "selector",
    [
        ".panel-surface",
        ".panel-canvas",
        ".panel-heading",
        ".panel-table-selection-bar",
        ".panel-data-table-compact",
        ".modal-backdrop-host::backdrop",
    ],
)
def test_the_framework_stylesheet_defines_the_rules_its_templates_use(
    selector: str,
) -> None:
    assert selector in FRAMEWORK_CSS.read_text()


def test_the_framework_stylesheet_scopes_the_select_chevron_to_panel_surfaces() -> None:
    """A select inside a panel surface draws its own chevron without the
    host's global select rule."""
    css = FRAMEWORK_CSS.read_text()
    scoped_rules = re.findall(
        r"\n    :is\(\.panel-surface, \.panel-canvas\) select \{(.*?)\n    \}",
        css,
        re.DOTALL,
    )

    assert len(scoped_rules) == 1
    assert "appearance-none" in scoped_rules[0]
    assert "currentColor" in scoped_rules[0]
    assert "pr-10" in scoped_rules[0]


@pytest.mark.parametrize("host", [MODAL_HOST, SIDE_PANEL_HOST], ids=lambda p: p.name)
def test_the_modal_host_and_the_side_panel_clip_horizontal_overflow(
    host: Path,
) -> None:
    """Nothing inside a dialog or sheet can push it past the viewport edge."""
    text = host.read_text()

    assert "overflow-x: hidden" in text
    assert "max-width: 100vw" in text
    assert "max-width: none" not in text


DIALOG_WIDTHS = ("min(92vw, 32rem)", "100%")


def test_only_a_dialog_declaring_the_wide_size_widens_the_modal_host() -> None:
    """Any width other than the standard dialog's and the sheet's is set
    only by a rule keyed on data-modal-size="wide"."""
    css = re.sub(r"/\*.*?\*/", "", MODAL_HOST.read_text(), flags=re.DOTALL)
    selectors = [
        css[: css.rfind("{", 0, match.start())].rsplit("}", 1)[-1]
        for match in re.finditer(r"(?<![-\w])width:\s*([^;]+);", css)
        if match.group(1).strip() not in DIALOG_WIDTHS
    ]

    assert [s for s in selectors if 'data-modal-size="wide"' not in s] == []


def test_no_framework_dialog_declares_the_wide_size() -> None:
    declaring = template_rules.dialogs_declaring_the_wide_size(
        DIALOG_TEMPLATES, MODAL_HOST
    )

    assert declaring == set()


def test_every_dialog_ends_in_the_modal_footer_not_a_button_group() -> None:
    """A dialog's buttons sit in <c-modal-footer>, Cancel at the left and the
    actions at the right; <c-panel-button-group> is for buttons outside a dialog."""
    assert len(DIALOG_TEMPLATES) > 5
    offenders = template_rules.dialogs_using_a_button_group(
        DIALOG_TEMPLATES, "panel-button-group"
    )

    assert offenders == []


# Dialogs that do not take the header, body and footer parts, each with its reason.
DIALOG_PART_EXEMPTIONS: dict[str, str] = {
    "modal_host.html": "the host holds the parts only inside its discard prompt",
    "table_sheet.html": "the filter sheet is a bottom sheet with its own grouped body",
}


def test_every_dialog_is_a_header_a_body_and_a_footer() -> None:
    """Every dialog is built from the same three sibling parts, so the header
    and footer rules run the full width and the content lines up with the
    title and the buttons."""
    templates = [*DIALOG_TEMPLATES, PARTIALS_DIR / "bulk_run_stopped.html"]

    offenders = template_rules.dialogs_missing_a_part(
        templates, TEMPLATES_DIR, DIALOG_PART_EXEMPTIONS
    )

    assert offenders == []


def test_no_dialog_footer_sits_inside_the_body() -> None:
    """The footer is the body's sibling: inside the body it picks up the
    body's padding, so its rule stops short and its buttons sit out of line."""
    offenders = template_rules.dialogs_with_a_footer_inside_the_body(
        DIALOG_TEMPLATES, TEMPLATES_DIR
    )

    assert offenders == []


def test_no_dialog_pads_its_own_body() -> None:
    """<c-modal-body> owns a dialog body's padding and spacing; a hand-padded
    div is a second, slightly different body."""
    offenders = template_rules.dialogs_padding_their_own_body(
        DIALOG_TEMPLATES, DIALOG_PART_EXEMPTIONS
    )

    assert offenders == []


# Templates whose anchors are allowed the prose style, each with its reason.
PROSE_LINK_TEMPLATES: dict[str, str] = {
    "panel_framework/partials/sidebar_nav.html": "nav links colour the current item with aria-[current]:text-primary",
    "cotton/panel-back-link.html": "the back link primitive owns the one back-link style, text-primary included",
}


def test_no_control_link_is_hand_styled() -> None:
    """Every anchor in these templates is a control, so it takes a component
    or the row-link style (no-underline and its own colour). The prose
    underline, whether hand-typed or left to the base layer by an anchor
    that names no link style, and a hand-typed text-primary are how a
    control used to be styled by hand, page by page."""
    offenders = template_rules.hand_styled_control_links(
        TEMPLATES_DIR, PROSE_LINK_TEMPLATES
    )

    assert offenders == []


def test_no_template_hand_writes_a_table_outside_the_table_components() -> None:
    """A static table is `<c-panel-table>` and a list a user sorts or filters
    is `<c-data-table>`: both give the table its caption, header style and a
    focusable scroll region, so a hand-written `<table>` drifts from them."""
    offenders = template_rules.hand_written_tables(
        TEMPLATES_DIR, {"data-table.html", "panel-table.html"}
    )

    assert offenders == []


def test_every_framework_action_trigger_is_small() -> None:
    """The framework renders every action trigger (page header, panel
    footer, empty state, row) at the small size; only a dialog's footer
    buttons are full size."""
    for name in ("modal_trigger.html", "action_button.html"):
        assert 'size="small"' in (PARTIALS_DIR / name).read_text(), name


def test_no_button_hand_writes_a_touch_height() -> None:
    """A button looks the same at every width: the shared `.panel-btn` rule gives it
    an invisible 44px hit area below md, and only the dialog footer's rule
    makes a button 44px to the eye. So no button carries `min-h-11` itself.
    Dropdown menu items are not `.panel-btn`, so they keep theirs."""
    offenders = template_rules.hand_written_touch_heights(
        TEMPLATES_DIR, "panel-button", "panel-btn", "panel-dropdown-menu"
    )

    assert offenders == []


def test_only_the_dialog_footer_makes_a_panel_button_44px_tall_on_a_phone() -> None:
    """The framework stylesheet's one height rule for `.panel-btn` is the
    dialog footer's, beside the hit area every `.panel-btn` gets below md."""
    css = FRAMEWORK_CSS.read_text()
    height_rules = re.findall(r"\n    ([^\n{]*\.panel-btn[^\n{]*)\{[^}]*min-h-11", css)

    assert height_rules == ["[data-modal-footer] .panel-btn "]
    assert re.search(r"\.panel-btn::after \{[^}]*height: 2\.75rem", css)
    assert "data-modal-footer" in (COMPONENTS_DIR / "modal-footer.html").read_text()


def test_the_filter_sheet_has_a_close_control() -> None:
    """A sheet opens with a header holding the title and a close control,
    as the quick view does, so how to dismiss it is never in doubt."""
    sheet = (PARTIALS_DIR / "table_sheet.html").read_text()

    assert "<c-panel-close-button" in sheet
    assert "bottom-sheet" in sheet


def test_the_quick_view_is_never_modal() -> None:
    """A quick view leaves the page behind it usable at every width, so it
    opens with show() and carries no scrim."""
    host = (PARTIALS_DIR / "quick_view_host.html").read_text()
    script = FRAMEWORK_SCRIPT.read_text()
    quick_view = script[script.index('Alpine.data("quickView"') :]

    assert "modal-backdrop-host" not in host
    assert "showModal" not in quick_view


def test_every_anchor_with_visible_text_carries_its_own_classes() -> None:
    """A bare <a> falls back to the prose style; a control names its look."""
    offenders = template_rules.anchors_without_classes(
        TEMPLATES_DIR, PROSE_LINK_TEMPLATES
    )

    assert offenders == []


def test_every_expand_chevron_turns_when_its_control_opens() -> None:
    """A chevron on a menu button, disclosure or filter chip points down while
    closed and up while open, so each one carries a rotate-180 variant, on
    itself or on the span that wraps it."""
    offenders = template_rules.expand_chevrons_that_do_not_turn(TEMPLATES_DIR)

    assert offenders == []


@pytest.mark.parametrize("path", DIALOG_BODIES, ids=lambda path: path.name)
def test_every_dialog_renders_one_modal_footer_outside_its_body(path: Path) -> None:
    """A dialog template holds one footer per step it renders, or none when
    it extends a template that supplies it; the footer is never inside the
    body, which is the part that scrolls under it."""
    assert template_rules.dialog_footer_problems(path) == []


FORBIDDEN_IN_DIALOGS = template_rules.forbidden_in_dialogs("panel-button")


@pytest.mark.parametrize("rule", sorted(FORBIDDEN_IN_DIALOGS))
def test_no_dialog_template_hand_writes_what_a_component_owns(rule: str) -> None:
    offenders = template_rules.dialogs_matching(
        DIALOG_BODIES, FORBIDDEN_IN_DIALOGS[rule]
    )

    assert offenders == [], (
        f"{rule} in a dialog template: use <c-panel-callout> in a framework "
        "template, <c-callout> in an FLS template"
    )


def test_no_framework_template_calls_the_host_callout() -> None:
    offenders = [
        str(path.relative_to(TEMPLATES_DIR))
        for path in TEMPLATES_DIR.rglob("*.html")
        if re.search(r"<c-callout(?![\w-])", path.read_text())
    ]

    assert offenders == [], (
        "the panel framework imports nothing from a host project: use "
        "<c-panel-callout>, which a host renders as its own callout"
    )


def test_every_dialog_loading_text_ends_in_the_ellipsis_character() -> None:
    offenders = template_rules.loading_texts_ending_in_three_dots(
        (*DIALOG_BODIES, INLINE_FORM)
    )

    assert offenders == []


# `find` matches the first element only, so a form with several submit
# buttons names all of them through the modal body instead. The same goes for
# a form holding an element that issues its own request, because that element
# inherits the form's selector and `find` would look inside it.
MULTI_SUBMIT_DIALOGS = {"form.html"}


def test_every_dialog_disables_only_its_own_submit_buttons() -> None:
    offenders = template_rules.dialogs_disabling_more_than_their_submit_buttons(
        DIALOG_BODIES, MULTI_SUBMIT_DIALOGS
    )

    assert offenders == []


def test_no_dialog_form_with_a_find_selector_holds_an_element_that_issues_its_own_request() -> (
    None
):
    """An element inside a form inherits the form's hx-disabled-elt, and `find`
    resolves relative to that element, so a select that issues its own request
    logged "returned no matches" in the console."""
    offenders = template_rules.requesting_elements_inside_a_find_form(DIALOG_BODIES)

    assert offenders == []


COTTON_TAG = re.compile(r"<c-([a-z][a-z0-9-]*)")
COTTON_SYNTAX_TAGS = {"vars", "slot"}
HOST_SUPPLIED_COMPONENTS = {"icon"}


def test_every_cotton_tag_in_a_framework_template_is_a_framework_component() -> None:
    available = {
        path.relative_to(COMPONENTS_DIR).with_suffix("").as_posix().replace("/", ".")
        for path in COMPONENTS_DIR.rglob("*.html")
    }
    used = {
        name
        for path in TEMPLATES_DIR.rglob("*.html")
        for name in COTTON_TAG.findall(path.read_text())
    }

    assert used - available - COTTON_SYNTAX_TAGS - HOST_SUPPLIED_COMPONENTS == set()


INCLUDE_OR_EXTENDS_PATH = re.compile(r"\{%\s*(?:include|extends)\s+[\"']([^\"']+)[\"']")
ALLOWED_TEMPLATE_PREFIXES = ("panel_framework/", "cotton/", "django/forms/")
FLS_APP_LABELS = (
    "accounts",
    "api",
    "api_admin",
    "audit_log",
    "base",
    "blog",
    "comms",
    "content_base",
    "content_engine",
    "course_access",
    "course_applications",
    "course_interest",
    "course_recommendations",
    "deadlines",
    "deployment",
    "educator_interface",
    "form_engine",
    "google_tag",
    "health",
    "hr_attributes",
    "icons",
    "learner_interface",
    "learner_management",
    "learner_progress",
    "mail",
    "markdown_rendering",
    "messaging_policy",
    "meta_pixel",
    "organisations",
    "referral_tracking",
    "registration_rules",
    "reports",
    "role_based_permissions",
    "site_aware_models",
    "tiktok_pixel",
    "webhooks",
)
# An app named in a template path, a URL namespace or a dotted module path.
FLS_ONLY_NAMES = re.compile(
    rf"\bfreedom_ls\b|\b(?:{'|'.join(FLS_APP_LABELS)})(?=/|:\w)|\bconversationChanged\b"
)


def test_no_framework_template_includes_or_extends_a_path_outside_the_framework() -> (
    None
):
    outside = {
        f"{path.relative_to(TEMPLATES_DIR).as_posix()}: {target}"
        for path in TEMPLATES_DIR.rglob("*.html")
        for target in INCLUDE_OR_EXTENDS_PATH.findall(path.read_text())
        if not target.startswith(ALLOWED_TEMPLATE_PREFIXES)
    }

    assert outside == set()


def test_no_framework_template_names_an_fls_app_or_an_fls_only_event() -> None:
    offenders = {
        f"{path.relative_to(TEMPLATES_DIR).as_posix()}: {name}"
        for path in TEMPLATES_DIR.rglob("*.html")
        for name in FLS_ONLY_NAMES.findall(path.read_text())
    }

    assert offenders == set()


HOST_ONLY_TEST_NAMES = re.compile(
    r"FREEDOM_LS_PACKAGE_DIR|tailwind\.components\.css|freedom_ls\.tests\.playwright_helpers"
)
# `_base.html` as a whole file name: the framework's own `_main_base.html` and
# `_panel_base.html` are its own templates.
HOST_ONLY_TEMPLATE_NAMES = re.compile(
    r"(?<![\w])_base\.html|_base_interface\.html|pagination_tags|fls_base_filters"
)


def test_no_framework_test_names_a_host_only_path_or_module() -> None:
    offenders = {
        path.relative_to(TESTS_DIR).as_posix()
        for path in TESTS_DIR.rglob("*.py")
        if path != Path(__file__) and HOST_ONLY_TEST_NAMES.search(path.read_text())
    }

    assert offenders == set()


def test_no_framework_template_names_a_host_only_template_or_module() -> None:
    offenders = {
        f"{path.relative_to(TEMPLATES_DIR).as_posix()}: {name}"
        for path in TEMPLATES_DIR.rglob("*.html")
        for name in HOST_ONLY_TEMPLATE_NAMES.findall(path.read_text())
    }

    assert offenders == set()


HOST_BUTTON_CLASS = re.compile(r"""class="[^"]*(?<![\w-])btn(?:-[\w-]+)?(?![\w-])""")


def test_no_framework_template_uses_a_host_button_class() -> None:
    """The framework's stylesheet styles `.panel-btn`; a bare `btn` class is a
    host's, and outside that host the button is unstyled."""
    offenders = [
        str(path.relative_to(TEMPLATES_DIR))
        for path in sorted(TEMPLATES_DIR.rglob("*.html"))
        if HOST_BUTTON_CLASS.search(path.read_text())
    ]

    assert offenders == []


def test_the_data_table_actions_wrapper_carries_its_hook_class() -> None:
    """A host whose button override draws its own classes keeps the labels on
    one line by selecting the wrapper's hook class."""
    source = (COMPONENTS_DIR / "data-table-actions.html").read_text()

    assert re.search(r'<div class="[^"]*\bpanel-data-table-actions\b', source)
