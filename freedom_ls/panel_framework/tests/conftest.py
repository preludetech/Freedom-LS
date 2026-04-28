"""Test fixtures for panel_framework - no cross-app imports."""

from __future__ import annotations

import itertools

import pytest
import pytest_django.fixtures

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models

# ---------------------------------------------------------------------------
# Lightweight test-only models
# ---------------------------------------------------------------------------


class StubModel(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return self.name


class StubChild(models.Model):
    parent = models.ForeignKey(StubModel, on_delete=models.CASCADE)

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return f"StubChild({self.pk})"


class StubGrandchild(models.Model):
    """Exists so Django's Collector puts StubChild in data (not fast_deletes)."""

    parent = models.ForeignKey(StubChild, on_delete=models.CASCADE)

    class Meta:
        app_label = "freedom_ls_panel_framework"

    def __str__(self) -> str:
        return f"StubGrandchild({self.pk})"


# ---------------------------------------------------------------------------
# Session-scoped table creation + permission setup
# ---------------------------------------------------------------------------

_counter = itertools.count(1)


@pytest.fixture(autouse=True, scope="session")
def _panel_test_tables(django_db_setup, django_db_blocker):
    """Create stub tables once per test session."""
    with django_db_blocker.unblock():
        # Register models in the app registry so Django's Collector can find them
        app_models = apps.all_models.get("freedom_ls_panel_framework", {})
        app_models["stubmodel"] = StubModel
        app_models["stubchild"] = StubChild
        app_models["stubgrandchild"] = StubGrandchild

        with connection.schema_editor() as editor:
            editor.create_model(StubModel)
            editor.create_model(StubChild)
            editor.create_model(StubGrandchild)

        yield

        with connection.schema_editor() as editor:
            editor.delete_model(StubGrandchild)
            editor.delete_model(StubChild)
            editor.delete_model(StubModel)
        app_models.pop("stubgrandchild", None)
        app_models.pop("stubmodel", None)
        app_models.pop("stubchild", None)


@pytest.fixture(autouse=True)
def _panel_test_permissions(db):
    """Ensure stub-model ContentType and Permissions exist before every test.

    Function-scoped because tests using ``@pytest.mark.django_db(transaction=True)``
    elsewhere in the suite flush the DB between tests, wiping any session-scoped
    setup. The ContentType in-memory cache must also be cleared so that
    ``get_for_model(StubModel)`` does not return a stale PK from a prior
    rolled-back transaction. Idempotent via ``get_or_create``.
    """
    # Clear the ContentType cache before the lookup so any stale PKs from
    # earlier rolled-back transactions are dropped.
    ContentType.objects.clear_cache()
    ct, _ = ContentType.objects.get_or_create(
        app_label="freedom_ls_panel_framework",
        model="stubmodel",
    )
    for codename in ("add_stubmodel", "change_stubmodel", "delete_stubmodel"):
        Permission.objects.get_or_create(
            content_type=ct,
            codename=codename,
            defaults={"name": f"Can {codename.split('_')[0]} stub model"},
        )


# ---------------------------------------------------------------------------
# Fixture: use panel_framework's own test URLs
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_panel_test_urls(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Point Django URL resolution at panel_framework's own test URLs.

    Applied autouse so every test in panel_framework/tests/ uses the isolated
    test URL config. The panel_framework app must not depend on any consumer
    app's URLs, so tests in this directory must only reverse URLs that live in
    `root_urls.py`.
    """
    settings.ROOT_URLCONF = "freedom_ls.panel_framework.tests.root_urls"


# ---------------------------------------------------------------------------
# Helper: staff user without importing UserFactory
# ---------------------------------------------------------------------------


def make_staff_user() -> object:
    """Create a staff user with a unique email. Requires mock_site_context active."""
    User = get_user_model()
    n = next(_counter)
    return User.objects.create_user(
        email=f"staff{n}@test.local",
        password="testpass",  # pragma: allowlist secret
        is_staff=True,
    )
