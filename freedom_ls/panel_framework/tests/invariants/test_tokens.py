"""The reference theme defines exactly the colour roles the framework uses.

A role a template or stylesheet uses with no definition renders as no colour in a
host that has not defined it. A role defined and used nowhere is a promise to
hosts the framework does not keep.
"""

from __future__ import annotations

import re
from pathlib import Path

PANEL_FRAMEWORK_DIR = Path(__file__).resolve().parents[2]
REFERENCE_THEME = PANEL_FRAMEWORK_DIR / "css" / "reference_theme.css"
TEMPLATES_DIR = PANEL_FRAMEWORK_DIR / "templates"
STYLESHEETS = (
    PANEL_FRAMEWORK_DIR / "css" / "panel_framework.css",
    PANEL_FRAMEWORK_DIR / "css" / "minimal_shell.css",
)

# A literal list, so a size or style utility such as `text-sm` or `border-2` is
# never read as a role.
ROLE_FAMILIES = (
    "primary",
    "secondary",
    "accent",
    "surface",
    "muted",
    "border",
    "success",
    "warning",
    "error",
    "info",
    "focus-ring",
    "sidepanel",
)
COLOUR_PREFIXES = (
    "bg",
    "text",
    "border",
    "divide",
    "ring",
    "outline",
    "fill",
    "stroke",
)

_FAMILY = "|".join(ROLE_FAMILIES)
_ROLE = rf"(?:on-)?(?:{_FAMILY})(?:-[a-z0-9]+)*"
CLASS_TOKEN = re.compile(
    rf"(?<![\w\[-])(?:[^\s\"'{{}}<>=]+:)*(?:{'|'.join(COLOUR_PREFIXES)})-({_ROLE})"
    r"(?:/[\d.]+|/\[[^\]\s]+\])?(?![\w-])"
)
VAR_REFERENCE = re.compile(r"var\(--color-([a-z0-9-]+)")
DEFINITION = re.compile(r"^\s*--color-([a-z0-9-]+)\s*:", re.MULTILINE)


def _defined_roles() -> set[str]:
    return set(DEFINITION.findall(REFERENCE_THEME.read_text()))


def _used_roles() -> set[str]:
    sources = [*TEMPLATES_DIR.rglob("*.html"), *STYLESHEETS]
    roles: set[str] = set()
    for path in sources:
        text = path.read_text()
        roles.update(CLASS_TOKEN.findall(text))
        roles.update(VAR_REFERENCE.findall(text))
    return roles


def test_every_role_the_framework_uses_is_defined_by_the_reference_theme() -> None:
    assert _used_roles() - _defined_roles() == set()


def test_the_reference_theme_defines_no_role_the_framework_does_not_use() -> None:
    assert _defined_roles() - _used_roles() == set()
