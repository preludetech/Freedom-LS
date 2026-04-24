"""Tests for the ``erase_actor`` management command.

Operating model: the command requires ``--confirm`` always and
``--admin-user-id`` when ``STRICT=True``. Anonymisation is
``actor_email`` / ``actor_display_name`` / ``actor_user_id=NULL`` / the
JSONB ``statement.actor`` tombstone — every other field survives. An
``ActorErasure`` audit row captures the operator identity and the count.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.experience_api.models import ActorErasure, Event
from freedom_ls.experience_api.tests._db_role_check import require_nonsuperuser_or_skip


def _write_event(
    *,
    site,
    actor_user=None,
    actor_ifi: str = "",
    actor_email: str = "a@example.com",
    actor_display_name: str = "A",
    object_id: uuid.UUID | None = None,
) -> Event:
    event = Event(
        site=site,
        site_domain=site.domain,
        actor_user=actor_user,
        actor_email=actor_email,
        actor_display_name=actor_display_name,
        actor_ifi=actor_ifi,
        verb="http://adlnet.gov/expapi/verbs/experienced",
        verb_display="viewed",
        object_type="Topic",
        object_id=object_id or uuid.uuid4(),
        object_definition={"topic_slug": "t", "topic_title": "T"},
        result=None,
        context={"extensions": {}},
        statement={
            "actor": {
                "account": {"name": str(actor_user.id) if actor_user else ""},
                "name": actor_display_name,
            },
            "verb": {"id": "http://adlnet.gov/expapi/verbs/experienced"},
            "object": {"definition": {"topic_slug": "t"}},
        },
        timestamp=datetime.now(UTC),
    )
    event._tracker_authorised = True
    event.save()
    return event


@pytest.fixture
def configured_erasure_settings(db):
    """No-op fixture retained for the tests that depend on ``db``.

    Credentials for ``DATABASES['erasure']`` are wired from environment
    variables in ``settings_dev.py`` with a ``pguser`` / ``password``
    fallback — overriding them here would defeat CI's non-superuser role
    setup.
    """
    return


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_refuses_without_confirm(mock_site_context, settings) -> None:
    user = UserFactory()
    with pytest.raises(CommandError, match="--confirm"):
        call_command("erase_actor", user_id=user.id)


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_refuses_when_strict_and_no_admin_user_id(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = True
    with pytest.raises(CommandError, match="admin-user-id"):
        call_command("erase_actor", user_id=user.id, confirm=True)


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_warns_when_permissive_and_no_admin_user_id(
    mock_site_context, settings, configured_erasure_settings, capsys
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    call_command("erase_actor", user_id=user.id, confirm=True)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_anonymises_snapshots(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    ifi = f"https://{mock_site_context.domain}|{user.id}"
    for _ in range(3):
        _write_event(
            site=mock_site_context,
            actor_user=user,
            actor_ifi=ifi,
            actor_email=user.email,
            actor_display_name="Real Name",
        )
    call_command("erase_actor", user_id=user.id, confirm=True)
    rows = list(Event._base_manager.filter(site=mock_site_context))
    assert len(rows) == 3
    for row in rows:
        assert row.actor_email.startswith("erased-")
        assert row.actor_email.endswith("@example.invalid")
        assert row.actor_display_name.startswith("Erased actor ")
        assert row.actor_user_id is None
        assert "erased-" in row.statement["actor"]["account"]["name"]


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_leaves_other_fields_untouched(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    ifi = f"https://{mock_site_context.domain}|{user.id}"
    event = _write_event(site=mock_site_context, actor_user=user, actor_ifi=ifi)
    original = {
        "verb": event.verb,
        "object_definition": event.object_definition,
        "context": event.context,
        "timestamp": event.timestamp,
    }
    call_command("erase_actor", user_id=user.id, confirm=True)
    refreshed = Event._base_manager.get(pk=event.pk)
    assert refreshed.verb == original["verb"]
    assert refreshed.object_definition == original["object_definition"]
    assert refreshed.context == original["context"]
    # Timestamp preserved to the microsecond.
    assert refreshed.timestamp == original["timestamp"]


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_finds_events_via_ifi_when_user_id_already_null(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    ifi = f"https://{mock_site_context.domain}|{user.id}"
    event = _write_event(site=mock_site_context, actor_user=None, actor_ifi=ifi)
    call_command("erase_actor", user_id=user.id, confirm=True)
    refreshed = Event._base_manager.get(pk=event.pk)
    assert refreshed.actor_email.startswith("erased-")


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_ifi_match_does_not_false_positive_across_user_ids(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user_a = UserFactory()
    user_b = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    ifi_a = f"https://{mock_site_context.domain}|{user_a.id}"
    ifi_b = f"https://{mock_site_context.domain}|{user_b.id}"
    ev_a = _write_event(site=mock_site_context, actor_user=user_a, actor_ifi=ifi_a)
    ev_b = _write_event(site=mock_site_context, actor_user=user_b, actor_ifi=ifi_b)

    call_command("erase_actor", user_id=user_a.id, confirm=True)

    ev_a_after = Event._base_manager.get(pk=ev_a.pk)
    ev_b_after = Event._base_manager.get(pk=ev_b.pk)
    assert ev_a_after.actor_email.startswith("erased-")
    assert not ev_b_after.actor_email.startswith("erased-")


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_ifi_match_does_not_false_positive_when_user_id_is_suffix(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    """IFI match must treat ``|1`` and ``|11`` as distinct.

    The LIKE pattern ``%|1`` only matches strings whose final two
    characters are ``|`` and ``1`` — it must NOT match strings ending in
    ``|11``, ``|21``, etc. This test pins that behaviour using synthetic
    IFIs so the guarantee is exercised regardless of factory-generated IDs.
    """
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    target_ifi = f"https://{mock_site_context.domain}|1"
    decoy_ifis = [
        f"https://{mock_site_context.domain}|11",
        f"https://{mock_site_context.domain}|21",
        f"https://{mock_site_context.domain}|100",
    ]
    target_ev = _write_event(
        site=mock_site_context, actor_user=None, actor_ifi=target_ifi
    )
    decoy_evs = [
        _write_event(site=mock_site_context, actor_user=None, actor_ifi=ifi)
        for ifi in decoy_ifis
    ]
    # The non-existent user id 1 avoids colliding with the factory-created user.
    assert user.id != 1
    call_command("erase_actor", user_id=1, confirm=True)

    assert Event._base_manager.get(pk=target_ev.pk).actor_email.startswith("erased-")
    for ev in decoy_evs:
        assert not Event._base_manager.get(pk=ev.pk).actor_email.startswith("erased-")


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_respects_configured_blockers(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = [
        "freedom_ls.experience_api.tests.test_erasure.always_block"
    ]
    with pytest.raises(CommandError, match="blocker"):
        call_command("erase_actor", user_id=user.id, confirm=True)


def always_block(user_id: int) -> bool:
    """Test blocker — always refuses to erase."""
    return True


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erase_actor_writes_audit_row(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    user = UserFactory()
    admin = UserFactory()
    settings.EXPERIENCE_API_STRICT_VALIDATION = True
    ifi = f"https://{mock_site_context.domain}|{user.id}"
    _write_event(site=mock_site_context, actor_user=user, actor_ifi=ifi)
    _write_event(site=mock_site_context, actor_user=user, actor_ifi=ifi)
    call_command(
        "erase_actor",
        user_id=user.id,
        confirm=True,
        admin_user_id=admin.id,
    )
    audit = ActorErasure._base_manager.get(target_user_id=user.id)
    assert audit.event_count == 2
    assert audit.invoking_admin_user_id == admin.id
    assert audit.invoking_os_user
    assert audit.invoking_hostname


@pytest.mark.django_db(databases=["default", "erasure"], transaction=True)
def test_erasure_role_cannot_update_actor_erasure(
    mock_site_context, settings, configured_erasure_settings
) -> None:
    """Append-only guard also covers the erasure role.

    Skipped when the erasure connection user is a Postgres superuser.
    """
    from django.db import connections

    user = UserFactory()
    ifi = f"https://{mock_site_context.domain}|{user.id}"
    _write_event(site=mock_site_context, actor_user=user, actor_ifi=ifi)
    call_command("erase_actor", user_id=user.id, confirm=True, admin_user_id=1)

    audit = ActorErasure._base_manager.get(target_user_id=user.id)
    connection = connections["erasure"]
    require_nonsuperuser_or_skip(connection, "Erasure connection user")
    from django.db.utils import ProgrammingError

    with pytest.raises(ProgrammingError), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE experience_api_actorerasure SET event_count = 0 WHERE id = %s",
            [str(audit.pk)],
        )
