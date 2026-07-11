from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


def _raw(name: str) -> str | None:
    """Return the stripped env value, or None when unset or empty/whitespace-only."""
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def env_bool(name: str, default: bool) -> bool:
    """Parse a boolean env var. Unset/empty falls back to ``default``; a value that
    is neither truthy (true/1/yes/on) nor falsy (false/0/no/off) raises."""
    value = _raw(name)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ImproperlyConfigured(
        f"{name}={value!r} is not a valid boolean (expected one of "
        f"true/false/1/0/yes/no/on/off)."
    )


def env_int(name: str, default: int) -> int:
    """Parse an integer env var. Unset/empty falls back to ``default``; a
    non-integer value raises instead of surfacing a bare ValueError at import."""
    value = _raw(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ImproperlyConfigured(
            f"{name}={value!r} is not a valid integer."
        ) from None


def env_float(name: str, default: float | None) -> float | None:
    """Parse a float env var. Unset/empty falls back to ``default``; a
    non-numeric value raises instead of surfacing a bare ValueError at import."""
    value = _raw(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ImproperlyConfigured(f"{name}={value!r} is not a valid number.") from None
