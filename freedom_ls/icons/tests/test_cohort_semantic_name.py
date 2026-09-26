"""Tests verifying the 'cohort' semantic icon is wired across all icon sets."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.icons.backend import get_icon_backend
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


def test_cohort_is_a_semantic_name() -> None:
    assert "cohort" in SEMANTIC_ICON_NAMES


@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_cohort_is_mapped_in_every_set(set_name: str) -> None:
    config = ICON_SETS[set_name]
    assert "cohort" in config.mapping, (
        f"icon set {set_name!r} is missing a mapping for 'cohort'"
    )


@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_cohort_renders_in_every_set(set_name: str) -> None:
    with override_settings(FREEDOM_LS_ICON_SET=set_name):
        result = get_icon_backend().render("cohort")
    assert "<svg" in result
