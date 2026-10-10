"""Fixtures that import the shipped `demo_content/` tree once per test module.

Only the `fls_internal` tests of this repo can use them, because `demo_content/`
is not distributed. A package of such tests re-exports them from its
`conftest.py` so the `site` and `_isolate_media_root` overrides stay inside it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_django import DjangoDbBlocker
from pytest_django.fixtures import SettingsWrapper

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import override_settings

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.tests.site_context import site_context


@pytest.fixture(scope="module")
def demo_site(
    django_db_setup: None, django_db_blocker: DjangoDbBlocker
) -> Iterator[Site]:
    """The site the demo tree is imported into, created outside any test transaction.

    Every table is flushed when the module ends, which is the reset every
    transaction=True test already performs. The flush lives here, in the fixture the
    import depends on, so it runs whether or not the import finished.
    """
    with django_db_blocker.unblock():
        site, _ = Site.objects.get_or_create(
            domain="demo.test", defaults={"name": "demo"}
        )
    try:
        yield site
    finally:
        with django_db_blocker.unblock():
            call_command("flush", interactive=False, verbosity=0)


@pytest.fixture(scope="module")
def demo_media_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A media root that outlives the per-test one, so imported images stay readable."""
    return tmp_path_factory.mktemp("demo_media")


@pytest.fixture(scope="module")
def loaded_demo_content(
    demo_site: Site, demo_media_root: Path, django_db_blocker: DjangoDbBlocker
) -> Site:
    """The shipped demo tree, imported once per module.

    The import optimises every image and writes hundreds of rows; importing it
    per test would be the slowest setup in the suite. The rows live outside the
    per-test transaction until `demo_site` flushes them.
    """
    with (
        django_db_blocker.unblock(),
        override_settings(MEDIA_ROOT=demo_media_root),
        site_context(demo_site),
    ):
        save_content_to_db(settings.BASE_DIR / "demo_content", demo_site.name)
    return demo_site


@pytest.fixture
def site(demo_site: Site) -> Site:
    """The module's demo site, so mock_site_context and the view tests agree on it."""
    return demo_site


@pytest.fixture(autouse=True)
def _isolate_media_root(settings: SettingsWrapper, demo_media_root: Path) -> None:
    """Point every test in the package at the module's media root, where the
    imported images are."""
    settings.MEDIA_ROOT = demo_media_root
