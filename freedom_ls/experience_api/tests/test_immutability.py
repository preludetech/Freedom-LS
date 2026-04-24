"""Immutability tests for Event and ActorErasure.

Covers the four layers of append-only enforcement per spec §"Immutability":

1. ``Event.save()`` override.
2. ``Event.delete()`` override.
3. Manager / queryset override (bulk ``update()`` / ``delete()``).
4. ``pre_save`` signal (defence in depth).

The DB-level REVOKE enforcement is covered in a separate test that runs raw
SQL through the application role.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from django.db import connection
from django.db.utils import ProgrammingError

from freedom_ls.experience_api.exceptions import EventImmutableError
from freedom_ls.experience_api.models import (
    ActorErasure,
    Event,
    _enforce_event_immutability,
)
from freedom_ls.experience_api.tests._db_role_check import require_nonsuperuser_or_skip


def _event_kwargs(site) -> dict:
    return {
        "site": site,
        "site_domain": site.domain,
        "actor_email": "a@example.com",
        "actor_display_name": "A",
        "actor_ifi": "https://x|1",
        "verb": "http://adlnet.gov/expapi/verbs/experienced",
        "verb_display": "viewed",
        "object_type": "Topic",
        "object_id": uuid.uuid4(),
        "object_definition": {"topic_slug": "t"},
        "result": None,
        "context": {"extensions": {}},
        "statement": {"actor": {}},
        "timestamp": datetime.now(UTC),
        "session_id_hash": None,
        "user_agent": None,
        "ip_address": None,
        "platform": "backend",
    }


@pytest.mark.django_db
def test_direct_objects_create_raises(mock_site_context) -> None:
    with pytest.raises(EventImmutableError):
        Event.objects.create(**_event_kwargs(mock_site_context))


@pytest.mark.django_db
def test_direct_save_raises(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    with pytest.raises(EventImmutableError):
        evt.save()


@pytest.mark.django_db
def test_save_with_tracker_flag_persists_row(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()
    # The flag is consumed on successful save.
    assert not hasattr(evt, "_tracker_authorised")
    assert Event.objects.filter(pk=evt.pk).exists()


@pytest.mark.django_db
def test_second_save_raises(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()
    # A second save must fail — rows are immutable once stored.
    with pytest.raises(EventImmutableError):
        evt.save()


@pytest.mark.django_db
def test_delete_raises(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()
    with pytest.raises(EventImmutableError):
        evt.delete()


@pytest.mark.django_db
def test_queryset_delete_raises(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()
    with pytest.raises(EventImmutableError):
        Event.objects.filter(pk=evt.pk).delete()


@pytest.mark.django_db
def test_queryset_update_raises(mock_site_context) -> None:
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()
    with pytest.raises(EventImmutableError):
        Event.objects.filter(pk=evt.pk).update(verb_display="altered")


@pytest.mark.django_db
def test_presave_signal_enforces_flag(mock_site_context) -> None:
    """Calling the pre_save handler directly on an unauthorised instance raises."""
    evt = Event(**_event_kwargs(mock_site_context))
    # No _tracker_authorised flag set.
    with pytest.raises(EventImmutableError):
        _enforce_event_immutability(sender=Event, instance=evt)


# --- DB-role-level probes --------------------------------------------------


@pytest.mark.django_db
def test_db_role_cannot_update_or_delete_event(mock_site_context) -> None:
    """Raw UPDATE / DELETE through the app role is blocked by the DB grants.

    The test verifies that migration 0002 has taken effect. If the test
    user is a Postgres superuser (e.g. local dev), the grants are bypassed
    and this test is skipped — the pre-deployment security checklist
    demands a non-superuser app role.
    """
    evt = Event(**_event_kwargs(mock_site_context))
    evt._tracker_authorised = True
    evt.save()

    require_nonsuperuser_or_skip(connection, "App connection")

    with pytest.raises(ProgrammingError), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE experience_api_event SET verb_display = 'x' WHERE id = %s",
            [str(evt.pk)],
        )
    with pytest.raises(ProgrammingError), connection.cursor() as cursor:
        cursor.execute("DELETE FROM experience_api_event WHERE id = %s", [str(evt.pk)])


# --- ActorErasure immutability --------------------------------------------


def _actor_erasure_kwargs(site) -> dict:
    return {
        "site": site,
        "target_user_id": 42,
        "erased_token": "abc123",
        "event_count": 0,
        "invoking_os_user": "test",
        "invoking_hostname": "host",
        "invoking_admin_user_id": None,
    }


@pytest.mark.django_db
def test_actor_erasure_save_on_existing_raises(mock_site_context) -> None:
    a = ActorErasure.objects.create(**_actor_erasure_kwargs(mock_site_context))
    with pytest.raises(EventImmutableError):
        a.save()


@pytest.mark.django_db
def test_actor_erasure_delete_raises(mock_site_context) -> None:
    a = ActorErasure.objects.create(**_actor_erasure_kwargs(mock_site_context))
    with pytest.raises(EventImmutableError):
        a.delete()


@pytest.mark.django_db
def test_actor_erasure_queryset_delete_raises(mock_site_context) -> None:
    ActorErasure.objects.create(**_actor_erasure_kwargs(mock_site_context))
    with pytest.raises(EventImmutableError):
        ActorErasure.objects.all().delete()


@pytest.mark.django_db
def test_actor_erasure_queryset_update_raises(mock_site_context) -> None:
    ActorErasure.objects.create(**_actor_erasure_kwargs(mock_site_context))
    with pytest.raises(EventImmutableError):
        ActorErasure.objects.all().update(event_count=99)


@pytest.mark.django_db
def test_app_role_cannot_update_or_delete_actor_erasure(
    mock_site_context,
) -> None:
    a = ActorErasure.objects.create(**_actor_erasure_kwargs(mock_site_context))

    require_nonsuperuser_or_skip(connection, "App connection")

    with pytest.raises(ProgrammingError), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE experience_api_actorerasure SET event_count = 0 WHERE id = %s",
            [str(a.pk)],
        )
    with pytest.raises(ProgrammingError), connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM experience_api_actorerasure WHERE id = %s",
            [str(a.pk)],
        )
