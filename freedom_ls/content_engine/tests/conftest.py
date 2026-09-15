"""Fixtures shared by the tests that read the shipped `demo_content/` tree.

The loader is expensive and site-scoped, so it lives here rather than being
repeated per module.
"""

from __future__ import annotations

import pytest

from django.conf import settings

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)


@pytest.fixture
def loaded_demo_content(site, mock_site_context) -> None:
    save_content_to_db(settings.BASE_DIR / "demo_content", site.name)
