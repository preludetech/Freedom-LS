from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

RENAMES = {
    "organisation_staff": "organisation_admin",
    "instructor": "cohort_admin",
    "ta": "cohort_viewer",
}


def _rename(apps: Apps, mapping: dict[str, str]) -> None:
    for model_name in ("SiteRoleAssignment", "ObjectRoleAssignment"):
        model = apps.get_model("freedom_ls_role_based_permissions", model_name)
        for old, new in mapping.items():
            model.objects.filter(role=old).update(role=new)


def rename_forward(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _rename(apps, RENAMES)


def rename_backward(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _rename(apps, {new: old for old, new in RENAMES.items()})


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_role_based_permissions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
