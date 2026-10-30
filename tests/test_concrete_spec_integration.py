"""The shared integration procedure that the concrete-project updater commands follow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.contrib import conformance

REPO_ROOT = Path(__file__).resolve().parents[1]
FLS_DEV = REPO_ROOT / "claude_plugins/fls-dev"
RESOURCE = FLS_DEV / "resources/concrete_spec_integration.md"
RESOURCE_REFERENCE = "resources/concrete_spec_integration.md"


@pytest.mark.parametrize(
    "command",
    [
        "commands/concrete/update_fls.md",
        "commands/update_concrete_projects.md",
    ],
)
def test_updater_command_names_the_shared_resource(command: str) -> None:
    text = (FLS_DEV / command).read_text()

    assert RESOURCE_REFERENCE in text


def test_shared_resource_exists() -> None:
    assert RESOURCE.is_file()


def test_collision_safe_binding_list_matches_conformance_exports() -> None:
    resource_text = RESOURCE.read_text()

    bound = set(re.findall(r"\bconformance\.(test_\w+)", resource_text))

    assert bound == set(conformance.__all__) - {"drop"}
