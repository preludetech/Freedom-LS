from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_learner_management", "0009_learnerimport_learnerimportrow"),
    ]

    operations = [
        migrations.RenameModel(old_name="OrganisationMember", new_name="StaffMember"),
        migrations.RemoveConstraint(
            model_name="staffmember",
            name="unique_member_per_organisation",
        ),
        migrations.AddConstraint(
            model_name="staffmember",
            constraint=models.UniqueConstraint(
                fields=("site", "user", "organisation"),
                name="unique_staff_member_per_organisation",
            ),
        ),
    ]
