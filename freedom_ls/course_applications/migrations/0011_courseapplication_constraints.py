import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('freedom_ls_course_applications', '0010_backfill_application_state'),
        ('freedom_ls_organisations', '0002_organisation_bio_organisation_profile_logo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseapplication',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='course_applications', to='freedom_ls_organisations.organisation'),
        ),
        migrations.RemoveConstraint(
            model_name='courseapplication',
            name='unique_application_per_site_user_course',
        ),
        migrations.AddConstraint(
            model_name='courseapplication',
            constraint=models.UniqueConstraint(condition=models.Q(('state__in', ['draft', 'submitted', 'approved'])), fields=('site', 'user', 'course'), name='unique_active_application_per_site_user_course'),
        ),
        migrations.AddConstraint(
            model_name='courseapplication',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('state__in', ['submitted', 'approved', 'rejected']), _negated=True), ('submitted_at__isnull', False), _connector='OR'), name='courseapp_submitted_at_matches_state'),
        ),
        migrations.AddConstraint(
            model_name='courseapplication',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('decided_at__isnull', False), ('state__in', ['approved', 'rejected'])), models.Q(models.Q(('state__in', ['approved', 'rejected']), _negated=True), ('decided_at__isnull', True)), _connector='OR'), name='courseapp_decided_at_matches_state'),
        ),
        migrations.AddConstraint(
            model_name='courseapplication',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('state__in', ['withdrawn']), ('withdrawn_at__isnull', False)), models.Q(models.Q(('state__in', ['withdrawn']), _negated=True), ('withdrawn_at__isnull', True)), _connector='OR'), name='courseapp_withdrawn_at_matches_state'),
        ),
        migrations.AddConstraint(
            model_name='courseapplication',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('state', 'rejected'), models.Q(('rejection_message', ''), _negated=True)), models.Q(models.Q(('state', 'rejected'), _negated=True), ('rejection_message', '')), _connector='OR'), name='courseapp_rejection_message_matches_state'),
        ),
    ]
