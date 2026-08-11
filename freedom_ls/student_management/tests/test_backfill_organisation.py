"""Behavioural tests for the organisation backfill callable.

Runs the callable directly against the real app registry rather than through
a migration harness — see freedom_ls/student_management/migration_helpers/
backfill_organisation.py for why that is safe.
"""

from __future__ import annotations

import pytest

from django.apps import apps
from django.contrib.sites.models import Site
from django.db import connection
from django.db.models.signals import post_save
from django.utils.text import slugify

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.signals import ensure_default_organisation
from freedom_ls.site_aware_models.slugs import get_unique_slug
from freedom_ls.student_management.factories import (
    CohortFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.migration_helpers.backfill_organisation import (
    backfill_organisation,
)


@pytest.fixture
def _no_default_organisation_receiver():
    """Disconnect the receiver that gives every new Site an Organisation.

    Without this, every seeded Site would already carry an Organisation, and
    "one Organisation per Site" would pass without the backfill having done
    anything — these tests would assert the receiver, not the migration.
    """
    post_save.disconnect(ensure_default_organisation, sender=Site)
    yield
    post_save.connect(ensure_default_organisation, sender=Site)


@pytest.fixture
def _organisation_fk_nullable():
    """Relax the NOT NULL constraint the final migration in this sequence adds.

    By the time the full suite runs, every migration — including the one that
    makes Cohort.organisation and UserCourseRegistration.organisation
    NOT NULL — is already applied to the test database. These tests need to
    construct the exact "still null" row shape a crash mid-backfill would
    leave, which is otherwise impossible against that schema. Postgres
    supports transactional DDL, so this ALTER is undone automatically when
    the test's transaction rolls back — no explicit restore needed.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE freedom_ls_student_management_cohort "
            "ALTER COLUMN organisation_id DROP NOT NULL"
        )
        cursor.execute(
            "ALTER TABLE freedom_ls_student_management_usercourseregistration "
            "ALTER COLUMN organisation_id DROP NOT NULL"
        )
    return


@pytest.mark.django_db
@pytest.mark.usefixtures("_no_default_organisation_receiver")
class TestBackfillOrganisation:
    def test_creates_one_organisation_named_after_each_site(self):
        site_a = SiteFactory(name="Backfill Site A")
        site_b = SiteFactory(name="Backfill Site B")

        backfill_organisation(apps)

        organisation_a = Organisation.objects.get(site=site_a)
        organisation_b = Organisation.objects.get(site=site_b)
        assert organisation_a.name == "Backfill Site A"
        assert organisation_b.name == "Backfill Site B"

    @pytest.mark.usefixtures("_organisation_fk_nullable")
    def test_points_existing_cohort_at_its_sites_organisation(self):
        site = SiteFactory(name="Backfill Cohort Site")
        cohort = CohortFactory(site=site, organisation=None)

        backfill_organisation(apps)

        cohort.refresh_from_db()
        organisation = Organisation.objects.get(site=site)
        assert cohort.organisation_id == organisation.id

    @pytest.mark.usefixtures("_organisation_fk_nullable")
    def test_points_existing_registration_at_its_sites_organisation(self):
        site = SiteFactory(name="Backfill Registration Site")
        registration = UserCourseRegistrationFactory(
            site=site,
            organisation=None,
            user=UserFactory(site=site),
            collection=CourseFactory(site=site),
        )

        backfill_organisation(apps)

        registration.refresh_from_db()
        organisation = Organisation.objects.get(site=site)
        assert registration.organisation_id == organisation.id

    @pytest.mark.usefixtures("_organisation_fk_nullable")
    def test_does_not_cross_contaminate_between_sites(self):
        site_a = SiteFactory(name="Backfill Isolation Site A")
        site_b = SiteFactory(name="Backfill Isolation Site B")
        cohort_a = CohortFactory(site=site_a, organisation=None)
        cohort_b = CohortFactory(site=site_b, organisation=None)

        backfill_organisation(apps)

        cohort_a.refresh_from_db()
        cohort_b.refresh_from_db()
        organisation_a = Organisation.objects.get(site=site_a)
        organisation_b = Organisation.objects.get(site=site_b)
        assert cohort_a.organisation_id == organisation_a.id
        assert cohort_b.organisation_id == organisation_b.id
        assert organisation_a.id != organisation_b.id

    def test_running_twice_from_a_clean_slate_creates_no_duplicate_organisation(self):
        site = SiteFactory(name="Backfill Idempotence Site")

        backfill_organisation(apps)
        backfill_organisation(apps)

        assert Organisation.objects.filter(site=site).count() == 1

    @pytest.mark.usefixtures("_organisation_fk_nullable")
    def test_resumes_a_partial_apply_without_duplicating_the_organisation(self):
        """The state a crash mid-loop would leave: the Organisation already
        exists and some rows already point at it, others do not yet."""
        site = SiteFactory(name="Backfill Resume Site")
        organisation = OrganisationFactory(
            site=site,
            name=site.name,
            slug=get_unique_slug(Organisation, site, slugify(str(site.name))),
        )
        already_backfilled = CohortFactory(site=site, organisation=organisation)
        still_null = CohortFactory(site=site, organisation=None)

        backfill_organisation(apps)

        assert Organisation.objects.filter(site=site).count() == 1
        already_backfilled.refresh_from_db()
        still_null.refresh_from_db()
        assert already_backfilled.organisation_id == organisation.id
        assert still_null.organisation_id == organisation.id
