"""Test fixtures for panel_framework - no cross-app imports."""

from __future__ import annotations

import itertools

import pytest

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
    """Create stub tables and permissions once per test session."""
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

        # Create ContentType and Permissions so guardian/assign_perm works
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

        yield

        with connection.schema_editor() as editor:
            editor.delete_model(StubGrandchild)
            editor.delete_model(StubChild)
            editor.delete_model(StubModel)
        app_models.pop("stubgrandchild", None)
        app_models.pop("stubmodel", None)
        app_models.pop("stubchild", None)


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
