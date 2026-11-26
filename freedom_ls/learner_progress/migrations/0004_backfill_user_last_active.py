from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, OuterRef, Subquery
from django.db.models.functions import Greatest


def backfill_last_active(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor | None
) -> None:
    User = apps.get_model("freedom_ls_accounts", "User")
    CourseProgress = apps.get_model("freedom_ls_learner_progress", "CourseProgress")
    latest_course_activity = (
        CourseProgress._base_manager.filter(learner__user=OuterRef("pk"))
        .order_by()
        .values("learner__user")
        .annotate(latest=Max("last_accessed_time"))
        .values("latest")
    )
    # PostgreSQL's GREATEST skips nulls, so one null side gives the other.
    User._base_manager.update(
        last_active=Greatest("last_login", Subquery(latest_course_activity))
    )


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_learner_progress", "0003_courseprogress_updated_at"),
        ("freedom_ls_accounts", "0006_user_last_active"),
    ]

    operations = [
        migrations.RunPython(backfill_last_active, migrations.RunPython.noop),
    ]
