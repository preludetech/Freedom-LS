"""FLS's panel-primitive wrappers render exactly what the component they stand in for rendered."""

from __future__ import annotations

import re

import pytest
from django_cotton.compiler_regex import CottonCompiler
from lxml import html as lxml_html

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _normalised(source: str) -> str:
    rendered = Template(_cotton_compiler.process(source)).render(Context())
    fragment = lxml_html.fragment_fromstring(rendered, create_parent="div")
    return re.sub(r"\s+", " ", lxml_html.tostring(fragment, encoding="unicode")).strip()


WRAPPER_PAIRS = [
    pytest.param(
        f'<c-panel-chip variant="{variant}">Text</c-panel-chip>',
        f'<c-chip variant="{variant}">Text</c-chip>',
        id=f"chip-{variant}",
    )
    for variant in [
        "primary",
        "warning",
        "success",
        "error",
        "info",
        "secondary",
        "muted",
    ]
] + [
    pytest.param(
        '<c-panel-chip size="xs">Text</c-panel-chip>',
        '<c-chip size="xs">Text</c-chip>',
        id="chip-xs",
    ),
    pytest.param(
        '<c-panel-chip class="shrink-0">Text</c-panel-chip>',
        '<c-chip class="shrink-0">Text</c-chip>',
        id="chip-class",
    ),
    pytest.param(
        '<c-panel-chip data-tone="ok">Text</c-panel-chip>',
        '<c-chip data-tone="ok">Text</c-chip>',
        id="chip-data-attribute",
    ),
]


BUTTON_VARIANTS = [
    "primary",
    "secondary",
    "ghost",
    "link",
    "accent",
    "success",
    "error",
]

BUTTON_PAIRS = [
    pytest.param(
        f'<c-panel-button variant="{variant}">Go</c-panel-button>',
        f'<c-button variant="{variant}">Go</c-button>',
        id=f"button-{variant}",
    )
    for variant in BUTTON_VARIANTS
] + [
    pytest.param(
        '<c-panel-button size="small">Go</c-panel-button>',
        '<c-button size="small">Go</c-button>',
        id="button-small",
    ),
    pytest.param(
        '<c-panel-button href="/x/">Go</c-panel-button>',
        '<c-button href="/x/">Go</c-button>',
        id="button-href",
    ),
    pytest.param(
        '<c-panel-button loading="true" loading_text="Wait">Go</c-panel-button>',
        '<c-button loading="true" loading_text="Wait">Go</c-button>',
        id="button-loading",
    ),
    pytest.param(
        '<c-panel-button dropdown="true">Go</c-panel-button>',
        '<c-button dropdown="true">Go</c-button>',
        id="button-dropdown",
    ),
    pytest.param(
        '<c-panel-button dropdown="true" tone="error">Go</c-panel-button>',
        '<c-button dropdown="true" tone="error">Go</c-button>',
        id="button-dropdown-error-tone",
    ),
    pytest.param(
        '<c-panel-button icon_left="user" icon_right="next">Go</c-panel-button>',
        '<c-button icon_left="user" icon_right="next">Go</c-button>',
        id="button-icons",
    ),
    pytest.param(
        '<c-panel-button disabled="disabled">Go</c-panel-button>',
        '<c-button disabled="disabled">Go</c-button>',
        id="button-disabled",
    ),
    pytest.param(
        '<c-panel-button hx-post="/x/" class="w-full">Go</c-panel-button>',
        '<c-button hx-post="/x/" class="w-full">Go</c-button>',
        id="button-htmx-attribute",
    ),
    pytest.param(
        '<c-panel-button type="submit" form="f" id="i" name="n" value="v" '
        'autofocus="true" aria_label="L" aria_describedby="d">Go</c-panel-button>',
        '<c-button type="submit" form="f" id="i" name="n" value="v" '
        'autofocus="true" aria_label="L" aria_describedby="d">Go</c-button>',
        id="button-form-and-aria-props",
    ),
    pytest.param(
        '<c-panel-button-group variant="right" class="ms-auto">Go</c-panel-button-group>',
        '<c-button-group variant="right" class="ms-auto">Go</c-button-group>',
        id="button-group-right-with-class",
    ),
]


ITEMS = '<c-panel-button dropdown="true">Edit</c-panel-button>'
ORIGINAL_ITEMS = '<c-button dropdown="true">Edit</c-button>'

DROPDOWN_PAIRS = [
    pytest.param(
        f'<c-panel-dropdown-menu aria_label="More actions" trigger_variant="{variant}" '
        f'trigger_size="small" panel_class="fixed w-64">{ITEMS}</c-panel-dropdown-menu>',
        f'<c-dropdown-menu aria_label="More actions" trigger_class="btn btn-{variant} btn-sm" '
        f'panel_class="fixed w-64">{ORIGINAL_ITEMS}</c-dropdown-menu>',
        id=f"dropdown-menu-{variant}-trigger",
    )
    for variant in ["ghost", "secondary"]
] + [
    pytest.param(
        f"<c-panel-dropdown-menu>{ITEMS}</c-panel-dropdown-menu>",
        f"<c-dropdown-menu>{ORIGINAL_ITEMS}</c-dropdown-menu>",
        id="dropdown-menu-default-trigger",
    ),
    pytest.param(
        f'<c-panel-dropdown-menu trigger_variant="ghost">{ITEMS}</c-panel-dropdown-menu>',
        f'<c-dropdown-menu trigger_class="btn btn-ghost">{ORIGINAL_ITEMS}</c-dropdown-menu>',
        id="dropdown-menu-variant-without-size",
    ),
    pytest.param(
        f'<c-panel-dropdown-menu trigger="Options" menu_label="Sort by" class="ms-2">{ITEMS}</c-panel-dropdown-menu>',
        f'<c-dropdown-menu trigger="Options" menu_label="Sort by" class="ms-2">{ORIGINAL_ITEMS}</c-dropdown-menu>',
        id="dropdown-menu-trigger-prop",
    ),
    pytest.param(
        '<c-panel-dropdown-menu><c-slot name="trigger">More <b>v</b></c-slot>'
        f"{ITEMS}</c-panel-dropdown-menu>",
        '<c-dropdown-menu><c-slot name="trigger">More <b>v</b></c-slot>'
        f"{ORIGINAL_ITEMS}</c-dropdown-menu>",
        id="dropdown-menu-trigger-slot",
    ),
    pytest.param(
        f"<c-panel-dropdown-menu>{ITEMS}<c-panel-dropdown-menu-separator />"
        f"{ITEMS}</c-panel-dropdown-menu>",
        f"<c-dropdown-menu>{ORIGINAL_ITEMS}<c-dropdown-menu-separator />"
        f"{ORIGINAL_ITEMS}</c-dropdown-menu>",
        id="dropdown-menu-separator",
    ),
]


@pytest.mark.parametrize(
    ("wrapper", "original"), [*WRAPPER_PAIRS, *BUTTON_PAIRS, *DROPDOWN_PAIRS]
)
def test_a_wrapper_renders_what_the_component_it_replaces_rendered(
    wrapper: str, original: str
) -> None:
    assert _normalised(wrapper) == _normalised(original)
