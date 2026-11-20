import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('freedom_ls_content_engine', '0013_course_shared_with'),
        ('freedom_ls_course_applications', '0008_courseapplication_courseapp_site_updated_idx'),
        ('freedom_ls_organisations', '0002_organisation_bio_organisation_profile_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseapplication',
            name='state',
            field=models.CharField(choices=[('draft', 'Not submitted'), ('submitted', 'Waiting for review'), ('approved', 'Approved'), ('rejected', 'Not approved'), ('withdrawn', 'Withdrawn')], default='draft', max_length=20),
        ),
        migrations.AddField(
            model_name='courseapplication',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courseapplication',
            name='decided_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courseapplication',
            name='withdrawn_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courseapplication',
            name='rejection_message',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='courseapplication',
            name='organisation',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='course_applications', to='freedom_ls_organisations.organisation'),
        ),
    ]
