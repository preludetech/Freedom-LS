"""Data migration to validate no User has multiple Student records."""

from django.db import migrations


def forward(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id, COUNT(*)
            FROM freedom_ls_student_management_student
            GROUP BY user_id HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            raise Exception(
                f"Duplicate Student records for user_ids: {[r[0] for r in duplicates]}"
            )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("freedom_ls_student_management", "0005_alter_student_cellphone_alter_student_id_number"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
