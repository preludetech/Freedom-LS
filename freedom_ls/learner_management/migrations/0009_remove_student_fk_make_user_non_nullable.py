"""Remove student FK from CohortMembership, StudentCourseRegistration,
StudentCohortDeadlineOverride and make user FK non-nullable.
Also update constraints."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("freedom_ls_student_management", "0008_populate_user_from_student"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- CohortMembership ---
        migrations.RemoveField(
            model_name="cohortmembership",
            name="student",
        ),
        migrations.AlterField(
            model_name="cohortmembership",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # --- StudentCourseRegistration ---
        # Remove old constraint first
        migrations.RemoveConstraint(
            model_name="studentcourseregistration",
            name="unique_student_course_registration",
        ),
        migrations.RemoveField(
            model_name="studentcourseregistration",
            name="student",
        ),
        migrations.AlterField(
            model_name="studentcourseregistration",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="studentcourseregistration",
            constraint=models.UniqueConstraint(
                fields=["site_id", "collection", "user"],
                name="unique_user_course_registration",
            ),
        ),
        # --- StudentCohortDeadlineOverride ---
        # Remove old constraint first
        migrations.RemoveConstraint(
            model_name="studentcohortdeadlineoverride",
            name="unique_student_cohort_override_per_item",
        ),
        migrations.RemoveField(
            model_name="studentcohortdeadlineoverride",
            name="student",
        ),
        migrations.AlterField(
            model_name="studentcohortdeadlineoverride",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="studentcohortdeadlineoverride",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("content_type__isnull", False), ("object_id__isnull", False)
                ),
                fields=["cohort_course_registration", "user", "content_type", "object_id"],
                name="unique_user_cohort_override_per_item",
            ),
        ),
    ]
