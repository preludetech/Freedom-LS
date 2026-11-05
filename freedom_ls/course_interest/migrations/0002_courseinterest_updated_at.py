from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import F


def backfill_updated_at(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None
) -> None:
    # Rows that predate the column are stamped with the interest date, so
    # incremental sync sees them in age order rather than all at deploy time.
    CourseInterest = apps.get_model("freedom_ls_course_interest", "CourseInterest")
    CourseInterest._base_manager.update(updated_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [("freedom_ls_course_interest", "0001_initial")]

    operations = [
        # Nullable first: the column has to exist and be filled before it can
        # refuse NULL.
        migrations.AddField(
            model_name="courseinterest",
            name="updated_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="courseinterest",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name="courseinterest",
            index=models.Index(
                fields=["site", "updated_at", "id"], name="course_interest_site_upd_idx"
            ),
        ),
    ]
