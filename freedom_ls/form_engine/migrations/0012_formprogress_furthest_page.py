from __future__ import annotations

import django.db.models.deletion
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

APP = "freedom_ls_form_engine"


def _page_ids_by_form(apps: Apps, sittings: models.QuerySet) -> dict[object, list[object]]:
    """Each form's page ids in authored order, for the forms these sittings sit."""
    FormPage = apps.get_model(APP, "FormPage")
    form_ids = sittings.order_by().values_list("form_id", flat=True).distinct()
    pages: dict[object, list[object]] = {form_id: [] for form_id in form_ids}
    for form_id, page_id in (
        FormPage.objects.filter(form_id__in=pages)
        .order_by("form_id", "order")
        .values_list("form_id", "id")
    ):
        pages[form_id].append(page_id)
    return pages


def number_to_page(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Point each sitting at the page its stored number names today.

    A number past the form's last page names the last page, as resume read it.
    """
    FormProgress = apps.get_model(APP, "FormProgress")
    reached = FormProgress.objects.filter(furthest_page_reached__gt=0)
    for form_id, page_ids in _page_ids_by_form(apps, reached).items():
        for number, page_id in enumerate(page_ids, start=1):
            is_last = number == len(page_ids)
            lookup = "furthest_page_reached__gte" if is_last else "furthest_page_reached"
            reached.filter(form_id=form_id, **{lookup: number}).update(
                furthest_page_id=page_id
            )


def page_to_number(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    FormProgress = apps.get_model(APP, "FormProgress")
    reached = FormProgress.objects.filter(furthest_page__isnull=False)
    for page_ids in _page_ids_by_form(apps, reached).values():
        for number, page_id in enumerate(page_ids, start=1):
            reached.filter(furthest_page_id=page_id).update(
                furthest_page_reached=number
            )


class Migration(migrations.Migration):
    dependencies = [(APP, "0011_shuffle")]

    operations = [
        migrations.AddField(
            model_name="formprogress",
            name="furthest_page",
            field=models.ForeignKey(
                blank=True,
                help_text="The page furthest along this sitting has been shown",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="freedom_ls_form_engine.formpage",
            ),
        ),
        migrations.RunPython(number_to_page, page_to_number),
    ]
