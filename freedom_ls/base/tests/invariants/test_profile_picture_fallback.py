"""A profile picture that fails to load falls back to the initials under it."""

from __future__ import annotations

from pathlib import Path

import lxml.html
import pytest

from django.test import Client

SCRIPT_PATH = "base/js/profile-picture-fallback.js"
TEMPLATE_PATHS = sorted(Path(__file__).parents[3].rglob("templates/**/*.html"))


@pytest.mark.django_db
def test_a_page_loads_the_fallback_script_in_the_head_without_defer(
    client: Client, mock_site_context: None
) -> None:
    response = client.get("/")

    document = lxml.html.fromstring(response.content)
    scripts = document.cssselect(f"head script[src$='{SCRIPT_PATH}']")
    assert len(scripts) == 1
    assert scripts[0].get("defer") is None
    assert scripts[0].get("async") is None


@pytest.mark.parametrize("template", TEMPLATE_PATHS, ids=lambda path: path.name)
def test_no_template_sets_an_inline_onerror_handler(template: Path) -> None:
    assert "onerror=" not in template.read_text()
