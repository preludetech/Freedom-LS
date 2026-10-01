"""Tests for the <c-modal /> cotton component."""

import re

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _render(template_string: str) -> str:
    processed = _cotton_compiler.process(template_string)
    return Template(processed).render(Context())


def _root_tag(html: str) -> str:
    match = re.search(r'<div x-data="modal"[^>]*>', html)
    assert match is not None, f"No modal root in:\n{html}"
    return match.group(0)


class TestModalComponent:
    def test_extra_attributes_land_on_the_modal_root(self) -> None:
        result = _render('<c-modal title="Hello" data-marker="yes">Body</c-modal>')

        assert 'data-marker="yes"' in _root_tag(result)
