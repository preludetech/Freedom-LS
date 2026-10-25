"""Tests for the prune_audit_log management command."""

from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from typing import cast

import pytest
import time_machine
from click import ClickException

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry


@pytest.fixture(autouse=True)
def _site_context(mock_site_context) -> None:
    """Every test here builds site-aware entries."""


@pytest.fixture
def old_and_new_entries() -> tuple[AuditLogEntry, AuditLogEntry]:
    with time_machine.travel(timezone.now() - timedelta(days=40), tick=False):
        old = cast(AuditLogEntry, AuditLogEntryFactory())
    return old, cast(AuditLogEntry, AuditLogEntryFactory())


def _call_prune(*args: str) -> str:
    out = StringIO()
    with redirect_stdout(out):
        call_command("prune_audit_log", *args)
    return out.getvalue()


@pytest.mark.django_db
def test_dry_run_deletes_nothing_and_prints_the_count(old_and_new_entries):
    out = _call_prune("--older-than", "30", "--dry-run")

    assert "Would delete 1 entries." in out
    assert AuditLogEntry.unscoped.count() == 2


@pytest.mark.django_db
def test_older_than_deletes_only_entries_older_than_that_many_days(
    old_and_new_entries,
):
    _, recent = old_and_new_entries

    out = _call_prune("--older-than", "30")

    assert "Deleted 1 entries." in out
    assert list(AuditLogEntry.unscoped.all()) == [recent]


@pytest.mark.django_db
@override_settings(AUDIT_LOG_RETENTION_DAYS=30)
def test_the_setting_supplies_the_default_age(old_and_new_entries):
    _, recent = old_and_new_entries

    _call_prune()

    assert list(AuditLogEntry.unscoped.all()) == [recent]


@pytest.mark.django_db
def test_no_age_given_anywhere_raises_and_deletes_nothing(old_and_new_entries):
    with pytest.raises(ClickException, match="--older-than"):
        _call_prune()

    assert AuditLogEntry.unscoped.count() == 2


@pytest.mark.django_db
def test_older_than_zero_raises_and_deletes_nothing(old_and_new_entries):
    with pytest.raises(ClickException):
        _call_prune("--older-than", "0")

    assert AuditLogEntry.unscoped.count() == 2


@pytest.mark.django_db
@override_settings(AUDIT_LOG_RETENTION_DAYS=0)
def test_a_retention_setting_of_zero_raises_and_deletes_nothing(old_and_new_entries):
    with pytest.raises(ClickException):
        _call_prune()

    assert AuditLogEntry.unscoped.count() == 2
