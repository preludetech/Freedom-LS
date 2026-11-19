"""Render a cotton-tag template string without a request.

Every panel-framework component test renders through this helper rather than
through a view, since the components themselves carry no request-dependent
logic.
"""

from __future__ import annotations

import copy
from pathlib import Path

from django_cotton.compiler_regex import CottonCompiler

from django.conf import settings
from django.template import Context, Template
from django.test import override_settings

FRAMEWORK_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

_compiler = CottonCompiler()


def render_cotton(source: str, **context: object) -> str:
    """Render a template string holding cotton tags, without a request."""
    return Template(_compiler.process(source)).render(Context(context))


def render_framework_default(source: str, **context: object) -> str:
    """Render a cotton string with the framework's own component files winning.

    A host project shadows framework components through the app-directories
    loader. Putting the framework's templates directory first in `DIRS` makes
    the filesystem loader find the framework file before any host file, while
    components the framework does not own, such as `<c-icon>`, still resolve
    through the app directories.
    """
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(FRAMEWORK_TEMPLATES_DIR), *templates[0]["DIRS"]]
    with override_settings(TEMPLATES=templates):
        return render_cotton(source, **context)
