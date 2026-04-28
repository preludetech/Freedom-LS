"""Loader and protocol for site-configurable additional registration forms.

Each entry in ``SiteSignupPolicy.additional_registration_forms`` is a dotted
path to a ``django.forms.Form`` subclass that implements
``RegistrationFormProtocol``. The loader resolves these paths, validates the
target is well-formed, and degrades gracefully (logs + skips) on
misconfiguration — it MUST NOT raise into a request.
"""

from __future__ import annotations

import inspect
import logging
from typing import Protocol, cast, runtime_checkable

from django import forms
from django.contrib.auth.models import AbstractBaseUser
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset({"user", "user_id", "email"})


@runtime_checkable
class RegistrationFormProtocol(Protocol):
    """Contract for forms listed in ``additional_registration_forms``."""

    @classmethod
    def applies_to(cls, user: AbstractBaseUser) -> bool: ...

    @classmethod
    def is_complete(cls, user: AbstractBaseUser) -> bool: ...

    def save(self, user: AbstractBaseUser) -> None: ...


def _is_protocol_compliant(cls: type) -> bool:
    """Return True iff `cls` exposes the three required methods correctly."""
    if not inspect.isclass(cls):
        return False
    if not issubclass(cls, forms.Form):
        return False

    # `applies_to` and `is_complete` should be classmethods (or callable).
    for method_name in ("applies_to", "is_complete"):
        method = getattr(cls, method_name, None)
        if method is None or not callable(method):
            return False

    save_method = getattr(cls, "save", None)
    return not (save_method is None or not callable(save_method))


def _has_forbidden_field(form_cls: type[forms.Form]) -> bool:
    base_fields = getattr(form_cls, "base_fields", {}) or {}
    forbidden = set(base_fields).intersection(FORBIDDEN_FIELD_NAMES)
    return bool(forbidden)


def load_registration_form_classes(
    dotted_paths: list[str],
) -> list[type[forms.Form]]:
    """Resolve ``dotted_paths`` to Form classes, skipping bad entries.

    A misconfigured entry never raises into the caller — it is logged at
    WARNING and excluded from the result.
    """
    resolved: list[type[forms.Form]] = []

    for path in dotted_paths or []:
        try:
            cls = import_string(path)
        except (ImportError, AttributeError, ValueError, TypeError) as err:
            logger.warning(
                "Could not import additional registration form %r: %s",
                path,
                err,
            )
            continue

        if not _is_protocol_compliant(cls):
            logger.warning(
                "Additional registration form %r is not a forms.Form "
                "subclass with the required protocol; skipping",
                path,
            )
            continue

        if _has_forbidden_field(cls):
            logger.warning(
                "Additional registration form %r defines a forbidden user-"
                "identifying field (one of %s); skipping",
                path,
                sorted(FORBIDDEN_FIELD_NAMES),
            )
            continue

        resolved.append(cls)

    return resolved


def get_incomplete_forms(
    user: AbstractBaseUser, dotted_paths: list[str]
) -> list[type[forms.Form]]:
    """Return form classes that ``applies_to`` ``user`` and aren't yet complete.

    Superusers are short-circuited to ``[]`` as a baseline safety net so a
    misconfigured form can never lock out a superuser.
    """
    if getattr(user, "is_superuser", False):
        return []

    classes = load_registration_form_classes(dotted_paths)
    incomplete: list[type[forms.Form]] = []

    for cls in classes:
        # `_is_protocol_compliant` already verified `applies_to` and
        # `is_complete` exist; cast to the Protocol to satisfy the type
        # checker without `# type: ignore`.
        proto_cls = cast(type[RegistrationFormProtocol], cls)
        # `applies_to` / `is_complete` run third-party code, so any exception
        # type is possible — log and skip rather than 500 the request.
        try:
            applies = proto_cls.applies_to(user)
        except Exception as err:
            logger.warning(
                "applies_to(%r) raised on form %s: %s",
                user,
                cls.__name__,
                err,
            )
            continue
        if not applies:
            continue

        try:
            complete = proto_cls.is_complete(user)
        except Exception as err:
            logger.warning(
                "is_complete(%r) raised on form %s: %s",
                user,
                cls.__name__,
                err,
            )
            continue

        if not complete:
            incomplete.append(cls)

    return incomplete
