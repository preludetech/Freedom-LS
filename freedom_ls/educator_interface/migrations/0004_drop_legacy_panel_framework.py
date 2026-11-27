"""Dropped the table, migration records and content types of the old
`freedom_ls_panel_framework` app label. Audit log entries that pointed at one
of those content types point at the `panel_framework` one instead."""

from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import StateApps

LEGACY_LABEL = "freedom_ls_panel_framework"
LEGACY_TABLE = "freedom_ls_panel_framework_bulkactionrun"
CURRENT_LABEL = "panel_framework"


def drop_legacy_panel_framework(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Remove the table, migration records and content types of the
    `freedom_ls_panel_framework` label.

    The panel framework's models live in an installed package under the
    `panel_framework` label and table, so nothing references these. An audit
    log entry protects its content type from deletion, so each one moves to
    the same model's content type under the `panel_framework` label first."""
    connection = schema_editor.connection
    if LEGACY_TABLE in connection.introspection.table_names():

        class LegacyBulkActionRun(models.Model):
            class Meta:
                # A private registry keeps the legacy label out of the real one.
                apps = Apps()
                app_label = "legacy_panel_framework_drop"
                db_table = LEGACY_TABLE

        schema_editor.delete_model(LegacyBulkActionRun)
    MigrationRecorder(connection).migration_qs.filter(app=LEGACY_LABEL).delete()
    ContentType = apps.get_model("contenttypes", "ContentType")
    AuditLogEntry = apps.get_model("freedom_ls_audit_log", "AuditLogEntry")
    legacy_types = ContentType.objects.filter(app_label=LEGACY_LABEL)
    for legacy_type in legacy_types:
        entries = AuditLogEntry._base_manager.filter(target_content_type=legacy_type)
        if not entries.exists():
            continue
        current_type, _ = ContentType.objects.get_or_create(
            app_label=CURRENT_LABEL, model=legacy_type.model
        )
        # The base update: the audit log's own queryset refuses `update()`.
        models.QuerySet.update(entries, target_content_type=current_type)
    legacy_types.delete()


class Migration(migrations.Migration):
    # Beyond this app's own chain: the latest migration of every app with a
    # model that points at ContentType, so the delete reaches all their rows.
    dependencies = [
        ("freedom_ls_educator_interface", "0003_move_cohort_bulk_runs"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        (
            "guardian",
            "0003_remove_groupobjectpermission_guardian_gr_content_ae6aec_idx_and_more",
        ),
        ("freedom_ls_audit_log", "0005_rename_member_audit_codes"),
        ("freedom_ls_comms", "0003_notification_rollup_key"),
        (
            "freedom_ls_referral_tracking",
            "0009_drop_attributiontouch_referral_code_index",
        ),
        (
            "freedom_ls_role_based_permissions",
            "0005_alter_objectroleassignment_options",
        ),
        ("freedom_ls_content_engine", "0018_alter_course_options"),
    ]
    operations = [
        migrations.RunPython(drop_legacy_panel_framework, migrations.RunPython.noop),
    ]
