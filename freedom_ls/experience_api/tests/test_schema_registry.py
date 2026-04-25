"""Registry tests — idempotent registration, conflict detection, unknown lookups."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from freedom_ls.experience_api.exceptions import TrackingSchemaError
from freedom_ls.experience_api.registry import (
    REGISTRY,
    get_schema,
    register_event_type,
)
from freedom_ls.experience_api.schema_base import BaseEventSchema
from freedom_ls.experience_api.verbs import Verb


@pytest.fixture
def dummy_verb() -> Verb:
    return Verb(iri="http://example.test/verbs/dummy", display="dummied")


@pytest.fixture(autouse=True)
def _clean_registry(dummy_verb: Verb):
    """Remove any registrations made by the tests so they don't leak."""
    before = dict(REGISTRY)
    yield
    for key in list(REGISTRY.keys()):
        if key not in before:
            del REGISTRY[key]


def _make_schema_class(name: str) -> type[BaseEventSchema]:
    class _Obj(BaseModel):
        topic_slug: str

    class _Ctx(BaseModel):
        pass

    return type(
        name,
        (BaseEventSchema,),
        {
            "__annotations__": {
                "object_definition": _Obj,
                "context_extensions": _Ctx,
            },
        },
    )


def test_register_event_type_adds_to_map(dummy_verb: Verb) -> None:
    schema = _make_schema_class("DummySchema")
    register_event_type(dummy_verb, "Thing", schema)
    assert get_schema(dummy_verb, "Thing") is schema


def test_register_event_type_idempotent_for_same_schema(dummy_verb: Verb) -> None:
    schema = _make_schema_class("DummySchema")
    register_event_type(dummy_verb, "Thing", schema)
    register_event_type(dummy_verb, "Thing", schema)  # must not raise


def test_register_event_type_rejects_conflicting_schema(dummy_verb: Verb) -> None:
    schema_a = _make_schema_class("DummyA")
    schema_b = _make_schema_class("DummyB")
    register_event_type(dummy_verb, "Thing", schema_a)
    with pytest.raises(RuntimeError):
        register_event_type(dummy_verb, "Thing", schema_b)


def test_get_schema_unknown_raises_tracking_schema_error(dummy_verb: Verb) -> None:
    with pytest.raises(TrackingSchemaError):
        get_schema(dummy_verb, "NeverRegistered")
