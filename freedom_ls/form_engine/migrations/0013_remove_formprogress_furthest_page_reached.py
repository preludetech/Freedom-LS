from django.db import migrations


class Migration(migrations.Migration):
    # Its own migration: PostgreSQL refuses to drop a column in the transaction
    # that has just written the new foreign key on the same table.
    dependencies = [
        ("freedom_ls_form_engine", "0012_formprogress_furthest_page"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="formprogress",
            name="furthest_page_reached",
        ),
    ]
