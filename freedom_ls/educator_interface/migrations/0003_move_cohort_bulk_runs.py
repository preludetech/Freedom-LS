from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

_OLD = "freedom_ls.educator_interface.actions."
_NEW = "freedom_ls.educator_interface.panels.cohort.bulk_actions."

# (old action_path, new action_path) for every @register_bulk_action cohort class;
# the undecorated bases are never stored.
MOVES = [
    (f"{_OLD}{name}", f"{_NEW}{name}")
    for name in [
        "RegisterCohortForCourseBulkAction",
        "DeactivateCohortRegistrationBulkAction",
        "DeactivateCohortsBulkAction",
        "ReactivateCohortsBulkAction",
    ]
]


def _repoint(apps: Apps, pairs: list[tuple[str, str]]) -> None:
    """A stored run names its action class by dotted path and is loaded with
    import_string, so each run must name the module that defines its class.
    Every site's runs are repointed: the historical model's manager has no
    site filter, and a run left on the old path on any site would fail to load.
    Matches whole paths only, so other classes under the same prefix stay."""
    BulkActionRun = apps.get_model("freedom_ls_panel_framework", "BulkActionRun")
    for old_path, new_path in pairs:
        BulkActionRun.objects.filter(action_path=old_path).update(action_path=new_path)


def forwards(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _repoint(apps, MOVES)


def backwards(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    _repoint(apps, [(new, old) for old, new in MOVES])


class Migration(migrations.Migration):
    dependencies = [("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")]
    operations = [migrations.RunPython(forwards, backwards)]
