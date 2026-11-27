"""Moved the cohort bulk actions into `panels.cohort.bulk_actions`.

The rows this rewrote lived in a table the project does not have, so the
migration does nothing now. It stays so the migration history keeps its names.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
