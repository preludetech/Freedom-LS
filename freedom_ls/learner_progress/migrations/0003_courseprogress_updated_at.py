from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models.functions import Greatest


def backfill_updated_at(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor | None
) -> None:
    # The latest thing known to have happened to the row. GREATEST skips nulls
    # on PostgreSQL and created_at is never null, so every row gets a value.
    CourseProgress = apps.get_model("freedom_ls_learner_progress", "CourseProgress")
    CourseProgress._base_manager.update(
        updated_at=Greatest(
            "created_at", "started_at", "last_accessed_time", "completed_time"
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        (
            "freedom_ls_learner_progress",
            "0002_course_progress_cohort_constraint_deferrable",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="courseprogress",
            name="updated_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="courseprogress",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name="courseprogress",
            index=models.Index(
                fields=["site", "updated_at", "id"], name="lp_progress_site_upd_idx"
            ),
        ),
    ]
