"""Tests for the migration that adds updated_at to course interest."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from django.apps import apps as django_apps
from django.contrib.sites.models import Site
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Model

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest

migration = importlib.import_module(
    "freedom_ls.course_interest.migrations.0002_courseinterest_updated_at"
)

APP_LABEL = "freedom_ls_course_interest"
BEFORE = [(APP_LABEL, "0001_initial")]
AFTER = [(APP_LABEL, "0002_courseinterest_updated_at")]


@pytest.mark.django_db
def test_backfill_sets_updated_at_to_created_at(mock_site_context: Site) -> None:
    interest = CourseInterestFactory()
    CourseInterest._base_manager.filter(pk=interest.pk).update(
        updated_at=datetime(2031, 1, 1, tzinfo=UTC)
    )

    migration.backfill_updated_at(django_apps, None)

    stored = CourseInterest._base_manager.get(pk=interest.pk)
    assert stored.updated_at == stored.created_at


@pytest.fixture
def before_updated_at() -> Iterator[type[Model]]:
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    yield executor.loader.project_state(BEFORE).apps.get_model(
        APP_LABEL, "CourseInterest"
    )
    MigrationExecutor(connection).migrate(AFTER)


# The executor rewrites the schema, which a transaction-wrapped test cannot roll back.
@pytest.mark.django_db(transaction=True)
def test_the_migration_backfills_rows_that_predate_it(
    before_updated_at: type[Model], mock_site_context: Site
) -> None:
    row = before_updated_at._base_manager.create(
        site_id=mock_site_context.pk,
        user_id=UserFactory().pk,
        course_id=CourseFactory().pk,
    )

    MigrationExecutor(connection).migrate(AFTER)

    stored = CourseInterest._base_manager.get(pk=row.pk)
    assert stored.updated_at == stored.created_at
