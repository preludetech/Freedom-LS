from __future__ import annotations

from uuid import UUID

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def remove_duplicates(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Keep the oldest row per (site, user, course) and delete the rest.

    Every row so far was made by staff and carries nothing but its timestamp,
    so the extra rows lose no data. The oldest stays so the learner's dashboard
    order, newest first, does not move.
    """
    RecommendedCourse = apps.get_model(
        "freedom_ls_course_recommendations", "RecommendedCourse"
    )
    seen: set[tuple[int, int, UUID]] = set()
    extra: list[UUID] = []
    for pk, site_id, user_id, course_id in (
        RecommendedCourse.objects.order_by("created_at", "id")
        .values_list("id", "site_id", "user_id", "course_id")
        .iterator()
    ):
        key = (site_id, user_id, course_id)
        if key in seen:
            extra.append(pk)
        else:
            seen.add(key)
    RecommendedCourse.objects.filter(id__in=extra).delete()


class Migration(migrations.Migration):
    dependencies = [("freedom_ls_course_recommendations", "0001_initial")]
    operations = [migrations.RunPython(remove_duplicates, migrations.RunPython.noop)]
