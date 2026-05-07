"""Integration test for the Phase-1 theme template-override codepath.

The Phase-1 resolver (``freedom_ls.base.theming.configure_theme``) prepends the
active theme's ``templates/`` dir to ``TEMPLATES[0]["DIRS"]``. Until Phase 4
no shipped theme had a ``templates/`` folder, so the end-to-end behaviour --
a request for ``cotton/<name>.html`` resolving to a theme override file
rather than the FLS default -- has never actually been exercised against the
real Django template engine.

This module renders a cotton primitive (``<c-loading-indicator>``) under both
"no theme template dir" and "first_class theme template dir prepended" and
asserts the rendered output flips from the FLS default markup to the first_class
override markup. That proves the resolver wiring and Django's template loader
chain cooperate correctly when a theme drops a same-named file under its
``templates/cotton/`` dir.
"""

from __future__ import annotations

from copy import deepcopy

from django_cotton.compiler_regex import CottonCompiler

from django.conf import settings
from django.template import Context, Template
from django.test import override_settings

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

_FIRST_CLASS_TEMPLATES_DIR = (
    FREEDOM_LS_PACKAGE_DIR / "themes" / "first_class" / "templates"
)
_DEFAULT_THEME_TEMPLATES_DIR = (
    FREEDOM_LS_PACKAGE_DIR / "themes" / "default" / "templates"
)

# Default-theme markup marker -- the spinning icon used in the FLS default.
_DEFAULT_MARKER = "animate-spin"
# first_class override markup marker -- introduced by the override file.
_FIRST_CLASS_MARKER = "fls-first-class-loading-indicator"


def _render_loading_indicator() -> str:
    """Compile and render ``<c-loading-indicator>`` against current settings.

    Django's ``override_settings`` fires the ``setting_changed`` signal which
    rebuilds the engines registry, so no manual cache invalidation is needed
    here -- the template engine resolves DIRS afresh on the next access.
    """
    compiler = CottonCompiler()
    processed = compiler.process("<c-loading-indicator />")
    template = Template(processed)
    return template.render(Context())


def _templates_with_dir_prepended(extra_dir: str) -> list[dict]:
    """Return a deep copy of ``TEMPLATES`` with ``extra_dir`` first in DIRS."""
    new_templates = deepcopy(settings.TEMPLATES)
    new_templates[0].setdefault("DIRS", [])
    # Drop any existing entry pointing at a theme templates/ dir so the test
    # is independent of which theme happens to be active in the settings being
    # tested against -- we want a clean baseline.
    filtered = [
        d
        for d in new_templates[0]["DIRS"]
        if str(_FIRST_CLASS_TEMPLATES_DIR) != str(d)
        and str(_DEFAULT_THEME_TEMPLATES_DIR) != str(d)
    ]
    new_templates[0]["DIRS"] = [extra_dir, *filtered]
    return new_templates


def _templates_without_theme_dirs() -> list[dict]:
    """Return a deep copy of ``TEMPLATES`` with theme template dirs stripped."""
    new_templates = deepcopy(settings.TEMPLATES)
    new_templates[0].setdefault("DIRS", [])
    new_templates[0]["DIRS"] = [
        d
        for d in new_templates[0]["DIRS"]
        if str(_FIRST_CLASS_TEMPLATES_DIR) != str(d)
        and str(_DEFAULT_THEME_TEMPLATES_DIR) != str(d)
    ]
    return new_templates


def test_first_class_template_override_files_exist() -> None:
    """The three Phase-4 override files are shipped on disk."""
    cotton_dir = _FIRST_CLASS_TEMPLATES_DIR / "cotton"
    assert (cotton_dir / "header-button.html").is_file()
    assert (cotton_dir / "chip.html").is_file()
    assert (cotton_dir / "loading-indicator.html").is_file()


def test_default_loading_indicator_renders_fls_default_markup() -> None:
    """Without a theme templates dir prepended, the FLS default cotton
    primitive must render -- the spinning icon marker is present and the
    first_class override marker is absent.
    """
    with override_settings(TEMPLATES=_templates_without_theme_dirs()):
        rendered = _render_loading_indicator()

    assert _DEFAULT_MARKER in rendered, (
        f"expected default-theme marker {_DEFAULT_MARKER!r} in: {rendered!r}"
    )
    assert _FIRST_CLASS_MARKER not in rendered


def test_first_class_template_override_picked_up_by_resolver() -> None:
    """With ``first_class/templates/`` prepended to ``TEMPLATES[0]["DIRS"]``,
    the override file must shadow the FLS default. This is the codepath the
    Phase-1 resolver wires up at startup -- exercised end-to-end here for the
    first time now that Phase 4 ships actual theme template overrides.
    """
    new_templates = _templates_with_dir_prepended(str(_FIRST_CLASS_TEMPLATES_DIR))

    with override_settings(TEMPLATES=new_templates):
        rendered = _render_loading_indicator()

    assert _FIRST_CLASS_MARKER in rendered, (
        f"expected override marker {_FIRST_CLASS_MARKER!r} in: {rendered!r}"
    )
    assert _DEFAULT_MARKER not in rendered
