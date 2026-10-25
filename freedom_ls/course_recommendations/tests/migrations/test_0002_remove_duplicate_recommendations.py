"""The data migration that collapses duplicate recommendations before the constraint."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.sites.models import Site
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory

APP = "freedom_ls_course_recommendations"


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_duplicates_collapse_to_the_oldest_row(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    other_course = CourseFactory()
    site = Site.objects.get_current()
    other_site = SiteFactory(domain="other.example.com", name="Other")
    other_user = UserFactory()
    other_site_course = CourseFactory()

    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes(APP)
    executor.migrate([(APP, "0001_initial")])
    old_apps = executor.loader.project_state([(APP, "0001_initial")]).apps
    Historical = old_apps.get_model(APP, "RecommendedCourse")

    def make(site_id: int, user_id: int, course_id: object, age_days: int) -> object:
        row = Historical.objects.create(
            site_id=site_id, user_id=user_id, course_id=course_id
        )
        Historical.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(days=age_days)
        )
        return row.pk

    oldest = make(site.pk, user.pk, course.pk, 3)
    make(site.pk, user.pk, course.pk, 2)
    make(site.pk, user.pk, course.pk, 1)
    other_course_row = make(site.pk, user.pk, other_course.pk, 1)
    other_site_row = make(other_site.pk, other_user.pk, other_site_course.pk, 1)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(leaf)
    new_apps = executor.loader.project_state(leaf).apps
    Current = new_apps.get_model(APP, "RecommendedCourse")

    assert set(Current.objects.values_list("pk", flat=True)) == {
        oldest,
        other_course_row,
        other_site_row,
    }
    with (
        pytest.raises(IntegrityError, match="unique_recommended_course"),
        transaction.atomic(),
    ):
        Current.objects.create(site_id=site.pk, user_id=user.pk, course_id=course.pk)
