"""FLS's override of the reference page's base template wins by path and fills
both blocks the page defines, and the reference route is mounted by `config.urls`
only while `settings.DEBUG` is on."""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import pytest_django.fixtures

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, clear_url_caches, reverse

pytestmark = pytest.mark.django_db


def _render() -> str:
    request = RequestFactory().get("/panel-framework/components/")
    return render_to_string(
        "panel_framework/reference/component_reference.html", request=request
    )


def test_the_reference_page_fills_the_title_and_content_blocks(
    mock_site_context: object,
) -> None:
    html = _render()

    title = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    assert title is not None
    assert "Component reference" in title.group(1)
    assert 'id="table-default"' in html


def test_the_reference_page_loads_the_panel_framework_alpine_components(
    mock_site_context: object,
) -> None:
    assert "panel_framework/js/alpine-components.js" in _render()


def _make_staff_user() -> object:
    return get_user_model().objects.create_user(
        email="staff@test.local",
        password="testpass",  # pragma: allowlist secret
        is_staff=True,
    )


class _FakeDebugToolbarModule:
    """Stands in for `debug_toolbar.toolbar` in `sys.modules` (see
    `debug_dev_server_urls` below): only the one name `config.urls` imports
    from it."""

    @staticmethod
    def debug_toolbar_urls() -> list[object]:
        return []


def test_component_reference_does_not_resolve_without_debug(
    settings: pytest_django.fixtures.SettingsWrapper,
) -> None:
    """Under the real `config.urls`, with `DEBUG` off (as pytest forces it for
    the whole session), the reference page's include is absent."""
    settings.ROOT_URLCONF = "config.urls"
    clear_url_caches()
    try:
        with pytest.raises(NoReverseMatch):
            reverse("panel_framework:component_reference")
    finally:
        clear_url_caches()


@contextmanager
def _dev_server_urls(
    settings: pytest_django.fixtures.SettingsWrapper, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Reload `config.urls` under `settings.DEBUG = True`, the dev-server route.

    `debug_toolbar` is only added to `INSTALLED_APPS` outside a pytest run
    (`settings_dev.py`'s `TESTING` guard), so `config.urls`'s real
    `from debug_toolbar.toolbar import debug_toolbar_urls` would otherwise
    chase an import chain that defines a Model with no app to belong to. A
    stand-in module for `debug_toolbar.toolbar` sidesteps that unrelated
    failure without touching the include this fixture exists to exercise.

    `config.urls` is imported here, at fixture-execution time, rather than
    at this module's top level: pytest-django forces `DEBUG` off for the
    whole session (see `settings_dev.py`'s comment on `TESTING`), but only
    once its own session fixture has run, which is after collection. A
    top-level `import config.urls` in this file would run its
    `if settings.DEBUG:` block, and chase the same debug_toolbar import
    chain, during collection instead — before the stand-in below exists.

    Restores `DEBUG`, `ROOT_URLCONF`, the reloaded module and the URL
    resolver cache on teardown, so no other test sees the dev-server route.
    Only the stand-in's own `sys.modules` key is restored: `config.urls` may be
    imported here for the first time, and un-importing the URL modules it pulls
    in would make the next import re-register their DRF routes.
    """
    monkeypatch.setitem(sys.modules, "debug_toolbar.toolbar", _FakeDebugToolbarModule())

    config_urls = importlib.import_module("config.urls")
    original_debug = settings.DEBUG
    original_root_urlconf = settings.ROOT_URLCONF

    def _reload_urls_under(debug: bool) -> None:
        settings.DEBUG = debug
        settings.ROOT_URLCONF = "config.urls"
        importlib.reload(config_urls)
        clear_url_caches()

    _reload_urls_under(True)
    try:
        yield
    finally:
        settings.DEBUG = original_debug
        settings.ROOT_URLCONF = original_root_urlconf
        importlib.reload(config_urls)
        clear_url_caches()


@pytest.fixture
def debug_dev_server_urls(
    settings: pytest_django.fixtures.SettingsWrapper, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Reload `config.urls` under `settings.DEBUG = True`; see `_dev_server_urls`."""
    with _dev_server_urls(settings, monkeypatch):
        yield


def test_dev_server_urls_fixture_keeps_modules_first_imported_inside_it(
    settings: pytest_django.fixtures.SettingsWrapper, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tearing the fixture down used to drop every module first imported
    while it was active, so the API URL modules were re-imported later and
    DRF raised "basename already registered"."""
    monkeypatch.delitem(sys.modules, "config.urls", raising=False)
    monkeypatch.delitem(sys.modules, "freedom_ls.api.urls", raising=False)
    with _dev_server_urls(settings, monkeypatch):
        assert "freedom_ls.api.urls" in sys.modules
    assert "freedom_ls.api.urls" in sys.modules


@pytest.mark.usefixtures("debug_dev_server_urls")
def test_dev_server_route_returns_200_for_staff(
    client: Client, mock_site_context: object
) -> None:
    client.force_login(_make_staff_user())
    response = client.get("/panel-framework/components/")
    assert response.status_code == 200


@pytest.mark.usefixtures("debug_dev_server_urls")
def test_dev_server_route_loads_the_panel_framework_alpine_components(
    client: Client, mock_site_context: object
) -> None:
    """The page loads the panel framework's script. It used to omit it, so the
    inline form's `refocusAfterRequest` component was undefined and Alpine
    logged an error on every load."""
    client.force_login(_make_staff_user())
    response = client.get("/panel-framework/components/")
    assert "panel_framework/js/alpine-components.js" in response.content.decode()


@pytest.mark.usefixtures("debug_dev_server_urls")
def test_dev_server_route_redirects_anonymous_to_admin_login() -> None:
    response = Client().get("/panel-framework/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))
