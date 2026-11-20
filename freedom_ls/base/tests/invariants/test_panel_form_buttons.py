"""A form in a panel puts its submit button in the card footer.

Every panel template under the package is read, and its panel_body block,
with every template it includes, must hold no submit button. The submit goes
in the panel_actions block, which the card renders as its footer, and names
its form with form=.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

PANEL_BASE = "panel_framework/panels/panel.html"

EXTENDS_PANEL = re.compile(r'{%\s*extends\s+"' + re.escape(PANEL_BASE) + r'"\s*%}')
PANEL_BODY = re.compile(
    r"{%\s*block\s+panel_body\s*%}(.*?){%\s*endblock(?:\s+panel_body)?\s*%}",
    re.DOTALL,
)
INCLUDE = re.compile(r'{%\s*include\s+"([^"]+)"')
SUBMIT = re.compile(r'type="submit"')

# A body made of a bar along the card's bottom edge (a message composer) is
# the one place a send button belongs inside the body.
BAR_TEMPLATES = {"comms/partials/composer.html"}


def _panel_templates() -> list[Path]:
    return sorted(
        path
        for path in FREEDOM_LS_PACKAGE_DIR.rglob("templates/**/*.html")
        if "/tests/" not in str(path)
        and EXTENDS_PANEL.search(path.read_text(encoding="utf-8"))
    )


def _template_source(name: str) -> str | None:
    try:
        template = get_template(name)
    except TemplateDoesNotExist:
        return None
    return Path(template.origin.name).read_text(encoding="utf-8")


def _submits_in(source: str, seen: set[str]) -> list[str]:
    found = ["inline"] if SUBMIT.search(source) else []
    for name in INCLUDE.findall(source):
        if name in seen or name in BAR_TEMPLATES:
            continue
        seen.add(name)
        included = _template_source(name)
        if included is not None and _submits_in(included, seen):
            found.append(name)
    return found


def test_the_package_has_panel_templates() -> None:
    assert _panel_templates()


@pytest.mark.parametrize(
    "path",
    _panel_templates(),
    ids=lambda path: str(path.relative_to(FREEDOM_LS_PACKAGE_DIR)),
)
def test_no_panel_body_holds_a_submit_button(path: Path) -> None:
    match = PANEL_BODY.search(path.read_text(encoding="utf-8"))
    if match is None:
        return

    found = _submits_in(match.group(1), set())

    assert found == [], (
        f"{path.name} renders a submit button in its panel body (via {found}); "
        "put it in panel_actions with "
        "panel_framework/partials/inline_record_form_submit.html"
    )
