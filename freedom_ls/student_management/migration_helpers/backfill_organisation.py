"""Backfill callable for the organisation-FK migration sequence.

Lives in an importable module, separate from the migration file itself, so it
can be unit-tested directly with the real app registry and no migration
harness. The migration file that calls this is a thin RunPython wrapper.
"""

from __future__ import annotations

from django.apps.registry import Apps
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.utils.text import slugify

from freedom_ls.site_aware_models.slugs import get_unique_slug


def backfill_organisation(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None = None
) -> None:
    """Give every Site an Organisation named after it, then point every
    cohort and registration on that Site at it.

    apps.get_model throughout: the real save() reads a thread-local request
    that does not exist during migrate. Iterates the Sites that actually
    exist rather than assuming a particular row is present.
    """
    Site = apps.get_model("sites", "Site")
    Organisation = apps.get_model("freedom_ls_organisations", "Organisation")
    Cohort = apps.get_model("freedom_ls_student_management", "Cohort")
    UserCourseRegistration = apps.get_model(
        "freedom_ls_student_management", "UserCourseRegistration"
    )

    for site in Site.objects.all():
        organisation, _ = Organisation.objects.get_or_create(
            site=site,
            name=site.name,
            defaults={"slug": get_unique_slug(Organisation, site, slugify(site.name))},
        )
        Cohort.objects.filter(site=site, organisation__isnull=True).update(
            organisation=organisation
        )
        UserCourseRegistration.objects.filter(
            site=site, organisation__isnull=True
        ).update(organisation=organisation)
