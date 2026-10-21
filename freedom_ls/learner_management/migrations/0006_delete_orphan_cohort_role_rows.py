from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def delete_orphans(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Role rows whose cohort no longer exists. The content type is looked
    up, not created: on a fresh database it does not exist yet, and there
    is nothing to clean."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    cohort_type = ContentType.objects.filter(
        app_label="freedom_ls_learner_management", model="cohort"
    ).first()
    if cohort_type is None:
        return
    Cohort = apps.get_model("freedom_ls_learner_management", "Cohort")
    existing = {str(pk) for pk in Cohort.objects.values_list("pk", flat=True)}
    ObjectRoleAssignment = apps.get_model(
        "freedom_ls_role_based_permissions", "ObjectRoleAssignment"
    )
    UserObjectPermission = apps.get_model("guardian", "UserObjectPermission")
    ObjectRoleAssignment.objects.filter(content_type=cohort_type).exclude(
        object_id__in=existing
    ).delete()
    UserObjectPermission.objects.filter(content_type=cohort_type).exclude(
        object_pk__in=existing
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("guardian", "0003_remove_groupobjectpermission_guardian_gr_content_ae6aec_idx_and_more"),
        (
            "freedom_ls_role_based_permissions",
            "0003_alter_objectroleassignment_options_and_more",
        ),
        ("freedom_ls_learner_management", "0005_cohort_is_active"),
    ]

    operations = [
        migrations.RunPython(delete_orphans, migrations.RunPython.noop),
    ]
