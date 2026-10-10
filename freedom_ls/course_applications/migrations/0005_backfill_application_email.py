from django.conf import settings
from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import OuterRef, Subquery


def backfill_email(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Rows created before the email column existed take their owner's address,
    so every application has an address to display and match against."""
    application = apps.get_model("freedom_ls_course_applications", "CourseApplication")
    user = apps.get_model(settings.AUTH_USER_MODEL)
    owner_email = user.objects.filter(pk=OuterRef("user_id")).values("email")[:1]
    application.objects.filter(email="", user__isnull=False).update(
        email=Subquery(owner_email)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_course_applications", "0004_courseapplication_email_and_user_nullable"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Nothing to undo: the schema migration's reverse drops the column.
        migrations.RunPython(backfill_email, migrations.RunPython.noop),
    ]
