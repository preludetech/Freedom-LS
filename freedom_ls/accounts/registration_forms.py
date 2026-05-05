"""Loader and protocol for site-configurable additional registration forms.

Each entry in ``SiteSignupPolicy.additional_registration_forms`` is a dotted
path to a ``django.forms.Form`` subclass that implements
``RegistrationFormProtocol``. The loader resolves these paths and validates
the target is well-formed. Any load-time misconfiguration — bad import,
wrong type, or a forbidden user-identifying field — raises
``ImproperlyConfigured``. Silent skipping would let a registration step
that should have gated a user disappear without a trace.

Per-user form callbacks (``applies_to``, ``is_complete``) are trusted to be
exception-safe. Bugs in them propagate to the caller — silently skipping a
form that raises would let a user bypass a registration step that should
have applied to them, which is a worse failure mode than a 500.

They must also return strictly ``True`` or ``False``. Any other return
value (including ``None``) raises ``TypeError``. The strict check exists
because a ``None`` return would otherwise be falsy and silently treated
as "does not apply" — bypassing a gate that should have applied.
"""

from __future__ import annotations

import inspect
from typing import Protocol, cast, runtime_checkable

from django import forms
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

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


def _forbidden_fields(form_cls: type[forms.Form]) -> set[str]:
    base_fields = getattr(form_cls, "base_fields", {}) or {}
    return set(base_fields).intersection(FORBIDDEN_FIELD_NAMES)


def load_registration_form_classes(
    dotted_paths: list[str],
) -> list[type[forms.Form]]:
    """Resolve ``dotted_paths`` to Form classes.

    Any misconfigured entry raises ``ImproperlyConfigured``. Silent skipping
    would let a registration step quietly stop gating users.
    """
    resolved: list[type[forms.Form]] = []

    for path in dotted_paths or []:
        try:
            cls = import_string(path)
        except (ImportError, AttributeError, ValueError, TypeError) as err:
            raise ImproperlyConfigured(
                f"Could not import additional registration form {path!r}: {err}"
            ) from err

        if not _is_protocol_compliant(cls):
            raise ImproperlyConfigured(
                f"Additional registration form {path!r} is not a forms.Form "
                f"subclass with the required protocol "
                f"(applies_to, is_complete, save)."
            )

        offending = _forbidden_fields(cls)
        if offending:
            raise ImproperlyConfigured(
                f"Additional registration form {path!r} defines forbidden "
                f"user-identifying field(s) {sorted(offending)!r}. The "
                f"completion view always passes request.user; remove or "
                f"rename these fields. Forbidden names: "
                f"{sorted(FORBIDDEN_FIELD_NAMES)!r}."
            )

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
        proto_cls = cast(type[RegistrationFormProtocol], cls)
        if not _strict_bool(proto_cls.applies_to(user), cls, "applies_to"):
            continue
        if not _strict_bool(proto_cls.is_complete(user), cls, "is_complete"):
            incomplete.append(cls)

    return incomplete


def _strict_bool(value: object, cls: type, method_name: str) -> bool:
    """Reject non-bool returns from ``applies_to`` / ``is_complete``.

    Why: ``None`` (or any falsy non-bool) would be treated as "doesn't apply"
    or "already complete", silently bypassing the gate. Fail loud instead.
    """
    if value is True or value is False:
        return value
    raise TypeError(
        f"{cls.__module__}.{cls.__qualname__}.{method_name} must return "
        f"True or False, got {value!r} ({type(value).__name__})."
    )
