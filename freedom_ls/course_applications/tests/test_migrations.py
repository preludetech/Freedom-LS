"""Data migration for the application email column."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import StateApps

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

APP = "freedom_ls_course_applications"


def _apps_at(target: str) -> StateApps:
    """Migrate this app to `target`; every other app stays at its latest state."""
    MigrationExecutor(connection).migrate([(APP, target)])
    loader = MigrationExecutor(connection).loader
    nodes = [node for node in loader.graph.leaf_nodes() if node[0] != APP]
    return loader.project_state([*nodes, (APP, target)]).apps


@pytest.fixture
def executor() -> Iterator[MigrationExecutor]:
    yield MigrationExecutor(connection)
    final = MigrationExecutor(connection)
    final.migrate(final.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_email_backfilled_from_user_for_existing_rows(executor):
    before = "0004_courseapplication_email_and_user_nullable"
    after = "0005_backfill_application_email"
    old_apps = _apps_at(before)
    site = old_apps.get_model("sites", "Site").objects.create(
        domain="migration.example.com", name="migration"
    )
    user = old_apps.get_model("freedom_ls_accounts", "User").objects.create(
        email="owner@example.com", site=site
    )
    course = old_apps.get_model("freedom_ls_content_engine", "Course").objects.create(
        title="C", slug="c", site=site
    )
    row = old_apps.get_model(APP, "CourseApplication").objects.create(
        user=user, course=course, site=site
    )

    new_apps = _apps_at(after)

    migrated = new_apps.get_model(APP, "CourseApplication").objects.get(pk=row.pk)
    assert migrated.email == "owner@example.com"
