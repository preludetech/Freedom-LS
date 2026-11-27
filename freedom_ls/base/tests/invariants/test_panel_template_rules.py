"""FLS's own stylesheet and base templates against the panel template rules.

The framework owns its surface, canvas and dialog rules; `tailwind.components.css`
carries only the project's base-layer rules and the `.btn` family. The shared
template walks (`template_rules`) run over the base templates, which spell
the components `c-button` and `c-dropdown-menu`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from panel_framework.testing import template_rules

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

TAILWIND_COMPONENTS_CSS: Path = (
    FREEDOM_LS_PACKAGE_DIR.parent / "tailwind.components.css"
)
BASE_TEMPLATES_DIR: Path = FREEDOM_LS_PACKAGE_DIR / "base" / "templates"
BASE_INTERFACE: Path = BASE_TEMPLATES_DIR / "_base_interface.html"


def test_the_base_select_rule_draws_its_own_chevron_inside_the_end_padding() -> None:
    """A select keeps its arrow clear of the edge: the base rule hides the
    browser's own, draws one in currentColor, and pads the end for it."""
    css = TAILWIND_COMPONENTS_CSS.read_text()
    select_rules = re.findall(r"\n    select \{(.*?)\n    \}", css, re.DOTALL)
    chevron_rules = [body for body in select_rules if "appearance-none" in body]

    assert len(chevron_rules) == 1
    assert "currentColor" in chevron_rules[0]
    assert "pr-10" in chevron_rules[0]


def test_no_button_rule_sets_a_touch_height() -> None:
    """No `.btn` rule sets `min-h-11`: every button, a dialog footer's
    included, is small below md and reaches 44px through the invisible ::after
    hit area every `.btn` gets there."""
    css = TAILWIND_COMPONENTS_CSS.read_text()
    height_rules = re.findall(r"\n    ([^\n{]*\.btn[^\n{]*)\{[^}]*min-h-11", css)

    assert height_rules == []
    assert re.search(r"\.btn::after \{[^}]*height: 2\.75rem", css)


@pytest.mark.parametrize(
    "selector",
    [
        ".panel-surface",
        ".panel-canvas",
        ".modal-backdrop-host",
        ".panel-heading",
        ".panel-table-selection-bar",
        ".panel-data-table-compact",
        ".panel-progress-bar",
    ],
)
def test_the_components_stylesheet_defines_no_framework_rule(selector: str) -> None:
    assert selector not in TAILWIND_COMPONENTS_CSS.read_text()


def test_the_interface_base_clips_horizontal_overflow_on_its_dialogs() -> None:
    """Nothing inside a dialog or sheet can push it past the viewport edge."""
    text = BASE_INTERFACE.read_text()

    assert "overflow-x: hidden" in text
    assert "max-width: 100vw" in text
    assert "max-width: none" not in text


def test_no_base_button_hand_writes_a_touch_height() -> None:
    offenders = template_rules.hand_written_touch_heights(
        BASE_TEMPLATES_DIR, "button", "btn", "dropdown-menu"
    )

    assert offenders == []


def test_every_base_expand_chevron_turns_when_its_control_opens() -> None:
    assert template_rules.expand_chevrons_that_do_not_turn(BASE_TEMPLATES_DIR) == []


ACCOUNTS_TEMPLATES_DIR: Path = (
    FREEDOM_LS_PACKAGE_DIR / "accounts" / "templates" / "accounts"
)
EDUCATOR_TEMPLATES_DIR: Path = (
    FREEDOM_LS_PACKAGE_DIR / "educator_interface" / "templates" / "educator_interface"
)
TEMPLATE_COMMENT = re.compile(
    r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}", re.DOTALL
)


def test_no_fls_panel_template_calls_the_site_callout() -> None:
    """An FLS panel-framework template used <c-callout> where <c-panel-callout> belongs."""
    paths = [
        *ACCOUNTS_TEMPLATES_DIR.rglob("*.html"),
        *EDUCATOR_TEMPLATES_DIR.rglob("*.html"),
    ]
    offenders = [
        str(path.relative_to(FREEDOM_LS_PACKAGE_DIR))
        for path in paths
        if re.search(r"<c-callout(?![\w-])", TEMPLATE_COMMENT.sub("", path.read_text()))
    ]

    assert offenders == [], (
        "a notice on a panel-framework page is <c-panel-callout>; "
        "<c-callout> is for pages outside the panel framework"
    )


ACCOUNTS_TEMPLATES_ROOT: Path = FREEDOM_LS_PACKAGE_DIR / "accounts" / "templates"
EDUCATOR_TEMPLATES_ROOT: Path = (
    FREEDOM_LS_PACKAGE_DIR / "educator_interface" / "templates"
)
# Signup pages, outside the panel framework: they draw their own field errors.
ACCOUNTS_ALERT_OWNERS = frozenset(
    {
        "accounts/complete_registration.html",
        "cotton/consent-checkboxes.html",
    }
)


@pytest.mark.parametrize(
    ("root", "allowed"),
    [
        (ACCOUNTS_TEMPLATES_ROOT, ACCOUNTS_ALERT_OWNERS),
        (EDUCATOR_TEMPLATES_ROOT, frozenset()),
    ],
    ids=["accounts", "educator_interface"],
)
def test_only_the_callout_and_the_field_error_draw_an_alert(
    root: Path, allowed: frozenset[str]
) -> None:
    """An FLS panel-framework template drew an error or warning by hand."""
    offenders = template_rules.hand_drawn_alerts(root, allowed)

    assert offenders == [], (
        "an error or warning is <c-panel-callout>, and a field's own error is "
        "panel_framework/partials/field_error.html: no template writes "
        'role="alert", text-error or an error or warning tint itself'
    )


@pytest.mark.parametrize(
    "root",
    [ACCOUNTS_TEMPLATES_ROOT, EDUCATOR_TEMPLATES_ROOT],
    ids=["accounts", "educator_interface"],
)
def test_every_request_error_holder_is_the_shared_partial(root: Path) -> None:
    """An FLS template wrote a request-error holder of its own."""
    offenders = template_rules.request_error_holders(root, frozenset())

    assert offenders == [], (
        "a failed request shows in panel_framework/partials/request_error.html: "
        "include it, never write a [data-request-error] element"
    )
