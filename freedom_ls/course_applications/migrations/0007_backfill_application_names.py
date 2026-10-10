from django.conf import settings
from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import OuterRef, Subquery


def backfill_names(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Claimed rows take their owner's names, so the admin can show a name
    without reading the user for every application."""
    application = apps.get_model("freedom_ls_course_applications", "CourseApplication")
    user = apps.get_model(settings.AUTH_USER_MODEL)
    owner = user.objects.filter(pk=OuterRef("user_id"))
    application.objects.filter(user__isnull=False).update(
        first_name=Subquery(owner.values("first_name")[:1]),
        last_name=Subquery(owner.values("last_name")[:1]),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_course_applications", "0006_courseapplication_first_name_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Nothing to undo: the schema migration's reverse drops the columns.
        migrations.RunPython(backfill_names, migrations.RunPython.noop),
    ]
