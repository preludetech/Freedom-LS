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


@pytest.mark.parametrize(("wrapper", "original"), WRAPPER_PAIRS)
def test_a_wrapper_renders_what_the_component_it_replaces_rendered(
    wrapper: str, original: str
) -> None:
    assert _normalised(wrapper) == _normalised(original)
