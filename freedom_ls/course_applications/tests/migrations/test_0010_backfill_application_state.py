"""The data migration that gives existing applications a state and an organisation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import StateApps
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.factories import SiteFactory

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

APP = "freedom_ls_course_applications"
BEFORE = (APP, "0008_courseapplication_courseapp_site_updated_idx")
BACKFILL = (APP, "0010_backfill_application_state")

# transaction=True: the tests migrate the schema backwards and forwards.
pytestmark = pytest.mark.django_db(transaction=True)


def _rows_through_the_backfill(
    seed: Callable[[StateApps], object],
    repair: Callable[[], object] = lambda: None,
) -> StateApps:
    """Migrate back to before the state fields, run `seed` on the historical
    models, migrate forward through the backfill and return the state there.

    The rows are re-read from the returned apps by primary key. `repair` runs
    before the schema is brought back to the leaf, for a test whose data makes
    the backfill fail and would otherwise leave the schema behind.
    """
    executor = MigrationExecutor(connection)
    # Every app's leaf: migrating back also unapplies apps that depend on this one.
    leaf = executor.loader.graph.leaf_nodes()
    executor.migrate([BEFORE])
    seed(executor.loader.project_state([BEFORE]).apps)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    try:
        executor.migrate([BACKFILL])
        return executor.loader.project_state([BACKFILL]).apps
    finally:
        repair()
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(leaf)


def _seed_application(
    apps: StateApps,
    *,
    course: Course,
    site: Site,
    user_id: int | None = None,
    form_progress_id: object | None = None,
    created_at: datetime | None = None,
) -> object:
    Application = apps.get_model(APP, "CourseApplication")
    row = Application.objects.create(
        site_id=site.pk,
        course_id=course.pk,
        user_id=user_id,
        form_progress_id=form_progress_id,
    )
    if created_at is not None:
        Application.objects.filter(pk=row.pk).update(created_at=created_at)
    return row.pk


def _row_after(apps: StateApps, pk: object) -> object:
    return apps.get_model(APP, "CourseApplication").objects.get(pk=pk)


def test_an_application_with_no_sitting_becomes_submitted_when_it_was_created(
    mock_site_context: Site,
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    created = timezone.now() - timedelta(days=5)
    seeded: list[object] = []

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(
            _seed_application(apps, course=course, site=site, created_at=created)
        )
    )

    row = _row_after(apps, seeded[0])
    assert row.state == "submitted"
    assert row.submitted_at == created


def test_an_application_with_a_completed_sitting_becomes_submitted_when_it_completed(
    mock_site_context: Site,
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    completed = timezone.now() - timedelta(days=2)
    sitting = FormProgressFactory(form=FormFactory(), completed_time=completed)
    seeded: list[object] = []

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(
            _seed_application(
                apps, course=course, site=site, form_progress_id=sitting.pk
            )
        )
    )

    row = _row_after(apps, seeded[0])
    assert row.state == "submitted"
    assert row.submitted_at == completed


@pytest.mark.parametrize("with_user", [True, False], ids=["claimed", "unclaimed"])
def test_an_application_with_an_open_sitting_stays_a_draft(
    mock_site_context: Site, with_user: bool
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    user = UserFactory() if with_user else None
    sitting = FormProgressFactory(form=FormFactory(), user=user, completed_time=None)
    seeded: list[object] = []

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(
            _seed_application(
                apps,
                course=course,
                site=site,
                user_id=user.pk if user else None,
                form_progress_id=sitting.pk,
            )
        )
    )

    row = _row_after(apps, seeded[0])
    assert row.state == "draft"
    assert row.submitted_at is None


@pytest.mark.parametrize("with_user", [True, False], ids=["claimed", "unclaimed"])
def test_an_application_with_no_sitting_is_submitted_whoever_holds_it(
    mock_site_context: Site, with_user: bool
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    user = UserFactory() if with_user else None
    seeded: list[object] = []

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(
            _seed_application(
                apps, course=course, site=site, user_id=user.pk if user else None
            )
        )
    )

    assert _row_after(apps, seeded[0]).state == "submitted"


def test_a_course_with_one_owning_organisation_gives_it_to_the_application(
    mock_site_context: Site,
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    owner = OrganisationFactory()
    course.organisations.add(owner)
    seeded: list[object] = []

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(_seed_application(apps, course=course, site=site))
    )

    assert _row_after(apps, seeded[0]).organisation_id == owner.pk


@pytest.mark.parametrize("owner_count", [0, 2])
def test_a_course_without_exactly_one_owner_gives_the_application_its_sites_default(
    mock_site_context: Site, owner_count: int
) -> None:
    site = Site.objects.get_current()
    other_site = SiteFactory(domain="other.example.com", name="Other")
    course = CourseFactory()
    course.organisations.add(*[OrganisationFactory() for _ in range(owner_count)])
    other_course = Course._base_manager.get(pk=CourseFactory().pk)
    other_course.site = other_site
    other_course.save(update_fields=["site"])
    seeded: list[object] = []

    def seed(apps: StateApps) -> None:
        seeded.append(_seed_application(apps, course=course, site=site))
        seeded.append(_seed_application(apps, course=other_course, site=other_site))

    apps = _rows_through_the_backfill(seed)

    assert _row_after(apps, seeded[0]).organisation_id == get_default_organisation(
        site
    ).pk
    assert _row_after(apps, seeded[1]).organisation_id == get_default_organisation(
        other_site
    ).pk


def test_updated_at_moves_on_every_row(mock_site_context: Site) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    seeded: list[object] = []
    started = timezone.now()

    apps = _rows_through_the_backfill(
        lambda apps: seeded.append(_seed_application(apps, course=course, site=site))
    )

    assert _row_after(apps, seeded[0]).updated_at >= started


def test_a_site_without_a_default_organisation_stops_the_migration(
    mock_site_context: Site,
) -> None:
    site = Site.objects.get_current()
    course = CourseFactory()
    Organisation._base_manager.filter(site=site, is_default=True).delete()

    with pytest.raises(RuntimeError, match=f"Site {site.pk} has no default"):
        _rows_through_the_backfill(
            lambda apps: _seed_application(apps, course=course, site=site),
            repair=lambda: Organisation._base_manager.create(
                site=site, name="Default", slug="default", is_default=True
            ),
        )
