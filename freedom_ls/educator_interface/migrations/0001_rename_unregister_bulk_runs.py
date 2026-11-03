from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

_ACTIONS = "freedom_ls.educator_interface.actions."

# (old action_path, new action_path, new action_name)
RENAMES = [
    (
        f"{_ACTIONS}UnregisterFromCourseBulkAction",
        f"{_ACTIONS}DeactivateRegistrationBulkAction",
        "deactivate_registration",
    ),
    (
        f"{_ACTIONS}UnregisterCohortFromCourseBulkAction",
        f"{_ACTIONS}DeactivateCohortRegistrationBulkAction",
        "deactivate_cohort_registration",
    ),
]


def rename_runs(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """A stored run names its action class by dotted path, so a run recorded
    under a class's old name would fail to load once the class is renamed.
    Point every such run at the renamed class."""
    BulkActionRun = apps.get_model("freedom_ls_panel_framework", "BulkActionRun")
    for old_path, new_path, new_name in RENAMES:
        BulkActionRun.objects.filter(action_path=old_path).update(
            action_path=new_path, action_name=new_name
        )


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_panel_framework", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_runs, migrations.RunPython.noop),
    ]
