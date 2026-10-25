from datetime import timedelta
from typing import cast

import pytest
import time_machine

from django.utils import timezone

from freedom_ls.audit_log.exceptions import AppendOnlyError
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry


@pytest.fixture
def entry(mock_site_context) -> AuditLogEntry:
    return cast(AuditLogEntry, AuditLogEntryFactory())


@pytest.mark.django_db
def test_saving_an_existing_entry_raises(entry):
    entry.reason = "changed"

    with pytest.raises(AppendOnlyError):
        entry.save()


@pytest.mark.django_db
def test_deleting_an_entry_raises(entry):
    with pytest.raises(AppendOnlyError):
        entry.delete()


@pytest.mark.django_db
@pytest.mark.parametrize("manager_name", ["objects", "unscoped", "_base_manager"])
@pytest.mark.parametrize("call", ["update", "delete", "bulk_update"])
def test_a_queryset_refuses_to_change_or_remove_rows(entry, manager_name, call):
    queryset = getattr(AuditLogEntry, manager_name).all()
    calls = {
        "update": lambda: queryset.update(reason="x"),
        "delete": lambda: queryset.delete(),
        "bulk_update": lambda: queryset.bulk_update([entry], ["reason"]),
    }

    with pytest.raises(AppendOnlyError):
        calls[call]()

    assert AuditLogEntry.unscoped.count() == 1


@pytest.mark.django_db
def test_bulk_create_adds_entries(entry):
    copies = [
        AuditLogEntry(
            site=entry.site,
            action=entry.action,
            target_content_type=entry.target_content_type,
            target_object_id=entry.target_object_id,
            target_label=entry.target_label,
            subjects=entry.subjects,
        )
        for _ in range(2)
    ]

    AuditLogEntry.unscoped.bulk_create(copies)

    assert AuditLogEntry.unscoped.count() == 3


@pytest.mark.django_db
def test_label_and_description_for_a_registered_code(mock_site_context):
    entry = AuditLogEntryFactory(action="cohort.created")

    assert (entry.label, entry.description) == ("Cohort created", "")


@pytest.mark.django_db
def test_label_is_the_code_and_description_empty_for_an_unregistered_code(
    mock_site_context,
):
    entry = AuditLogEntryFactory(action="widget.exploded")

    assert (entry.label, entry.description) == ("widget.exploded", "")


@pytest.mark.django_db
def test_update_may_only_null_the_actor(entry):
    AuditLogEntry.unscoped.update(actor=None)

    with pytest.raises(AppendOnlyError):
        AuditLogEntry.unscoped.update(actor=None, reason="x")


@pytest.mark.django_db
def test_prune_before_deletes_only_rows_before_the_cutoff(mock_site_context):
    now = timezone.now()
    with time_machine.travel(now - timedelta(days=10), tick=False):
        AuditLogEntryFactory.create_batch(2)
    recent = AuditLogEntryFactory()

    deleted = AuditLogEntry.unscoped.all().prune_before(now - timedelta(days=5))

    assert deleted == 2
    assert list(AuditLogEntry.unscoped.all()) == [recent]


@pytest.mark.django_db
def test_prune_before_deletes_every_row_across_batches(mock_site_context):
    AuditLogEntryFactory.create_batch(5)

    deleted = AuditLogEntry.unscoped.all().prune_before(
        timezone.now() + timedelta(days=1), batch_size=2
    )

    assert deleted == 5
    assert AuditLogEntry.unscoped.count() == 0


def test_plural_name_is_spelled_entries():
    """The admin used to show "Audit log entrys" because no plural was set."""
    assert AuditLogEntry._meta.verbose_name_plural == "audit log entries"
