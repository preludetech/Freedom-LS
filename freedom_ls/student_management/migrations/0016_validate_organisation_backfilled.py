"""Data migration: verify the previous migration left no Cohort or
UserCourseRegistration row without an organisation before the next migration
makes the column NOT NULL.

Turns a bare "null value in column ... violates not-null constraint",
several steps later and with no context, into a message that says what
happened and what to do.
"""

from django.db import migrations


def validate_organisation_backfilled(apps, schema_editor) -> None:
    Cohort = apps.get_model("freedom_ls_student_management", "Cohort")
    Registration = apps.get_model(
        "freedom_ls_student_management", "UserCourseRegistration"
    )

    cohort_count = Cohort.objects.filter(organisation__isnull=True).count()
    if cohort_count:
        raise RuntimeError(
            f"{cohort_count} Cohort row(s) still have no organisation after the "
            "backfill migration. This means a Site existed without a default "
            "Organisation at backfill time, or a Cohort was created between the "
            "backfill and this check. Do not proceed: investigate before "
            "re-running `migrate`."
        )

    registration_count = Registration.objects.filter(organisation__isnull=True).count()
    if registration_count:
        raise RuntimeError(
            f"{registration_count} UserCourseRegistration row(s) still have no "
            "organisation after the backfill migration. This means a Site existed "
            "without a default Organisation at backfill time, or a registration "
            "was created between the backfill and this check. Do not proceed: "
            "investigate before re-running `migrate`."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("freedom_ls_student_management", "0015_backfill_organisation"),
    ]

    operations = [
        migrations.RunPython(
            validate_organisation_backfilled, migrations.RunPython.noop
        ),
    ]
