"""Tracking tests — context helpers and the generic ``track()`` pipeline.

Tests for the context helpers live alongside tests for the tracker so
Phase 2 and Phase 3 share setup. The tracker uses an in-test dummy schema
registered via :func:`register_event_type` inside a fixture so no test here
depends on any domain app being loaded.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel, ConfigDict, Field

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.experience_api.context import (
    build_actor_ifi,
    get_ip_address,
    hash_session_key,
)
from freedom_ls.experience_api.exceptions import TrackingSchemaError
from freedom_ls.experience_api.models import Event
from freedom_ls.experience_api.registry import REGISTRY, register_event_type
from freedom_ls.experience_api.schema_base import BaseEventSchema
from freedom_ls.experience_api.tasks import write_event
from freedom_ls.experience_api.tracking import track
from freedom_ls.experience_api.verbs import Verb

# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture
def dummy_verb() -> Verb:
    return Verb(iri="http://example.test/verbs/dummy", display="dummied")


@pytest.fixture
def dummy_schema(dummy_verb: Verb):
    class _Obj(BaseModel):
        model_config = ConfigDict(extra="forbid")
        topic_id: uuid.UUID | None = None
        topic_slug: str = Field(max_length=512)
        topic_title: str = Field(max_length=512)

    class _Ctx(BaseModel):
        model_config = ConfigDict(extra="forbid")
        course_slug: str = Field(max_length=512, default="")
        course_title: str = Field(max_length=512, default="")
        course_id: uuid.UUID | None = None

    class DummySchema(BaseEventSchema):
        object_definition: _Obj
        context_extensions: _Ctx

    register_event_type(dummy_verb, "DummyTopic", DummySchema)
    yield DummySchema
    REGISTRY.pop((dummy_verb, "DummyTopic"), None)


@pytest.fixture
def user(db, mock_site_context):
    return UserFactory()


# ---------------------------------------------------------------------------
# Context-helper tests (Phase 2)


def test_session_hash_is_lowercase_hex_of_expected_length(settings) -> None:
    settings.SECRET_KEY = "top-secret"  # noqa: S105  # pragma: allowlist secret
    h = hash_session_key("sess-key-1")
    assert h is not None
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


def test_session_hash_null_when_no_session_key() -> None:
    assert hash_session_key(None) is None
    assert hash_session_key("") is None


def test_session_hash_changes_when_secret_key_rotates(settings) -> None:
    settings.SECRET_KEY = "key-a"  # noqa: S105  # pragma: allowlist secret
    h_a = hash_session_key("s")
    settings.SECRET_KEY = "key-b"  # noqa: S105  # pragma: allowlist secret
    h_b = hash_session_key("s")
    assert h_a != h_b


def test_get_ip_address_returns_none_when_capture_disabled(settings, rf) -> None:
    settings.EXPERIENCE_API_CAPTURE_IP = False
    req = rf.get("/", REMOTE_ADDR="1.2.3.4")
    assert get_ip_address(req) is None


def test_get_ip_address_returns_ip_when_capture_enabled(settings, rf) -> None:
    settings.EXPERIENCE_API_CAPTURE_IP = True
    req = rf.get("/", REMOTE_ADDR="1.2.3.4")
    assert get_ip_address(req) == "1.2.3.4"


@pytest.mark.django_db
def test_build_actor_ifi_shape(mock_site_context, user) -> None:
    ifi = build_actor_ifi(user, mock_site_context)
    assert "|" in ifi
    host, id_part = ifi.split("|", 1)
    assert host.startswith("https://")
    assert id_part == str(user.id)
    # Email never appears in the IFI.
    assert user.email not in ifi


# ---------------------------------------------------------------------------
# Tracker pipeline tests (Phase 3)


@pytest.mark.django_db
def test_unknown_verb_object_type_raises(mock_site_context, user) -> None:
    unknown_verb = Verb(iri="x://never", display="never")
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=unknown_verb,
            object_type="Nope",
            object_id=None,
            object_definition={},
        )


@pytest.mark.django_db
def test_track_writes_event_row(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    topic_id = uuid.uuid4()
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=topic_id,
        object_definition={
            "topic_id": topic_id,
            "topic_slug": "t",
            "topic_title": "T",
        },
    )
    assert evt is not None
    assert evt.object_id == topic_id
    assert evt.verb == dummy_verb.iri
    assert evt.object_type == "DummyTopic"


@pytest.mark.django_db
def test_track_derives_actor_fields(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s",
            "topic_title": "T",
        },
    )
    assert evt is not None
    assert evt.actor_email == user.email
    assert evt.actor_display_name == (user.display_name or user.email)
    assert str(user.id) in evt.actor_ifi


@pytest.mark.django_db
def test_hard_ceiling_rejects_multi_megabyte_string(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    huge = "x" * (65537)
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=dummy_verb,
            object_type="DummyTopic",
            object_id=None,
            object_definition={
                "topic_id": None,
                "topic_slug": huge,
                "topic_title": "T",
            },
        )


@pytest.mark.django_db
def test_strict_true_raises_on_unknown_extension(
    dummy_verb, dummy_schema, mock_site_context, user, settings
) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = True
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=dummy_verb,
            object_type="DummyTopic",
            object_id=None,
            object_definition={
                "topic_id": None,
                "topic_slug": "s",
                "topic_title": "T",
            },
            context_extensions={"rogue_key": "x"},
        )


@pytest.mark.django_db
def test_strict_false_drops_unknown_extension_and_persists_rest(
    dummy_verb, dummy_schema, mock_site_context, user, settings
) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s",
            "topic_title": "T",
        },
        context_extensions={"rogue_key": "x", "course_slug": "c"},
    )
    assert evt is not None
    assert "rogue_key" not in evt.context["extensions"]
    assert evt.context["extensions"]["course_slug"] == "c"


@pytest.mark.django_db
def test_strict_false_drops_event_on_missing_required_field(
    dummy_verb, dummy_schema, mock_site_context, user, settings, caplog
) -> None:
    import logging as _logging

    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    caplog.set_level(_logging.ERROR, logger="freedom_ls.experience_api.tracking")
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            # topic_slug missing — required
            "topic_title": "T",
        },
    )
    assert evt is None
    # Log line must name the field but not the value.
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "topic_slug" in log_text


@pytest.mark.django_db
def test_per_call_strict_overrides_setting(
    dummy_verb, dummy_schema, mock_site_context, user, settings
) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=dummy_verb,
            object_type="DummyTopic",
            object_id=None,
            object_definition={
                "topic_title": "T",  # topic_slug missing
            },
            strict=True,
        )


@pytest.mark.django_db
def test_log_lines_never_contain_caller_values(
    dummy_verb, dummy_schema, mock_site_context, user, settings, caplog
) -> None:
    import logging as _logging

    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    caplog.set_level(_logging.WARNING, logger="freedom_ls.experience_api.tracking")
    sentinel = "sensitive-value-a1b2c3"
    track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "slug",
            "topic_title": sentinel,
        },
        context_extensions={"rogue_key": sentinel},
    )
    for record in caplog.records:
        assert sentinel not in record.getMessage()


@pytest.mark.django_db
def test_async_task_does_not_rely_on_thread_locals(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    """The write_event task must run successfully without thread-locals."""
    from freedom_ls.site_aware_models.models import _thread_locals

    # First, build a valid payload via track() so we have realistic fields.
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s",
            "topic_title": "T",
        },
    )
    assert evt is not None

    # Now clear thread-locals and write a second event via the task directly.
    saved_request = _thread_locals.request
    delattr(_thread_locals, "request")
    try:
        payload = {
            "id": uuid.uuid4(),
            "site_id": mock_site_context.id,
            "site_domain": mock_site_context.domain,
            "actor_user": user,
            "actor_email": user.email,
            "actor_display_name": user.display_name or user.email,
            "actor_ifi": f"https://{mock_site_context.domain}|{user.id}",
            "verb": dummy_verb.iri,
            "verb_display": dummy_verb.display,
            "object_type": "DummyTopic",
            "object_id": None,
            "object_definition": {
                "topic_id": None,
                "topic_slug": "s2",
                "topic_title": "T2",
            },
            "result": None,
            "context": {"extensions": {}},
            "statement": {"actor": {}},
            "timestamp": evt.timestamp,
            "session_id_hash": None,
            "user_agent": None,
            "ip_address": None,
            "platform": "backend",
        }
        write_event.call(payload)
        row = Event._base_manager.get(pk=payload["id"])
        assert row.site_id == mock_site_context.id
        assert row.site_domain == mock_site_context.domain
    finally:
        _thread_locals.request = saved_request


@pytest.mark.django_db
def test_dangling_pointer_guard_raises(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=dummy_verb,
            object_type="DummyTopic",
            object_id=None,
            object_definition={
                "topic_id": uuid.uuid4(),
                "topic_slug": "",  # populated id but empty snapshot
                "topic_title": "T",
            },
        )


@pytest.mark.django_db
def test_track_returns_event_instance_for_chaining(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s",
            "topic_title": "T",
        },
    )
    assert isinstance(evt, Event)
    assert evt.id is not None


# ---------------------------------------------------------------------------
# Multi-tenant cross-site isolation tests.


@pytest.mark.django_db
def test_cross_site_isolation(
    dummy_verb, dummy_schema, mock_site_context, user, mocker
) -> None:
    from django.contrib.sites.models import Site

    from freedom_ls.site_aware_models.models import _thread_locals

    # Write an event on site A (the default mock_site_context).
    evt_a = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s-a",
            "topic_title": "Site A",
        },
    )
    assert evt_a is not None

    # Create a second site and switch the thread-locals site.
    site_b, _ = Site.objects.get_or_create(
        name="SiteB", defaults={"domain": "siteb.example"}
    )
    mocker.patch(
        "freedom_ls.site_aware_models.models.get_current_site", return_value=site_b
    )
    mock_req = mocker.Mock()
    mock_req._cached_site = site_b
    _thread_locals.request = mock_req

    # Now Event.objects is filtered by site_b — site_a's event must not appear.
    assert not Event.objects.filter(pk=evt_a.pk).exists()
    # But the base manager sees both.
    assert Event._base_manager.filter(pk=evt_a.pk).exists()


@pytest.mark.django_db
def test_site_domain_snapshot_survives_site_rename(
    dummy_verb, dummy_schema, mock_site_context, user
) -> None:
    original_domain = mock_site_context.domain
    evt = track(
        actor=user,
        verb=dummy_verb,
        object_type="DummyTopic",
        object_id=None,
        object_definition={
            "topic_id": None,
            "topic_slug": "s",
            "topic_title": "T",
        },
    )
    assert evt is not None
    assert evt.site_domain == original_domain

    mock_site_context.domain = "renamed.example"
    mock_site_context.save()
    # Re-fetch via base manager; snapshot must be unchanged.
    fresh = Event._base_manager.get(pk=evt.pk)
    assert fresh.site_domain == original_domain
