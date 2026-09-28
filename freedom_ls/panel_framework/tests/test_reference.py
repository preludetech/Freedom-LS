"""The component reference page: staff-only, every component, no query cost.

`component_reference` is a plain `staff_member_required` view, so most tests
run against the isolated test URLconf at `/test-panel/components/`
(`tests/urls.py`, `tests/root_urls.py`). One test exercises the real
`config.urls` include under `settings.DEBUG`, since that is the route a
developer actually uses.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator

import pytest
import pytest_django.fixtures
from pytest_mock import MockerFixture

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client
from django.urls import NoReverseMatch, clear_url_caches, reverse

from ..reference import EXAMPLE_CONTEXT
from .conftest import make_staff_user

# One id prefix per component family the reference page documents, matching
# the section headings in _examples.html. `attention-list` and
# `attention-row` are separate names: both `panel-attention-list` and
# `panel-attention-row` are public components with their own example ids.
COMPONENT_NAMES = [
    "page-header",
    "stat-tile",
    "stat-row",
    "status-badge",
    "avatar-chip",
    "attention-list",
    "attention-row",
    "progress-bar",
    "card",
    "definition-list",
    "definition-row",
    "toolbar",
    "search-field",
    "filter-toggle",
    "applied-filter",
    "empty-state",
    "skeleton",
    "callout",
]


class _FakeDebugToolbarModule:
    """Stands in for `debug_toolbar.toolbar` in `sys.modules` (see
    `debug_dev_server_urls` below): only the one name `config.urls` imports
    from it."""

    @staticmethod
    def debug_toolbar_urls() -> list[object]:
        return []


def test_examples_partial_renders_with_no_queries(django_assert_num_queries) -> None:
    with django_assert_num_queries(0):
        render_to_string("panel_framework/reference/_examples.html", EXAMPLE_CONTEXT)


def test_anonymous_user_is_redirected_to_admin_login(client: Client) -> None:
    response = client.get("/test-panel/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


def test_non_staff_user_is_redirected_to_admin_login(
    client: Client, mock_site_context: object
) -> None:
    user = get_user_model().objects.create_user(
        email="learner@test.local",
        password="testpass",  # pragma: allowlist secret
        is_staff=False,
    )
    client.force_login(user)
    response = client.get("/test-panel/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


def test_staff_user_gets_200(client: Client, mock_site_context: object) -> None:
    client.force_login(make_staff_user())
    response = client.get("/test-panel/components/")
    assert response.status_code == 200


@pytest.mark.parametrize("component_name", COMPONENT_NAMES)
def test_every_component_has_at_least_one_example_id(
    client: Client, mock_site_context: object, component_name: str
) -> None:
    client.force_login(make_staff_user())
    response = client.get("/test-panel/components/")
    assert f'id="{component_name}-' in response.content.decode()


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


@pytest.fixture
def debug_dev_server_urls(
    settings: pytest_django.fixtures.SettingsWrapper, mocker: MockerFixture
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
    """
    mocker.patch.dict(sys.modules, {"debug_toolbar.toolbar": _FakeDebugToolbarModule()})

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


@pytest.mark.usefixtures("debug_dev_server_urls")
def test_dev_server_route_returns_200_for_staff(
    client: Client, mock_site_context: object
) -> None:
    client.force_login(make_staff_user())
    response = client.get("/panel-framework/components/")
    assert response.status_code == 200


@pytest.mark.usefixtures("debug_dev_server_urls")
def test_dev_server_route_redirects_anonymous_to_admin_login() -> None:
    response = Client().get("/panel-framework/components/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))
