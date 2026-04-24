"""Generic ``track()`` helper — the single tracker entry point.

Callers pass pre-built snapshot dicts. Domain apps wrap this in per-event-
type helpers living in the owning app's ``xapi_events.py``.

Pipeline (see ``1. spec.md`` §"Validation behaviour"):

1. Resolve request (explicit arg > ``_thread_locals`` > ``None``) and pull
   site / domain / session-hash / UA / IP.
2. Enforce the hard per-string byte ceiling (DoS guard).
3. Look up the registered schema for ``(verb, object_type)``.
4. Validate the composed input against the schema. On failure, delegate to
   :func:`handle_validation_error` which either re-raises, returns the
   cleaned schema (permissive / unknown-key recovery), or returns ``None``
   to signal "drop the event".
5. Run the dangling-pointer guard: any schema-recognised ``_id`` populated
   but its paired snapshot empty raises.
6. Derive the actor snapshot (email, display name, IFI).
7. Compose the full xAPI statement (denormalised payload).
8. Enqueue :func:`freedom_ls.experience_api.tasks.write_event` with the
   fully-resolved payload.

Log hygiene: every log line, every exception message, every structured
field names **field names only** — never caller-supplied values. Callers
may pass anything in ``object_definition`` / ``result`` /
``context_extensions`` and the tracker must not echo it back.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.site_aware_models.models import _thread_locals

from .context import (
    build_actor_ifi,
    get_current_site_and_domain,
    get_ip_address,
    get_user_agent,
    hash_session_key,
)
from .exceptions import TrackingSchemaError
from .models import Event
from .registry import get_schema
from .schema_base import HARD_CEILING_BYTES, BaseEventSchema
from .tasks import write_event
from .verbs import Verb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers


def _iter_strings(value: Any):
    """Yield every ``str`` value nested inside dicts / lists."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def _enforce_hard_ceiling(*payloads: Any) -> None:
    """Raise :class:`TrackingSchemaError` if any nested string is oversize."""
    for payload in payloads:
        if payload is None:
            continue
        for s in _iter_strings(payload):
            if len(s.encode("utf-8")) > HARD_CEILING_BYTES:
                raise TrackingSchemaError(
                    f"Payload contains a string longer than "
                    f"{HARD_CEILING_BYTES} bytes (field-name-only logging)."
                )


def _log_field_names_only(errors: list[Any]) -> list[str]:
    """Reduce Pydantic error dicts to dotted field paths — never values."""
    paths: list[str] = []
    for err in errors:
        loc = err.get("loc", ())
        paths.append(".".join(str(p) for p in loc))
    return paths


def _strip_unknown_extension_keys(
    schema_cls: type[BaseEventSchema],
    context_extensions: dict,
    errors: list[Any],
) -> tuple[dict, list[str]]:
    """Remove unknown keys from ``context_extensions`` per Pydantic errors.

    Returns ``(cleaned_dict, dropped_names)``.
    """
    dropped: list[str] = []
    cleaned = dict(context_extensions)
    for err in errors:
        loc = err.get("loc", ())
        if (
            err.get("type") == "extra_forbidden"
            and len(loc) >= 2
            and loc[0] == "context_extensions"
        ):
            key = loc[1]
            if key in cleaned:
                cleaned.pop(key)
                dropped.append(str(key))
    return cleaned, dropped


def _all_unknown_extensions(errors: list[Any]) -> bool:
    """True when every error is an unknown ``context_extensions`` key."""
    if not errors:
        return False
    for err in errors:
        loc = err.get("loc", ())
        if err.get("type") != "extra_forbidden":
            return False
        if not (len(loc) >= 2 and loc[0] == "context_extensions"):
            return False
    return True


def handle_validation_error(
    exc: ValidationError,
    strict_mode: bool,
    verb: Verb,
    object_type: str,
    object_definition: dict,
    result: dict | None,
    context_extensions: dict,
) -> BaseEventSchema | None:
    """Strict-vs-permissive validation-error handler.

    Strict mode: re-raise as :class:`TrackingSchemaError` with a
    field-name-only message.

    Permissive mode:

    - If every error is an unknown ``context_extensions`` key: drop the
      offending keys, re-validate, return the cleaned schema. Log dropped
      key names at warning.
    - Otherwise: log at error and return ``None`` to signal "drop the
      event" — tracking failures must not break the user's primary action.
    """
    errors = exc.errors()
    field_paths = _log_field_names_only(errors)

    if strict_mode:
        raise TrackingSchemaError(
            f"Validation failed for (verb={verb.display!r}, "
            f"object_type={object_type!r}): {field_paths}"
        )

    schema_cls = get_schema(verb, object_type)

    if _all_unknown_extensions(errors):
        cleaned, dropped = _strip_unknown_extension_keys(
            schema_cls, context_extensions, errors
        )
        logger.warning(
            "experience_api: unknown context_extensions keys dropped "
            "(verb=%s, object_type=%s): %s",
            verb.display,
            object_type,
            dropped,
        )
        try:
            return schema_cls(
                object_definition=object_definition,
                result=result,
                context_extensions=cleaned,
            )
        except ValidationError as re_exc:  # pragma: no cover - defensive
            logger.error(
                "experience_api: validation still failing after stripping "
                "unknown keys (verb=%s, object_type=%s): %s",
                verb.display,
                object_type,
                _log_field_names_only(re_exc.errors()),
            )
            return None

    logger.error(
        "experience_api: validation error — event dropped (verb=%s, "
        "object_type=%s): %s",
        verb.display,
        object_type,
        field_paths,
    )
    return None


def _enforce_dangling_pointer_rule(validated: BaseEventSchema) -> None:
    """Raise if any ``<prefix>_id`` is populated but its snapshot is empty.

    The guard walks the nested ``ObjectDefinition`` and ``ContextExtensions``
    models and pairs every ``<prefix>_id`` field with ``<prefix>_slug`` /
    ``<prefix>_title`` / ``<prefix>_name`` when present. An ``_id`` that
    points somewhere but has no paired snapshot would leave us with an
    audit record that can neither be joined to live data (if the record is
    gone) nor interpreted standalone — precisely what the spec forbids.
    """
    sections: list[BaseModel] = [validated.object_definition]
    if validated.context_extensions is not None:
        sections.append(validated.context_extensions)

    for section in sections:
        data = section.model_dump()
        for key, value in data.items():
            if not key.endswith("_id") or value in (None, ""):
                continue
            prefix = key[: -len("_id")]
            for suffix in ("_slug", "_title", "_name"):
                paired = f"{prefix}{suffix}"
                if paired in data and not data[paired]:
                    raise TrackingSchemaError(
                        f"Dangling-pointer violation: {key!r} populated "
                        f"but {paired!r} is empty."
                    )


def compose_statement(
    actor_ifi: str,
    verb: Verb,
    validated: BaseEventSchema,
) -> dict:
    """Build the denormalised xAPI statement payload stored as JSONB.

    This is a pure function — no DB hits — so it's cheap to test. The
    shape matches the xAPI spec closely enough for external tools to
    consume, though we do not claim strict xAPI 1.0.3 compliance.
    """
    # mode="json" serialises UUID / datetime to JSON-compatible primitives;
    # the statement column is JSONField so primitives are required.
    obj = validated.object_definition.model_dump(mode="json")
    ctx_extensions = (
        validated.context_extensions.model_dump(mode="json")
        if validated.context_extensions is not None
        else {}
    )
    result = (
        validated.result.model_dump(mode="json")
        if validated.result is not None
        else None
    )
    statement: dict[str, Any] = {
        "actor": {
            "account": {"name": actor_ifi.split("|", 1)[-1] if actor_ifi else ""}
        },
        "verb": {"id": verb.iri, "display": {"en-US": verb.display}},
        "object": {"definition": obj},
        "context": {"extensions": ctx_extensions},
    }
    if result is not None:
        statement["result"] = result
    return statement


# ---------------------------------------------------------------------------
# Public API


def track(
    *,
    actor: User | None,
    verb: Verb,
    object_type: str,
    object_id: UUID | None,
    object_definition: dict,
    result: dict | None = None,
    context_extensions: dict | None = None,
    request: HttpRequest | None = None,
    strict: bool | None = None,
) -> Event | None:
    """Validate, compose, and persist one xAPI-shaped event.

    Keyword-only arguments. See :mod:`freedom_ls.experience_api.tracking`
    module docstring for the full pipeline. Returns the persisted
    :class:`~freedom_ls.experience_api.models.Event` on success, or ``None``
    when permissive-mode validation drops the event.
    """
    # 1. Resolve request.
    req = request or getattr(_thread_locals, "request", None)

    # 2. Resolve site / domain / session / UA / IP.
    site, site_domain = get_current_site_and_domain(req)
    session_key = None
    if req is not None:
        session = getattr(req, "session", None)
        session_key = getattr(session, "session_key", None) if session else None
    session_id_hash = hash_session_key(session_key)
    ip = get_ip_address(req)
    ua = get_user_agent(req)

    # 3. Enforce the hard per-string ceiling BEFORE Pydantic sees the data.
    _enforce_hard_ceiling(object_definition, result, context_extensions or {})

    # 4. Look up and validate.
    schema_cls = get_schema(verb, object_type)
    strict_mode = (
        strict
        if strict is not None
        else getattr(settings, "EXPERIENCE_API_STRICT_VALIDATION", False)
    )
    try:
        validated = schema_cls(
            object_definition=object_definition,
            result=result,
            context_extensions=context_extensions or {},
        )
    except ValidationError as exc:
        outcome = handle_validation_error(
            exc,
            strict_mode,
            verb,
            object_type,
            object_definition,
            result,
            context_extensions or {},
        )
        if outcome is None:
            return None
        validated = outcome

    # 5. Dangling-pointer guard.
    _enforce_dangling_pointer_rule(validated)

    # 6. Derive actor snapshot.
    actor_ifi = build_actor_ifi(actor, site) if actor else ""
    actor_email = getattr(actor, "email", "") if actor else ""
    actor_display_name = (
        (getattr(actor, "display_name", "") or actor_email) if actor else ""
    )

    # 7. Compose the full xAPI statement.
    statement = compose_statement(actor_ifi, verb, validated)

    # 8. Build the fully-resolved payload. No _thread_locals reads beyond here.
    event_id = uuid4()
    payload: dict[str, Any] = {
        "id": event_id,
        "site_id": getattr(site, "id", None) if site is not None else None,
        "site_domain": site_domain or "",
        "actor_user": actor,
        "actor_email": actor_email,
        "actor_display_name": actor_display_name,
        "actor_ifi": actor_ifi,
        "verb": verb.iri,
        "verb_display": verb.display,
        "object_type": object_type,
        "object_id": object_id,
        "object_definition": validated.object_definition.model_dump(mode="json"),
        "result": (
            validated.result.model_dump(mode="json")
            if validated.result is not None
            else None
        ),
        "context": {
            "extensions": (
                validated.context_extensions.model_dump(mode="json")
                if validated.context_extensions is not None
                else {}
            )
        },
        "statement": statement,
        "timestamp": timezone.now(),
        "session_id_hash": session_id_hash,
        "user_agent": ua,
        "ip_address": ip,
        "platform": "backend",
    }

    # 9. Dispatch the write.
    #
    # Django Tasks normalise payloads to JSON on enqueue, which would strip
    # UUID / datetime / model-instance types. While we run under
    # ImmediateBackend (the only supported configuration — see apps.py
    # ready() guard) we call the task synchronously through its `call`
    # helper, which bypasses serialisation. If operators flip to a queued
    # backend they must also wire a serialisation layer per the spec
    # preconditions; the guard enforces acknowledgement.
    write_event.call(payload)

    # Return the persisted row — callers chain via .id (e.g. PROGRESSED).
    # Use the `default` manager bypass: Event.objects is site-filtered which
    # would not find rows with no request in the thread-locals. Use
    # `._base_manager` to read back by PK deterministically.
    return Event._base_manager.filter(pk=event_id).first()
