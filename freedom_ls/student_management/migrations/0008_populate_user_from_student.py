"""Data migration to populate user_id from student.user_id on affected models."""

from django.db import migrations


def forward(apps, schema_editor):
    for table in [
        "freedom_ls_student_management_cohortmembership",
        "freedom_ls_student_management_studentcourseregistration",
        "freedom_ls_student_management_studentcohortdeadlineoverride",
    ]:
        schema_editor.execute(f"""
            UPDATE {table} SET user_id = s.user_id
            FROM freedom_ls_student_management_student AS s
            WHERE {table}.student_id = s.id
        """)  # nosec B608 - table names are hardcoded, not user input


def reverse(apps, schema_editor):
    for table in [
        "freedom_ls_student_management_cohortmembership",
        "freedom_ls_student_management_studentcourseregistration",
        "freedom_ls_student_management_studentcohortdeadlineoverride",
    ]:
        schema_editor.execute(f"""
            UPDATE {table} SET user_id = NULL
        """)  # nosec B608 - table names are hardcoded, not user input


class Migration(migrations.Migration):

    dependencies = [
        ("freedom_ls_student_management", "0007_cohortmembership_user_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
