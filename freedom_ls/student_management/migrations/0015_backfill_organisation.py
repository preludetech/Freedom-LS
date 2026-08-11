"""Data migration: give every Site an Organisation, and point existing
cohorts and registrations at it.

The callable lives in migration_helpers.backfill_organisation so it can be
unit-tested directly, outside a migration harness. This file is a thin
wrapper around it.
"""

from django.db import migrations

from freedom_ls.student_management.migration_helpers.backfill_organisation import (
    backfill_organisation,
)


class Migration(migrations.Migration):

    dependencies = [
        ("freedom_ls_student_management", "0014_cohort_organisation_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_organisation, migrations.RunPython.noop),
    ]
