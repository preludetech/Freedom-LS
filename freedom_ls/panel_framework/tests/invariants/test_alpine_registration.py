"""Every Alpine component a framework template names is registered by a
framework script (or, for the few it shares with its host, by the host)."""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PACKAGE_DIR / "templates"
SCRIPTS = (
    PACKAGE_DIR / "static" / "panel_framework" / "js" / "alpine-components.js",
    PACKAGE_DIR / "static" / "panel_framework" / "js" / "shell-components.js",
)

# Components the host project registers and framework templates use. The
# framework does not ship them, so the host has to supply them.
HOST_SUPPLIED_COMPONENTS: frozenset[str] = frozenset()

X_DATA_NAME = re.compile(r"""x-data=["']([A-Za-z_][\w$]*)["']""")
REGISTRATION = re.compile(r"""Alpine\.data\(\s*["']([\w$]+)["']""")


def test_every_component_a_framework_template_names_is_registered() -> None:
    registered = {
        name for script in SCRIPTS for name in REGISTRATION.findall(script.read_text())
    }
    unregistered = [
        f"{template.relative_to(TEMPLATES_DIR)}: {name}"
        for template in sorted(TEMPLATES_DIR.rglob("*.html"))
        for name in X_DATA_NAME.findall(template.read_text())
        if name not in registered and name not in HOST_SUPPLIED_COMPONENTS
    ]

    assert not unregistered, (
        "x-data names no framework script registers with Alpine.data(): "
        + "; ".join(unregistered)
    )
