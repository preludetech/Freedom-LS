from django.db import migrations

RENAMES = {
    "member.deactivated": "staff_member.deactivated",
    "member.reactivated": "staff_member.reactivated",
}


def _rename(apps, renames: dict[str, str]) -> None:
    AuditLogEntry = apps.get_model("freedom_ls_audit_log", "AuditLogEntry")
    for old, new in renames.items():
        AuditLogEntry.objects.filter(action=old).update(action=new)


def forwards(apps, schema_editor) -> None:
    _rename(apps, RENAMES)


def backwards(apps, schema_editor) -> None:
    _rename(apps, {new: old for old, new in RENAMES.items()})


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_audit_log", "0004_actor_index_and_delete_handler"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
