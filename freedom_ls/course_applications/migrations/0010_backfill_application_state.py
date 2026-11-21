from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Count, F, OuterRef, Subquery
from django.db.migrations.state import StateApps
from django.utils import timezone


def backfill(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Application = apps.get_model("freedom_ls_course_applications", "CourseApplication")
    FormProgress = apps.get_model("freedom_ls_form_engine", "FormProgress")
    Course = apps.get_model("freedom_ls_content_engine", "Course")
    Organisation = apps.get_model("freedom_ls_organisations", "Organisation")
    Owners = Course._meta.get_field("organisations").remote_field.through
    rows = Application._base_manager.all()
    # state defaults to "draft" from 0009, so an open sitting needs no update.
    rows.filter(form_progress__isnull=True).update(
        state="submitted", submitted_at=F("created_at")
    )
    completed_time = FormProgress._base_manager.filter(
        pk=OuterRef("form_progress_id")
    ).values("completed_time")[:1]
    rows.filter(form_progress__completed_time__isnull=False).update(
        state="submitted", submitted_at=Subquery(completed_time)
    )
    single_owner = (
        Course._base_manager.alias(owners=Count("organisations"))
        .filter(owners=1)
        .values("pk")
    )
    only_owner = Owners.objects.filter(course_id=OuterRef("course_id")).values(
        "organisation_id"
    )[:1]
    rows.filter(course_id__in=single_owner).update(
        organisation_id=Subquery(only_owner)
    )
    for site_id in (
        rows.filter(organisation__isnull=True)
        .order_by()
        .values_list("site_id", flat=True)
        .distinct()
    ):
        default = (
            Organisation._base_manager.filter(site_id=site_id, is_default=True)
            .values_list("pk", flat=True)
            .first()
        )
        if default is None:
            raise RuntimeError(
                f"Site {site_id} has no default organisation; give it one, "
                "then migrate again."
            )
        rows.filter(organisation__isnull=True, site_id=site_id).update(
            organisation_id=default
        )
    # Moved so API clients polling updated_since pick up the new fields.
    rows.update(updated_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ('freedom_ls_content_engine', '0013_course_shared_with'),
        ('freedom_ls_course_applications', '0009_courseapplication_state_and_organisation'),
        ('freedom_ls_form_engine', '0008_alter_formprogress_user'),
        ('freedom_ls_organisations', '0002_organisation_bio_organisation_profile_logo'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
