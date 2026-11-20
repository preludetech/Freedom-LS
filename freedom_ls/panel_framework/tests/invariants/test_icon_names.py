"""REQUIRED_ICON_NAMES lists every icon name the framework's templates draw."""

from __future__ import annotations

import re
from pathlib import Path

from freedom_ls.panel_framework.checks import REQUIRED_ICON_NAMES

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
ICON_BODIES_DIR = TEMPLATES_DIR / "panel_framework" / "icons"
STATIC_ICON = re.compile(r'<c-panel-icon\s+name="([a-z_]+)"')
BUTTON_ICON = re.compile(r'icon_(?:left|right)="([a-z_]+)"')
# Drawn by primitives from a value the caller passes (a button's loading
# spinner, pagination's arrows, a callout's status icon), so no template
# spells them as a literal icon name.
PRIMITIVE_DRAWN_NAMES = {
    "loading",
    "previous",
    "next",
    "more_options",
    "info",
    "warning",
    "error",
    "success",
}
# Names a template picks at render time inside an `{% if %}`, so no template
# spells them as a literal `c-panel-icon name=` (a details row of kind boolean).
RENDER_TIME_NAMES = {
    "boolean_true",
    "boolean_false",
}


def _names_in_templates() -> set[str]:
    names: set[str] = set()
    for path in TEMPLATES_DIR.rglob("*.html"):
        text = path.read_text()
        names.update(STATIC_ICON.findall(text))
        for line in text.splitlines():
            if "<c-panel-button" in line:
                names.update(BUTTON_ICON.findall(line))
    return names


def test_required_icon_names_equal_the_names_the_templates_draw() -> None:
    derived = _names_in_templates() | PRIMITIVE_DRAWN_NAMES | RENDER_TIME_NAMES

    assert derived ^ REQUIRED_ICON_NAMES == set()


def test_the_framework_ships_one_icon_body_per_required_name() -> None:
    shipped = {path.stem for path in ICON_BODIES_DIR.glob("*.html")}

    assert shipped ^ REQUIRED_ICON_NAMES == set()


def test_no_framework_template_draws_an_icon_through_a_host_component() -> None:
    offenders = [
        path.relative_to(TEMPLATES_DIR).as_posix()
        for path in TEMPLATES_DIR.rglob("*.html")
        if "<c-icon" in path.read_text()
    ]

    assert offenders == []
