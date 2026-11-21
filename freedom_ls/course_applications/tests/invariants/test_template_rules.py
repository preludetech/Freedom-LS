"""Template rules that hold for every application template."""

from __future__ import annotations

import re
from pathlib import Path

import freedom_ls.course_applications as course_applications

TEMPLATES_DIR = Path(course_applications.__file__).resolve().parent / "templates"
# Templates whose anchors keep their own inline styling, each with its reason.
UNCLASSED_ANCHOR_TEMPLATES: dict[str, str] = {
    "course_applications/email/application_claim_message.html": "an email styles its button inline; no stylesheet reaches it",
}
ANCHOR = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.DOTALL)


def _unclassed_anchors(path: Path) -> list[str]:
    return [
        match.group(0)[:80]
        for match in ANCHOR.finditer(path.read_text())
        if "class=" not in match.group(1) and "{{ attrs }}" not in match.group(1)
    ]


def test_no_anchor_falls_back_to_the_prose_underline() -> None:
    """An anchor with no class takes the base layer's underline, which means
    "a link inside a sentence". These templates link a record or an action
    from a table, a card or a line of its own, so each anchor names its style."""
    offenders = {
        path.relative_to(TEMPLATES_DIR).as_posix(): _unclassed_anchors(path)
        for path in sorted(TEMPLATES_DIR.rglob("*.html"))
        if path.relative_to(TEMPLATES_DIR).as_posix() not in UNCLASSED_ANCHOR_TEMPLATES
    }

    assert {name: found for name, found in offenders.items() if found} == {}
