"""A cotton component name belongs to one app, unless it is a framework primitive a host overrides."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from django.apps import apps

FRAMEWORK_LABEL = "freedom_ls_panel_framework"


def _component_owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    for config in apps.get_app_configs():
        cotton_dir = Path(config.path) / "templates" / "cotton"
        for template in cotton_dir.rglob("*.html"):
            owners[template.relative_to(cotton_dir).as_posix()].add(config.label)
    return owners


def test_no_component_name_is_owned_by_two_apps_unless_it_overrides_a_framework_primitive() -> (
    None
):
    owners = _component_owners()

    offending = {
        name
        for name, labels in owners.items()
        if len(labels) > 1
        and not (name.startswith("panel-") and FRAMEWORK_LABEL in labels)
    }

    assert offending == set()
