"""Renamed the two unregister bulk actions to their deactivate names.

The rows this rewrote lived in a table the project does not have, so the
migration does nothing now. It stays so the migration history keeps its names.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
