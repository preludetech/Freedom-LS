"""No FileField or ImageField on a freedom_ls model may resolve to the
default storage alias — each one belongs to a dedicated media alias, and a
field that fell back to `default` would put learner uploads or reports in
the general-purpose bucket instead of the alias meant for them.
"""

from __future__ import annotations

from django.apps import apps
from django.core.files.storage import default_storage, storages
from django.db.models import FileField


def _freedom_ls_file_fields() -> list[tuple[str, FileField]]:
    """Every FileField and ImageField declared on a freedom_ls model."""
    fields: list[tuple[str, FileField]] = []
    for model in apps.get_models():
        if not model._meta.app_config.name.startswith("freedom_ls."):
            continue
        for field in model._meta.get_fields():
            if isinstance(field, FileField):
                label = f"{model._meta.app_label}.{model.__name__}.{field.name}"
                fields.append((label, field))
    return fields


def test_no_file_field_resolves_to_default_storage() -> None:
    fields = _freedom_ls_file_fields()
    resolved = {label: field.storage for label, field in fields}

    assert len(fields) == 3
    assert default_storage not in resolved.values()
    assert storages["default"] not in resolved.values()
