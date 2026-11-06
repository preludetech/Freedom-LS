from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import F

MODELS = ["learnercourseregistration", "cohortcourseregistration"]


def backfill_updated_at(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None
) -> None:
    # Rows that predate the column are stamped with the registration date, so
    # incremental sync sees them in age order rather than all at deploy time.
    for name in MODELS:
        model = apps.get_model("freedom_ls_learner_management", name)
        model._base_manager.update(updated_at=F("registered_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_learner_management", "0009_learnerimport_learnerimportrow")
    ]

    operations = [
        # Nullable first: the column has to exist and be filled before it can
        # refuse NULL.
        *[
            migrations.AddField(
                model_name=name,
                name="updated_at",
                field=models.DateTimeField(null=True),
            )
            for name in MODELS
        ],
        migrations.RunPython(backfill_updated_at, migrations.RunPython.noop),
        *[
            migrations.AlterField(
                model_name=name,
                name="updated_at",
                field=models.DateTimeField(auto_now=True),
            )
            for name in MODELS
        ],
        migrations.AddIndex(
            model_name="learnercourseregistration",
            index=models.Index(
                fields=["site", "updated_at", "id"], name="lm_learner_reg_site_upd_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="cohortcourseregistration",
            index=models.Index(
                fields=["site", "updated_at", "id"], name="lm_cohort_reg_site_upd_idx"
            ),
        ),
    ]
