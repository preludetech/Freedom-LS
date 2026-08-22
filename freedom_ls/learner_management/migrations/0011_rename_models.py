from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_student_management", "0010_delete_student"),
    ]
    operations = [
        migrations.RenameModel(
            old_name="StudentCourseRegistration",
            new_name="UserCourseRegistration",
        ),
        migrations.RenameModel(
            old_name="StudentCohortDeadlineOverride",
            new_name="UserCohortDeadlineOverride",
        ),
    ]
