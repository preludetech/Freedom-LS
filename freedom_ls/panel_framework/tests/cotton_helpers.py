"""Render a cotton-tag template string without a request.

Every panel-framework component test renders through this helper rather than
through a view, since the components themselves carry no request-dependent
logic.
"""

from __future__ import annotations

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_compiler = CottonCompiler()


def render_cotton(source: str, **context: object) -> str:
    """Render a template string holding cotton tags, without a request."""
    return Template(_compiler.process(source)).render(Context(context))
