"""Guardrail: every FLS app label carries the `freedom_ls_` prefix.

The prefix is what keeps FLS's tables (and its system-check ids) distinct
from a downstream project's own apps. This probe opens no database
connection; it only reads the populated app registry.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from django.apps import AppConfig, apps
from django.conf import settings

import freedom_ls

pytestmark = pytest.mark.fls_internal

# icons: stays bare "icons". It is on its way to becoming the standalone
# django_semantic_iconify package, so prefixing it now would mean renaming
# it a second time on extraction.
UNPREFIXED_LABEL_ALLOWLIST = frozenset({"icons"})


def _offending_apps(
    app_configs: Iterable[AppConfig], allowlist: frozenset[str]
) -> list[AppConfig]:
    """FLS apps whose label is neither prefixed nor allowlisted."""
    offenders = []
    for config in app_configs:
        if not config.name.startswith("freedom_ls."):
            continue
        if config.label.startswith("freedom_ls_"):
            continue
        if config.name.rpartition(".")[2] in allowlist:
            continue
        offenders.append(config)
    return offenders


def test_fls_app_labels_are_prefixed() -> None:
    offenders = _offending_apps(apps.get_app_configs(), UNPREFIXED_LABEL_ALLOWLIST)
    assert not offenders, (
        "These FLS apps have an unprefixed label: "
        f"{', '.join(sorted(config.name for config in offenders))}. "
        'Either add label = "freedom_ls_<app>" to the app\'s AppConfig, or '
        "add its bare module name to UNPREFIXED_LABEL_ALLOWLIST above, citing "
        "the spec that commits it to extraction."
    )


def test_app_config_without_prefix_is_flagged() -> None:
    config = AppConfig("freedom_ls.health", freedom_ls)

    assert config in _offending_apps([config], UNPREFIXED_LABEL_ALLOWLIST)


def test_allowlisted_app_config_without_prefix_is_not_flagged() -> None:
    config = AppConfig("freedom_ls.icons", freedom_ls)

    assert config not in _offending_apps([config], UNPREFIXED_LABEL_ALLOWLIST)


# Renamed in an earlier pass (UserCohortDeadlineOverride -> LearnerCohortDeadlineOverride,
# unique_user_cohort_override_per_item -> unique_learner_cohort_override_per_item). Migration
# files legitimately keep the old names as RenameModel/RemoveConstraint arguments, which is
# why they're excluded here; everything else in the tree should read the new names only.
_STALE_NAMES = ("UserCohortDeadlineOverride", "unique_user_cohort_override_per_item")
_SCAN_DIRS = ("freedom_ls", "demo_content", "config", "docs")
_SCAN_SUFFIXES = (".py", ".html", ".md")


def _files_with_stale_names(base_dir: Path) -> list[Path]:
    this_file = Path(__file__).resolve()
    hits = []
    for scan_dir in _SCAN_DIRS:
        for path in (base_dir / scan_dir).rglob("*"):
            if "migrations" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix not in _SCAN_SUFFIXES or not path.is_file():
                continue
            if path.resolve() == this_file:
                continue
            text = path.read_text(encoding="utf-8")
            if any(name in text for name in _STALE_NAMES):
                hits.append(path)
    return hits


def test_pre_rename_deadline_override_name_is_gone_from_the_tree() -> None:
    hits = _files_with_stale_names(Path(settings.BASE_DIR))
    assert not hits, (
        f"Found the pre-rename name in: {[str(path) for path in hits]}. "
        "UserCohortDeadlineOverride and unique_user_cohort_override_per_item "
        "were renamed; migrations are exempt since RenameModel/RemoveConstraint "
        "legitimately keep the old name as an argument."
    )
